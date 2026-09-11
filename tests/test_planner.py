"""Tests for kod/planner.py (Plan A: read-only plan preview)."""

import os
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import lupa
import pytest

EXAMPLE = Path(__file__).parent.parent / "example" / "testvm"


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


class TestPartitionPrediction:
    def test_predict_partition_list_sda(self):
        """predict_partition_list handles /dev/sdaX naming."""
        from kod.planner import predict_partition_list

        conf = make_conf(devices={
            "disk0": {"device": "/dev/sda", "partitions": {
                "1": {"name": "boot", "size": "512M", "type": "esp", "mountpoint": "/boot"},
                "2": {"name": "root", "size": "100%", "type": "btrfs", "mountpoint": "/"},
            }},
        })
        parts = predict_partition_list(conf)
        assert len(parts) == 2
        assert parts[0] == {"device": "/dev/sda1", "mountpoint": "/boot", "filesystem": "esp"}
        assert parts[1] == {"device": "/dev/sda2", "mountpoint": "/", "filesystem": "btrfs"}

    def test_predict_partition_list_nvme(self):
        """predict_partition_list handles /dev/nvmXcYpZ naming."""
        from kod.planner import predict_partition_list

        conf = make_conf(devices={
            "disk0": {"device": "/dev/nvme0n1", "partitions": {
                "1": {"name": "boot", "size": "512M", "type": "esp", "mountpoint": "/boot"},
                "2": {"name": "root", "size": "100%", "type": "ext4", "mountpoint": "/"},
            }},
        })
        parts = predict_partition_list(conf)
        assert len(parts) == 2
        assert parts[0] == {"device": "/dev/nvme0n1p1", "mountpoint": "/boot", "filesystem": "esp"}
        assert parts[1] == {"device": "/dev/nvme0n1p2", "mountpoint": "/", "filesystem": "ext4"}

    def test_predict_partition_list_malformed_raises(self):
        """predict_partition_list raises ValueError on missing root partition."""
        from kod.planner import predict_partition_list

        # No root partition
        conf = make_conf(devices={
            "disk0": {"device": "/dev/sda", "partitions": {
                "1": {"name": "boot", "size": "512M", "type": "esp", "mountpoint": "/boot"},
            }},
        })
        with pytest.raises(ValueError, match="root.*partition"):
            predict_partition_list(conf)

    def test_predict_partition_list_empty_devices(self):
        """predict_partition_list returns empty list for no devices."""
        from kod.planner import predict_partition_list

        parts = predict_partition_list(make_conf())
        assert parts == []


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


def make_dist(kernel_update=False):
    from types import SimpleNamespace

    return SimpleNamespace(kernel_update_required=lambda *a, **k: kernel_update)


class TestPlanRebuild:
    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_diff_mapping(self, _mock):
        from kod.planner import plan_rebuild

        conf = make_conf(packages=["keep", "new"])
        current_packages = {"packages": ["keep", "gone"], "kernel": "linux"}
        steps = plan_rebuild(conf, make_dist(), current_packages, [], {})
        acts = {s.name: s.meta["action"] for s in steps if s.kind == "package"}
        assert acts == {"gone": "remove", "new": "install"}  # "keep" satisfied -> no step
        removed = next(s for s in steps if s.name == "gone")
        assert removed.on_error == "warn"

    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_service_diff_and_order(self, _mock):
        from kod.planner import plan_rebuild

        conf = make_conf(services={"newsvc": {}})
        current_packages = {"packages": [], "kernel": "linux"}
        steps = plan_rebuild(conf, make_dist(), current_packages, ["oldsvc"], {})
        names = [s.name for s in steps if s.kind == "service"]
        assert names == ["oldsvc", "newsvc"]  # disable before enable (kod.py:365-391)
        acts = {s.name: s.meta["action"] for s in steps if s.kind == "service"}
        assert acts == {"oldsvc": "disable", "newsvc": "enable"}

    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_new_generation_skips_disable(self, _mock):
        from kod.planner import plan_rebuild

        conf = make_conf(services={})
        steps = plan_rebuild(conf, make_dist(), {"packages": []}, ["oldsvc"], {},
                             new_generation=True)
        assert not [s for s in steps if s.kind == "service"]

    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_kernel_hook_step(self, _mock):
        from kod.planner import plan_rebuild

        conf = make_conf(boot={"kernel": {"package": "linux-lts"}})
        current_packages = {"packages": [], "kernel": "linux"}
        steps = plan_rebuild(conf, make_dist(kernel_update=True), current_packages, [], {})
        kernel_steps = [s for s in steps if s.kind == "system" and "update" in s.name]
        assert len(kernel_steps) == 2
        assert kernel_steps[0].name == "kernel-update"
        assert kernel_steps[0].meta.get("kernel") == "linux-lts"
        assert kernel_steps[1].name == "initramfs-update"
        assert kernel_steps[1].meta.get("kernel") == "linux-lts"

    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_update_flag(self, _mock):
        from kod.planner import Step, plan_rebuild

        conf = make_conf()
        steps = plan_rebuild(conf, make_dist(), {"packages": []}, [], {}, update=True)
        assert steps[0] == Step("system", "update-packages")


