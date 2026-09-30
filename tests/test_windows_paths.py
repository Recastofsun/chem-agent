"""Paths with Cyrillic, spaces and > 260 characters (Windows long paths via \\\\?\\ prefix)."""
import sys

from chem_agent.report import save_all
from chem_agent.utils.encoding import read_text, write_text
from chem_agent.utils.paths import long_path, user_data_dir


def test_cyrillic_and_spaces(agent, tmp_path):
    out = tmp_path / "Отчеты химия" / "папка с пробелами"
    r = agent.predict(reagents=[{"formula": "NaOH", "moles": 0.01, "phase": "aq"}, {"formula": "HCl", "moles": 0.01, "phase": "aq"}],
                      options={"accuracy": "fast", "output_formats": ["json", "html", "markdown"]})
    paths = save_all(r, out)
    for p in paths.values():
        assert p.exists()
        assert "Отчеты химия" in str(p)


def test_long_path(tmp_path):
    deep = tmp_path
    while len(str(deep)) < 300:
        deep = deep / ("очень_длинная_папка_" + "x" * 20)
    f = deep / "файл отчета.json"
    write_text(f, '{"ok": true}')
    assert read_text(f) == '{"ok": true}'
    assert len(str(f)) > 260


def test_long_path_prefix_on_windows(tmp_path):
    p = tmp_path / ("a" * 250) / "b.txt"
    lp = long_path(p)
    if sys.platform.startswith("win"):
        assert str(lp).startswith("\\\\?\\")
    else:
        assert lp == p


def test_user_data_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("CHEM_AGENT_HOME", str(tmp_path / "дом"))
    assert user_data_dir() == tmp_path / "дом"


def test_localappdata_on_windows(monkeypatch, tmp_path):
    monkeypatch.delenv("CHEM_AGENT_HOME", raising=False)
    if sys.platform.startswith("win"):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        assert user_data_dir() == tmp_path / "chem-agent"
