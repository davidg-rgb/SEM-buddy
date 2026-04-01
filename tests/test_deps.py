"""Verify unused dependencies are not present (INF-08)."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def test_pyproject_no_spacy():
    content = (PROJECT_ROOT / "pyproject.toml").read_text()
    assert "spacy" not in content.lower(), "spacy should not be in pyproject.toml"


def test_pyproject_no_pyenchant():
    content = (PROJECT_ROOT / "pyproject.toml").read_text()
    assert "pyenchant" not in content.lower(), "pyenchant should not be in pyproject.toml"


def test_requirements_no_spacy():
    content = (PROJECT_ROOT / "requirements.txt").read_text()
    assert "spacy" not in content.lower(), "spacy should not be in requirements.txt"


def test_requirements_no_pyenchant():
    content = (PROJECT_ROOT / "requirements.txt").read_text()
    assert "pyenchant" not in content.lower(), "pyenchant should not be in requirements.txt"
