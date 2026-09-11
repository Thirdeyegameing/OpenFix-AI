from pathlib import Path

from openfix.config import APP_VERSION, RELEASE_CHANNEL


def test_release_version_is_stable_1_0():
    assert APP_VERSION == "1.0.0"
    assert RELEASE_CHANNEL == "stable"


def test_readme_declares_v1():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "v1.0.0" in readme
    assert "No Cloud AI" in readme
    assert "read-only" in readme.lower()


def test_license_is_present():
    root = Path(__file__).resolve().parents[1]
    assert (root / "LICENSE").exists()


def test_version_file_matches_runtime():
    root = Path(__file__).resolve().parents[1]
    assert (root / "VERSION").read_text(encoding="utf-8").strip() == APP_VERSION