class TestBuildPlan:
    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_dispatch(self, _mock):
        from kod.planner import build_plan

        conf = make_conf(packages=["git"])
        empty = build_plan(conf, baseline="empty")
        # install plan starts with system phases; rebuild plan never has them
        assert [s.name for s in empty if s.kind == "system"][:2] == ["base-packages", "repos"]

        current = build_plan(conf, make_dist(), baseline="current",
                             current_packages={"packages": []}, current_services=[])
        assert not [s for s in current if s.name == "base-packages"]


class TestPlanCli:
    @patch("kod.kod._load_current_state",
           return_value=("/kod/generations/1", {"packages": []}, [], {}))
    @patch("kod.kod.load_config")
    def test_plan_current_baseline(self, mock_load, _mock_state):
        from click.testing import CliRunner
        from kod.kod import cli

        mock_load.return_value = make_conf(packages=["git"])
        with patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS):
            result = CliRunner().invoke(cli, ["plan", "--baseline", "current"])
        assert result.exit_code == 0, result.output
        assert "# kod plan" in result.output
        assert "baseline=current" in result.output

    @patch("kod.kod.load_config")
    def test_plan_empty_baseline_needs_no_state(self, mock_load):
        from click.testing import CliRunner
        from kod.kod import cli

        mock_load.return_value = make_conf()
        with patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS):
            result = CliRunner().invoke(cli, ["plan", "--baseline", "empty"])
        assert result.exit_code == 0, result.output
        assert "baseline=empty" in result.output

    @patch("kod.kod.load_config")
    def test_plan_missing_generation_hints_empty(self, mock_load):
        from click.testing import CliRunner
        from kod.kod import cli

        mock_load.return_value = make_conf()
        result = CliRunner().invoke(cli, ["plan"])  # default baseline=current
        assert result.exit_code != 0
        assert "--baseline empty" in result.output


