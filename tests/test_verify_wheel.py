import importlib.util
import os
import subprocess
import sys
from pathlib import Path


def _load_verify_wheel_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "verify-wheel.py"
    spec = importlib.util.spec_from_file_location("verify_wheel_script", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load wheel verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_wheel_commands_do_not_inherit_source_path_overrides(monkeypatch) -> None:
    module = _load_verify_wheel_script()
    monkeypatch.setenv("PYTHONPATH", "source-tree-leak")
    monkeypatch.setenv("PYTHONHOME", "wrong-interpreter")
    monkeypatch.setenv("SAM_DOCTOR_VERIFY_SENTINEL", "kept")
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module._run([sys.executable, "--version"], title="isolated command")

    environment = captured["env"]
    assert isinstance(environment, dict)
    assert "PYTHONPATH" not in environment
    assert "PYTHONHOME" not in environment
    assert environment["SAM_DOCTOR_VERIFY_SENTINEL"] == "kept"
    assert os.environ["PYTHONPATH"] == "source-tree-leak"
