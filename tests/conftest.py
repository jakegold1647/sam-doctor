import os
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))


def child_env(**overrides: str) -> dict[str, str]:
    """Environment for a subprocess that must import *this* checkout.

    `sys.path.insert` above only fixes in-process imports. A test that shells out
    to `python -m sam_doctor` gets whatever the interpreter finds on its own, and
    on any machine with sam-doctor installed - an editable install from another
    clone, a `pip install sam-doctor` from PyPI - that is a different copy of the
    code. The failure is quiet and backwards: the subprocess tests pass against
    the installed version while the repository is broken, or fail while the
    repository is fine. Both were observed; a stale editable install pointing at
    another clone reported version 0.8.1 to tests asserting 0.11.0.
    """

    env = dict(os.environ, **overrides)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{SOURCE_ROOT}{os.pathsep}{existing}" if existing else str(SOURCE_ROOT)
    )
    return env