class TestRebuildDryRun:
    @patch("kod.kod._load_current_state",
           return_value=("/kod/generations/1", {"packages": []}, [], {}))
    @patch("kod.kod.load_config")
    def test_dry_run_prints_plan_and_executes_nothing(self, mock_load, _mock_state):
        from click.testing import CliRunner
        from kod.kod import cli

        mock_load.return_value = make_conf()
        with patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS), \
             patch("kod.kod.exec") as mock_exec:
            result = CliRunner().invoke(cli, ["rebuild", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "# kod plan" in result.output
        mock_exec.assert_not_called()

    def test_dry_run_flag_registered(self):
        from click.testing import CliRunner
        from kod.kod import cli

        result = CliRunner().invoke(cli, ["rebuild", "--help"])
        assert "--dry-run" in result.output


GOLDEN = Path(__file__).parent / "golden" / "plan-testvm-empty.txt"


class TestGolden:
    @patch("kod.system.packages.get_base_packages", return_value={
        "kernel": "linux-lts",
        "base": ["arch-install-scripts", "bash-completion", "base", "base-devel",
                 "btrfs-progs", "dracut", "git", "intel-ucode", "linux-firmware",
                 "mlocate", "schroot", "sudo", "whois"],
    })
    def test_testvm_empty_baseline_golden(self, _mock):
         from kod._core import load_config as load_lua
         from kod.planner import plan_install, render_plan

         conf = load_lua(str(EXAMPLE / "configuration.lua"))
         out = render_plan(plan_install(conf), "empty", "example/testvm/configuration.lua")
         if os.environ.get("KODOS_WRITE_GOLDEN"):
             GOLDEN.parent.mkdir(exist_ok=True)
             GOLDEN.write_text(out)
             pytest.skip("golden written")
         assert out == GOLDEN.read_text()

    @patch("kod.system.packages.get_base_packages", return_value={
         "kernel": "linux-lts",
         "base": ["arch-install-scripts", "bash-completion", "base", "base-devel",
                  "btrfs-progs", "dracut", "git", "intel-ucode", "linux-firmware",
                  "mlocate", "schroot", "sudo", "whois"],
    })
    def test_testvm_preview_sanity(self, _mock):
         from kod._core import load_config as load_lua
         from kod.planner import plan_install

         conf = load_lua(str(EXAMPLE / "configuration.lua"))
         steps = plan_install(conf)
         assert ("disk", "wipe:/dev/vda") in [(s.kind, s.name) for s in steps]


class TestHookVisibility:
     """Tests for hook visibility in plan output (Task 5)."""
     
     def test_plan_includes_hooks_in_meta_when_registered(self):
         """Plan includes hook event names in step meta when hooks exist."""
         from kod.planner import Step, _attach_hooks_to_steps
         
         # Create some hooks
         hooks_map = {
             "post:service": [lambda step, ctx: None],
             "pre:package": [lambda step, ctx: None],
         }
         
         # Create steps
         steps = [
             Step("service", "nginx", meta={"action": "enable"}),
             Step("package", "vim", meta={"action": "install"}),
             Step("system", "kernel-update", meta={"kernel": "linux"}),
         ]
         
         # Attach hooks
         result = _attach_hooks_to_steps(steps, hooks_map)
         
         # Verify hooks attached to correct steps
         service_step = [s for s in result if s.kind == "service"][0]
         assert "hooks" in service_step.meta
         assert service_step.meta["hooks"] == ["post:service"]
         
         pkg_step = [s for s in result if s.kind == "package"][0]
         assert "hooks" in pkg_step.meta
         assert pkg_step.meta["hooks"] == ["pre:package"]
         
         # System step should not have hooks (no matching events)
         sys_step = [s for s in result if s.kind == "system"][0]
         assert "hooks" not in sys_step.meta
     
     def test_plan_without_hooks_no_hooks_field(self):
         """Plan without registered hooks doesn't include hooks field."""
         from kod.planner import Step, _attach_hooks_to_steps
         
         steps = [
             Step("service", "nginx", meta={"action": "enable"}),
             Step("package", "vim", meta={"action": "install"}),
         ]
         
         # Empty hooks map
         result = _attach_hooks_to_steps(steps, {})
         
         # Verify no hooks added
         for step in result:
             assert "hooks" not in step.meta
     
     def test_plan_with_multiple_hook_types(self):
         """Plan with multiple hook types shows all applicable events sorted."""
         from kod.planner import Step, _attach_hooks_to_steps
         
         # Register multiple hooks for same kind
         hooks_map = {
             "post:service": [lambda step, ctx: None],
             "pre:service": [lambda step, ctx: None],
             "post:package": [lambda step, ctx: None],
         }
         
         steps = [
             Step("service", "nginx", meta={"action": "enable"}),
             Step("package", "vim", meta={"action": "install"}),
         ]
         
         result = _attach_hooks_to_steps(steps, hooks_map)
         
         service_step = [s for s in result if s.kind == "service"][0]
         # Both pre and post hooks should be present, sorted
         assert service_step.meta["hooks"] == ["post:service", "pre:service"]
         
         pkg_step = [s for s in result if s.kind == "package"][0]
         assert pkg_step.meta["hooks"] == ["post:package"]
     
     def test_render_plan_includes_hooks_in_output(self):
         """render_plan formats hooks in output."""
         from kod.planner import Step, render_plan
         
         steps = [
             Step("service", "nginx", meta={"action": "enable", "hooks": ["post:service"]}),
             Step("package", "vim", meta={"action": "install"}),
         ]
         
         output = render_plan(steps, "current", "test.lua")
         
         # Service step should have hooks in output
         assert "nginx" in output
         assert 'hooks=["post:service"]' in output
         
         # Package step should not have hooks
         assert "vim" in output
         assert '"action": "install"' in output
     
     def test_render_plan_skips_empty_hooks_field(self):
         """render_plan doesn't output empty hooks lists."""
         from kod.planner import Step, render_plan
         
         # Step with empty hooks list (shouldn't happen, but verify graceful handling)
         steps = [Step("service", "nginx", meta={"action": "enable", "hooks": []})]
         
         output = render_plan(steps, "current")
         
         # Empty hooks should not appear in output
         lines = output.strip().split("\n")
         service_line = [l for l in lines if "nginx" in l][0]
         assert "hooks=" not in service_line
