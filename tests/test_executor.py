"""Unit tests for Executor class: step dispatch, on_error handling, timeout, hooks."""

import pytest
import time
import concurrent.futures
from kod.executor import Executor, StepError, StepResult
from kod.planner import Step


def test_executor_dispatch_package_install():
    """Package install step dispatches to mock install function."""
    executed = []
    
    def mock_manage_packages(mount_point, repos, action, packages, chroot=False):
        executed.append(("manage", action, packages))
    
    env = {"manage_packages": mock_manage_packages}
    step = Step("package", "vim", meta={"action": "install"})
    executor = Executor(env=env)
    results = executor.execute([step], {})
    
    assert len(results) == 1
    assert results[0].step == step
    assert results[0].success is True
    assert executed == [("manage", "install", ["vim"])]


def test_executor_on_error_abort():
    """on_error='abort' raises StepError on step failure."""
    def mock_fail(mount_point, repos, action, packages, chroot=False):
        raise RuntimeError("mock failure")
    
    env = {"manage_packages": mock_fail}
    step = Step("package", "vim", meta={"action": "install"}, on_error="abort")
    executor = Executor(env=env)
    
    with pytest.raises(StepError) as exc_info:
        executor.execute([step], {})
    
    assert "vim" in str(exc_info.value)


def test_executor_on_error_warn():
    """on_error='warn' logs failure and continues."""
    def mock_fail(mount_point, repos, action, packages, chroot=False):
        raise RuntimeError("mock failure")
    
    env = {"manage_packages": mock_fail}
    step = Step("package", "vim", meta={"action": "install"}, on_error="warn")
    executor = Executor(env=env)
    results = executor.execute([step], {})
    
    assert len(results) == 1
    assert results[0].success is False
    assert "mock failure" in results[0].error


def test_executor_pre_hook_abort():
    """pre:package hook error aborts the step."""
    executed = []
    def mock_hook(step, ctx):
        raise ValueError("hook error")
    
    def mock_manage(mount_point, repos, action, packages, chroot=False):
        executed.append(("manage", action))
    
    env = {"manage_packages": mock_manage}
    hooks = {"pre:package": [mock_hook]}
    step = Step("package", "vim", meta={"action": "install"})
    executor = Executor(env=env)
    
    with pytest.raises(StepError) as exc_info:
        executor.execute([step], {}, hooks=hooks)
    
    assert "hook error" in str(exc_info.value)
    assert executed == []  # manage_packages never called


def test_executor_post_hook_continue():
    """post:package hook error logs and continues; step marked as executed."""
    executed = []
    logs = []
    
    def mock_hook(step, ctx):
        raise ValueError("post hook error")
    
    def mock_manage(mount_point, repos, action, packages, chroot=False):
        executed.append(("manage", action))
    
    env = {"manage_packages": mock_manage}
    hooks = {"post:package": [mock_hook]}
    step = Step("package", "vim", meta={"action": "install"})
    executor = Executor(env=env, logger_fn=logs.append)
    results = executor.execute([step], {}, hooks=hooks)
    
    assert len(results) == 1
    assert results[0].success is True  # Step itself succeeded
    assert executed == [("manage", "install")]
    assert any("post hook error" in log for log in logs)


def test_executor_timeout():
    """Step timeout fires via ThreadPoolExecutor."""
    def mock_slow(mount_point, repos, action, packages, chroot=False):
        time.sleep(2)
    
    env = {"manage_packages": mock_slow}
    step = Step("package", "vim", meta={"action": "install"}, timeout_s=0.1)
    executor = Executor(env=env)
    
    with pytest.raises(StepError) as exc_info:
        executor.execute([step], {})
    
    assert "timed" in str(exc_info.value).lower()


def test_executor_disk_step_rejected():
    """Disk steps raise StepError (not executable yet; deferred to §6 step 2)."""
    step = Step("disk", "wipe:/dev/sda")
    executor = Executor(env={})
    
    with pytest.raises(StepError) as exc_info:
        executor.execute([step], {})
    
    assert "not executable" in str(exc_info.value) or "disk" in str(exc_info.value).lower()


def test_executor_unknown_kind():
    """Unknown step kind raises StepError with clear message."""
    step = Step("unknown_kind", "foo")
    executor = Executor(env={})
    
    with pytest.raises(StepError) as exc_info:
        executor.execute([step], {})
    
    assert "unknown_kind" in str(exc_info.value) or "no executor" in str(exc_info.value).lower()


def test_executor_service_enable():
    """Service enable step dispatches to enable_services."""
    executed = []
    
    def mock_enable(services, mount_point="/", use_chroot=False):
        executed.append(("enable", services))
    
    env = {"enable_services": mock_enable}
    step = Step("service", "nginx", meta={"action": "enable"})
    executor = Executor(env=env)
    results = executor.execute([step], {})
    
    assert executed == [("enable", ["nginx"])]


def test_executor_service_disable():
    """Service disable step dispatches to disable_services."""
    executed = []
    
    def mock_disable(services, mount_point="/", use_chroot=False):
        executed.append(("disable", services))
    
    env = {"disable_services": mock_disable}
    step = Step("service", "nginx", meta={"action": "disable"})
    executor = Executor(env=env)
    results = executor.execute([step], {})
    
    assert executed == [("disable", ["nginx"])]


def test_executor_multiple_steps_sequence():
    """Steps execute in order; later steps can depend on earlier success."""
    executed = []
    
    def mock_manage(mount_point, repos, action, packages, chroot=False):
        executed.append(("pkg", action, packages))
    
    def mock_enable(services, mount_point="/", use_chroot=False):
        executed.append(("svc", services))
    
    env = {"manage_packages": mock_manage, "enable_services": mock_enable}
    steps = [
        Step("package", "base", meta={"action": "install"}),
        Step("package", "nginx", meta={"action": "install"}),
        Step("service", "nginx", meta={"action": "enable"}),
    ]
    executor = Executor(env=env)
    results = executor.execute(steps, {})
    
    assert len(results) == 3
    assert executed == [
        ("pkg", "install", ["base"]),
        ("pkg", "install", ["nginx"]),
        ("svc", ["nginx"]),
    ]
