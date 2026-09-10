"""Tests for kod/planner.py (Plan A: read-only plan preview)."""

from dataclasses import replace
from unittest.mock import patch

import lupa
import pytest


def _to_lua(lua, value):
    if isinstance(value, dict):
        t = lua.table()
        for k, v in value.items():
            t[k] = _to_lua(lua, v)
        return t
    if isinstance(value, list):
        t = lua.table()
        for i, v in enumerate(value, 1):
            t[i] = _to_lua(lua, v)
        return t
    return value


def make_conf(**sections):
    """Build a LuaTable conf, same shape as production (nil for missing keys)."""
    lua = lupa.LuaRuntime()
    t = lua.table()
    for k, v in sections.items():
        t[k] = _to_lua(lua, v)
    return t


class TestStepModel:
    def test_defaults(self):
        from kod.planner import Step

        s = Step("package", "git")
        assert s.program == ""
        assert s.args == ()
        assert s.chroot is False
        assert s.timeout_s == 300
        assert s.on_error == "abort"
        assert s.meta == {}

    def test_to_dict_roundtrip(self):
        from kod.planner import Step

        s = Step("package", "git", program="pacman", args=("-S", "git"),
                 on_error="warn", meta={"repo": "official"})
        d = s.to_dict()
        assert d == {
            "kind": "package", "name": "git", "program": "pacman",
            "args": ["-S", "git"], "chroot": False, "timeout_s": 300,
            "on_error": "warn", "meta": {"repo": "official"},
        }

    def test_render_is_deterministic(self):
        from kod.planner import Step, render_plan

        steps = [Step("package", "b", meta={"x": 1, "a": 2}), Step("service", "sshd")]
        assert render_plan(steps, "empty") == render_plan(steps, "empty")

    def test_render_format(self):
        from kod.planner import Step, render_plan

        out = render_plan(
            [Step("disk", "wipe:/dev/vda", program="wipefs", args=("-a", "/dev/vda")),
             Step("system", "base-packages", meta={"kernel": "linux"}),
             Step("system", "bootloader")],
            "empty", "example/testvm/configuration.lua")
        lines = out.splitlines()
        assert lines[0] == "# kod plan"
        assert lines[1] == "# baseline=empty config=example/testvm/configuration.lua"
        assert lines[2] == "001 [disk] wipe:/dev/vda: wipefs -a /dev/vda"
        assert lines[3] == '002 [system] base-packages: {"kernel": "linux"}'
        assert lines[4] == "003 [system] bootloader:"


class TestDiskSteps:
    def test_wipe_partition_format_sequence(self):
        from kod.planner import plan_disk_steps

        conf = make_conf(devices={
            "disk0": {"device": "/dev/vda", "partitions": {
                "1": {"name": "boot", "size": "512M", "type": "esp", "mountpoint": "/boot"},
                "2": {"name": "root", "size": "100%", "type": "btrfs", "mountpoint": "/"},
            }},
        })
        steps = plan_disk_steps(conf)
        assert [(s.kind, s.name) for s in steps] == [
            ("disk", "wipe:/dev/vda"),
            ("disk", "partition:boot"),
            ("disk", "format:boot"),
            ("disk", "partition:root"),
            ("disk", "format:root"),
        ]
        assert steps[0].args == ("-a", "/dev/vda")
        # 100% size -> end=0, esp type ef00 (filesystem.py:285-289)
        assert steps[3].args == ("-n", "0:0:0", "-t", "0:8300", "-c", "0:root", "/dev/vda")
        assert steps[1].args == ("-n", "0:0:+512M", "-t", "0:ef00", "-c", "0:boot", "/dev/vda")
        assert steps[4].program == "mkfs.btrfs -f"
        assert steps[4].args == ("/dev/vda2",)
        assert steps[3].meta == {"size": "100%", "filesystem": "btrfs", "mountpoint": "/"}

    def test_nvme_device_suffix(self):
        from kod.planner import plan_disk_steps

        conf = make_conf(devices={
            "disk0": {"device": "/dev/nvme0n1", "partitions": {
                "1": {"name": "root", "size": "100%", "type": "noformat", "mountpoint": "/"},
            }},
        })
        steps = plan_disk_steps(conf)
        # nvme -> 'p' suffix (filesystem.py:350); noformat -> no format step, no -t flag
        assert steps[1].args == ("-n", "0:0:0", "-c", "0:root", "/dev/nvme0n1")
        assert len(steps) == 2

    def test_no_devices(self):
        from kod.planner import plan_disk_steps

        assert plan_disk_steps(make_conf()) == []


BASE_PKGS = {"kernel": "linux-lts",
             "base": ["base", "base-devel", "intel-ucode"]}


class TestPlanInstall:
    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_full_order_and_content(self, _mock):
        from kod.planner import plan_install

        conf = make_conf(
            devices={"disk0": {"device": "/dev/vda", "partitions": {
                "1": {"name": "boot", "size": "512M", "type": "esp", "mountpoint": "/boot"}}}},
            repos={"official": {}, "aur": {"package": "yay"}},
            packages=["git"],
            services={"sshd": {}},
            users={"bob": {"programs": {"vim": {"enable": True, "deploy_config": True}}}},
        )
        steps = plan_install(conf)
        kinds_names = [(s.kind, s.name) for s in steps]
        assert kinds_names[0] == ("disk", "wipe:/dev/vda")
        # system phase steps in install-flow order (kod.py:186-213)
        phases = [n for k, n in kinds_names if k == "system"]
        assert phases == ["base-packages", "repos", "configure-system", "bootloader", "kod-user"]
        # packages: "git" from conf.packages; "vim" from bob's enabled program
        # (_proc_user_programs adds program names as packages too)
        pkgs = [s for s in steps if s.kind == "package"]
        assert [p.name for p in pkgs] == ["git", "vim"]
        assert pkgs[0].meta == {"action": "install", "repo": "official"}
        base_step = next(s for s in steps if s.name == "base-packages")
        assert base_step.meta == {"kernel": "linux-lts", "base": ["base", "base-devel", "intel-ucode"]}
        repos_step = next(s for s in steps if s.name == "repos")
        assert repos_step.meta == {"repos": ["aur", "official"], "base_packages": {"aur": "yay"}}

    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_repo_prefix_parsing(self, _mock):
        from kod.planner import plan_install

        conf = make_conf(packages=["git", "aur:mylib"])
        pkgs = [s for s in plan_install(conf) if s.kind == "package"]
        assert {p.name: p.meta["repo"] for p in pkgs} == {"git": "official", "mylib": "aur"}

    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_services_users_programs(self, _mock):
        from kod.planner import plan_install

        conf = make_conf(
            services={"sshd": {}},
            users={"bob": {
                "programs": {"vim": {"enable": True, "deploy_config": True},
                             "off": {"enable": False}},
                "services": {"gpg": {"enable": True}}}},
        )
        steps = plan_install(conf)
        svcs = [(s.name, s.meta) for s in steps if s.kind == "service"]
        assert ("sshd", {"action": "enable"}) in svcs
        assert ("gpg", {"action": "enable", "user": "bob"}) in svcs
        users = [s.name for s in steps if s.kind == "user"]
        progs = [(s.name, s.meta) for s in steps if s.kind == "program"]
        assert users == ["bob"]
        assert progs == [("bob/vim", {"deploy_config": True, "run_script": False})]
