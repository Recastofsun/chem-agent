"""All text files of the project: UTF-8 without BOM; line endings: LF in .py, CRLF in .ps1/.bat."""
from pathlib import Path

import pytest

from chem_agent.utils.encoding import BOM, read_json, write_json

ROOT = Path(__file__).resolve().parent.parent
TEXT = {".py", ".md", ".json", ".yaml", ".yml", ".html", ".css", ".js", ".svg", ".txt", ".toml", ".ps1", ".bat", ".tsv", ".cfg"}
SKIP_DIRS = {".venv", "offline_cache", "__pycache__", ".git", ".pytest_cache", "build", "dist"}


def _files():
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in TEXT and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS):
            yield p


def test_no_bom_valid_utf8():
    bad = []
    for p in _files():
        data = p.read_bytes()
        if data.startswith(BOM):
            bad.append(f"BOM: {p}")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            bad.append(f"not utf-8: {p}")
    assert not bad, bad


def test_line_endings():
    bad = []
    for p in _files():
        data = p.read_bytes()
        if p.suffix.lower() in (".ps1", ".bat"):
            if b"\n" in data.replace(b"\r\n", b""):
                bad.append(f"LF in {p}")
        elif p.suffix.lower() == ".py" and b"\r\n" in data:
            bad.append(f"CRLF in {p}")
    assert not bad, bad


def test_bat_first_lines():
    for p in ROOT.glob("*.bat"):
        lines = p.read_text(encoding="utf-8").splitlines()
        assert lines[0].strip().lower() == "@echo off", p
        assert lines[1].strip().lower().startswith("chcp 65001"), p


def test_ps1_headers():
    for p in ROOT.glob("*.ps1"):
        text = p.read_text(encoding="utf-8")
        assert text.startswith("#Requires"), p
        if p.name != "enable_long_paths.ps1":
            assert '$ErrorActionPreference = "Stop"' in text, p


def test_reads_bom_input(tmp_path):
    f = tmp_path / "in.json"
    f.write_bytes(BOM + '{"формула": "NaCl"}'.encode("utf-8"))
    assert read_json(f) == {"формула": "NaCl"}


def test_writes_without_bom(tmp_path):
    f = write_json(tmp_path / "out.json", {"ключ": "значение"})
    assert not f.read_bytes().startswith(BOM)


@pytest.mark.parametrize("name", ["reactions.json"])
def test_fixture_encoding(name):
    p = ROOT / "tests" / "fixtures" / name
    assert not p.read_bytes().startswith(BOM)
