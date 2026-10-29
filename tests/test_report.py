"""Reports: JSON / HTML (single file, no CDN) / Markdown, UTF-8 without BOM, file naming."""
import json
import re

import pytest

from chem_agent.report import HTMLReport, save_all
from chem_agent.utils.encoding import has_bom


@pytest.fixture(scope="module")
def result(agent):
    return agent.predict(reagents=[{"formula": "BaCl2", "moles": 0.02, "phase": "aq"},
                                   {"formula": "Na2SO4", "moles": 0.02, "phase": "aq"}],
                         conditions={"temperature_profile": {"type": "ramp", "start_K": 298.15, "end_K": 340,
                                                             "rate_K_per_min": 5}},
                         options={"accuracy": "fast", "output_formats": ["json", "html", "markdown"]})


def test_json_schema(result):
    d = json.loads(result.to_json())
    for k in ("reaction_id", "input_hash", "balanced_equations", "products", "kinetics", "warnings", "metadata"):
        assert k in d
    eq = d["balanced_equations"][0]
    for k in ("equation", "delta_G_kJ_mol", "delta_G_uncertainty", "delta_H_kJ_mol", "delta_S_J_mol_K",
              "equilibrium_constant", "feasible", "confidence", "energy_sources"):
        assert k in eq
    p = d["products"][0]
    for k in ("formula", "phase", "moles", "mass_g", "delta_Gf_kJ_mol", "uncertainty", "source", "activity",
              "saturation_index"):
        assert k in p
    m = d["metadata"]
    assert m["offline"] is True and m["version"] == "2.5.0" and m["python"]
    assert not any(k.startswith("_") for k in json.dumps(d) and eq)


def test_every_number_has_uncertainty(result):
    d = result.data
    for e in d["balanced_equations"]:
        assert e["delta_G_uncertainty"] is not None
    for p in d["products"]:
        assert p["uncertainty"] is not None
    assert d["uncertainty"]["products"][0]["std"] is not None


def test_html_single_file_no_cdn(result, tmp_path):
    html = HTMLReport(result.data, theme="dark").render()
    assert "<script src=" not in html and "<link rel=\"stylesheet\"" not in html
    assert not re.search(r"https?://(?!www\.w3\.org)", html), "внешние ссылки в отчете"
    for section in ("1. Резюме", "2. Входные данные", "3. Возможные реакции", "4. Продукты", "5. Термодинамика",
                    "6. Кинетика", "7. Неопределенность", "8. Объяснение", "9. Метаданные"):
        assert section in html
    assert 'data-theme="dark"' in html
    assert "<svg class=\"chart\"" in html


def test_save_all_names_and_encoding(result, tmp_path):
    paths = save_all(result, tmp_path)
    assert set(paths) == {"json", "html", "markdown"}
    rid = result.data["reaction_id"]
    for p in paths.values():
        assert re.match(rf"chem-agent_{rid}_[0-9a-f-]+\.(json|html|md)$", p.name)
        assert not has_bom(p)
        p.read_bytes().decode("utf-8")
    md = paths["markdown"].read_text(encoding="utf-8")
    assert "| Формула |" in md and "## 9. Метаданные" in md


def test_save_html_api(result, tmp_path):
    p = result.save_html(tmp_path / "report.html")
    assert p.exists() and p.stat().st_size > 5000
