import importlib.util
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def _load_module(root: Path):
    script_path = root / "scripts" / "generate-share-snippets.py"
    spec = importlib.util.spec_from_file_location(
        "generate_share_snippets",
        str(script_path),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load generate-share-snippets.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generate_share_snippet_defaults() -> None:
    # Use repo root to mimic real path resolution.
    module = _load_module(Path(__file__).resolve().parents[1])
    text = module.generate_snippet(
        error="oidc",
        channel="x",
        include_link=True,
        include_command=True,
        utm_medium="chat",
    )
    assert "OIDC / AssumeRoleWithWebIdentity" in text
    assert "For X / Twitter:" in text
    assert "utm_source=share_script" in text


def test_generate_share_snippet_without_command_or_link() -> None:
    module = _load_module(Path(__file__).resolve().parents[1])
    text = module.generate_snippet(
        error="build",
        channel="chat",
        include_link=False,
        include_command=False,
        utm_medium="chat",
    )
    assert "Top finding + safe verification check." in text
    assert "utm_source=share_script" not in text


def test_main_writes_output_file(tmp_path: Path) -> None:
    module = _load_module(Path(__file__).resolve().parents[1])
    out_file = tmp_path / "snippet.txt"
    ret = module.main(
        [
            "--error",
            "rollback",
            "--channel",
            "discord",
            "--out",
            str(out_file),
            "--no-link",
            "--utm-medium",
            "discord",
        ]
    )
    assert ret == 0
    assert out_file.exists()
    assert "I posted this in Discord:" in out_file.read_text(encoding="utf-8")
    assert "utm_source=share_script" not in out_file.read_text(encoding="utf-8")


def test_main_rejects_unknown_error() -> None:
    module = _load_module(Path(__file__).resolve().parents[1])
    try:
        module.main(["--error", "does-not-exist"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("Expected argparse to exit with code 2 for invalid error option")


def test_snippet_links_have_real_queries_and_valid_fragments() -> None:
    module = _load_module(Path(__file__).resolve().parents[1])
    root = Path(__file__).resolve().parents[1]
    homepage = (root / "site" / "index.html").read_text(encoding="utf-8")

    for error in module.ERROR_TEMPLATES:
        text = module.generate_snippet(
            error=error,
            channel="chat",
            include_link=True,
            include_command=True,
            utm_medium="x / launch",
        )
        link = next(
            line for line in text.splitlines() if line.startswith(module.BASE_URL)
        )
        parsed = urlsplit(link)

        assert parsed.scheme == "https"
        assert parsed.netloc == "sam-doctor.jacobgoldstein.dev"
        assert parsed.path == "/"
        assert parse_qs(parsed.query) == {
            "utm_source": ["share_script"],
            "utm_medium": ["x / launch"],
        }

        expected_fragment = (
            "proof-title" if error in {"ecr", "build", "rollback"} else ""
        )
        assert parsed.fragment == expected_fragment
        if expected_fragment:
            assert f'id="{expected_fragment}"' in homepage
