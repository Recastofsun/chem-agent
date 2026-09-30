"""Single-file HTML report: Jinja2 templates, inline CSS/JS/SVG, no CDN."""
from __future__ import annotations

import base64
import html as _html
import webbrowser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..utils.encoding import write_text
from ..utils.paths import STATIC_DIR, TEMPLATES_DIR
from . import charts
from .fmt import chem, num, pct, pm
from .json_report import dumps


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig")


class HTMLReport:
    def __init__(self, result: dict, theme: str = "light", language: str = "ru"):
        self.result = result.data if hasattr(result, "data") else result
        self.theme = theme if theme in ("light", "dark") else "light"
        self.language = language
        self.env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)),
                               autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
        self.env.filters.update(num=num, pm=pm, pct=pct, chem=chem)

    def _charts(self) -> dict:
        d = self.result
        out = {}
        th = d.get("thermo") or {}
        if th.get("dG_T"):
            xs = [p["T_K"] for p in th["dG_T"]]
            out["dG_T"] = charts.line_chart(
                [{"name": "ΔG", "x": xs, "y": [p["delta_G_kJ_mol"] for p in th["dG_T"]]}],
                "T, K", "ΔG реакции, кДж/моль",
                band={"x": xs, "lo": [p["delta_G_kJ_mol"] - p["sigma"] for p in th["dG_T"]],
                      "hi": [p["delta_G_kJ_mol"] + p["sigma"] for p in th["dG_T"]]}, chart_id="ch-dg")
            out["K_T"] = charts.line_chart(
                [{"name": "lg K", "x": xs, "y": [p["log10_K"] for p in th["dG_T"]]}],
                "T, K", "lg K", chart_id="ch-k")
        if th.get("profile"):
            names = []
            for p in th["profile"]:
                for k in (p.get("products") or {}):
                    if k not in names:
                        names.append(k)
            series = [{"name": n, "x": [p["T_K"] for p in th["profile"]],
                       "y": [(p.get("products") or {}).get(n, 0.0) for p in th["profile"]]} for n in names[:6]]
            out["profile"] = charts.line_chart(series, "T, K", "количество, моль", chart_id="ch-prof")
        k = d.get("kinetics") or {}
        if k.get("profile"):
            pr = k["profile"]
            ts = [t for t in pr["t_s"] if t > 0]
            ys = [x for t, x in zip(pr["t_s"], pr["extent_M"]) if t > 0]
            out["kinetics"] = charts.line_chart([{"name": "степень превращения", "x": ts, "y": ys}],
                                                "время, с (лог. шкала)", "прореагировало, моль/л",
                                                log_x=True, chart_id="ch-kin")
        u = d.get("uncertainty") or {}
        if u.get("contributions"):
            out["contrib"] = charts.bar_chart([(c["species"], c["share"]) for c in u["contributions"]],
                                              "вклад в дисперсию ΔG", chart_id="ch-contrib")
        return out

    def render(self) -> str:
        d = self.result
        logo = STATIC_DIR / "logo.svg"
        ctx = {
            "d": d, "s": d.get("summary") or {}, "theme": self.theme, "charts": self._charts(),
            "css": _read(STATIC_DIR / "style.css"), "js": _read(STATIC_DIR / "script.js"),
            "logo_uri": "data:image/svg+xml;base64," + base64.b64encode(logo.read_bytes()).decode() if logo.exists() else "",
            "json_blob": dumps(d).replace("<", "\\u003c"),
            "title": "Отчет: " + " + ".join(chem(r["formula"]) for r in d["input"]["reagents"]),
        }
        return self.env.get_template("report.html").render(**ctx)

    def save(self, path: Path) -> Path:
        return write_text(Path(path), self.render())

    @staticmethod
    def open(path: Path) -> None:
        webbrowser.open(Path(path).resolve().as_uri())
