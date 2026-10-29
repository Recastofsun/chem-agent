"""Self-contained inline SVG charts (no CDN, no external JS).

Colours come from CSS variables of the report theme, so charts follow light/dark themes.
Each point carries a <title> tooltip; the report JS adds click-to-zoom.
"""
from __future__ import annotations

import html
import math

W, H = 640, 300
ML, MR, MT, MB = 64, 16, 16, 44
SERIES = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)", "var(--s6)"]


def _fmt(v: float) -> str:
    if v == 0:
        return "0"
    a = abs(v)
    if a >= 1e4 or a < 1e-2:
        m, e = f"{v:.1e}".split("e")
        return f"{m.replace('.', ',')}e{int(e)}"
    s = f"{v:.3g}"
    return s.replace(".", ",")


def _ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=mag * 10)
    start = math.ceil(lo / step) * step
    out, x = [], start
    while x <= hi + 1e-9 * step:
        out.append(round(x, 12))
        x += step
    return out


def line_chart(series: list[dict], x_label: str, y_label: str, log_x: bool = False, log_y: bool = False,
               band: dict | None = None, chart_id: str = "c") -> str:
    """series: [{name, x: [...], y: [...]}]; band: {x, lo, hi} shaded uncertainty band."""
    pts = [(x, y) for s in series for x, y in zip(s["x"], s["y"]) if y is not None]
    if not pts:
        return '<p class="muted">Нет данных для графика</p>'

    def tx(v):
        return math.log10(v) if log_x else v

    def ty(v):
        return math.log10(v) if log_y else v

    xs = [tx(x) for x, _ in pts if (x > 0 or not log_x)]
    ys = [ty(y) for _, y in pts if (y > 0 or not log_y)]
    if band:
        ys += [ty(v) for v in band["lo"] + band["hi"] if v is not None and (v > 0 or not log_y)]
    if not xs or not ys:
        return '<p class="muted">Нет данных для графика</p>'
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if x1 == x0:
        x0, x1 = x0 - 1, x1 + 1
    if y1 == y0:
        pad = abs(y0) * 0.1 or 1.0
        y0, y1 = y0 - pad, y1 + pad
    pad = (y1 - y0) * 0.06
    y0, y1 = y0 - pad, y1 + pad

    def px(v):
        return ML + (tx(v) - x0) / (x1 - x0) * (W - ML - MR)

    def py(v):
        return MT + (1 - (ty(v) - y0) / (y1 - y0)) * (H - MT - MB)

    out = [f'<svg class="chart" id="{chart_id}" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="{html.escape(y_label)} от {html.escape(x_label)}">']
    for t in _ticks(y0, y1):
        yy = MT + (1 - (t - y0) / (y1 - y0)) * (H - MT - MB)
        lab = _fmt(10 ** t) if log_y else _fmt(t)
        out.append(f'<line class="grid" x1="{ML}" x2="{W - MR}" y1="{yy:.1f}" y2="{yy:.1f}"/>'
                   f'<text class="tick" x="{ML - 6}" y="{yy + 4:.1f}" text-anchor="end">{lab}</text>')
    for t in _ticks(x0, x1, 6):
        xx = ML + (t - x0) / (x1 - x0) * (W - ML - MR)
        lab = _fmt(10 ** t) if log_x else _fmt(t)
        out.append(f'<text class="tick" x="{xx:.1f}" y="{H - MB + 16}" text-anchor="middle">{lab}</text>')
    out.append(f'<line class="axis" x1="{ML}" x2="{W - MR}" y1="{H - MB}" y2="{H - MB}"/>')
    out.append(f'<text class="axlabel" x="{(ML + W - MR) / 2:.0f}" y="{H - 6}" text-anchor="middle">'
               f'{html.escape(x_label)}</text>')
    out.append(f'<text class="axlabel" transform="translate(14,{(MT + H - MB) / 2:.0f}) rotate(-90)" '
               f'text-anchor="middle">{html.escape(y_label)}</text>')
    if band:
        up = [(px(x), py(v)) for x, v in zip(band["x"], band["hi"]) if v is not None]
        dn = [(px(x), py(v)) for x, v in zip(band["x"], band["lo"]) if v is not None]
        if up and dn:
            poly = " ".join(f"{a:.1f},{b:.1f}" for a, b in up + dn[::-1])
            out.append(f'<polygon class="band" points="{poly}"/>')
    for k, s in enumerate(series):
        col = SERIES[k % len(SERIES)]
        p = [(px(x), py(y), x, y) for x, y in zip(s["x"], s["y"])
             if y is not None and (y > 0 or not log_y) and (x > 0 or not log_x)]
        if not p:
            continue
        d = " ".join(("M" if i == 0 else "L") + f"{a:.1f},{b:.1f}" for i, (a, b, _, _) in enumerate(p))
        out.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2"/>')
        for a, b, x, y in p:
            out.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="3" fill="{col}"><title>'
                       f'{html.escape(s["name"])}: {_fmt(x)} → {_fmt(y)}</title></circle>')
    out.append("</svg>")
    if len(series) > 1:
        leg = "".join(f'<span class="lg"><i style="background:{SERIES[k % len(SERIES)]}"></i>'
                      f'{html.escape(s["name"])}</span>' for k, s in enumerate(series))
        out.append(f'<div class="legend">{leg}</div>')
    return "\n".join(out)


def bar_chart(items: list[tuple[str, float]], x_label: str, chart_id: str = "b") -> str:
    """Horizontal bars (e.g. uncertainty contributions, shares 0..1)."""
    if not items:
        return '<p class="muted">Нет данных для графика</p>'
    h = 26 * len(items) + 30
    mx = max(v for _, v in items) or 1.0
    out = [f'<svg class="chart" id="{chart_id}" viewBox="0 0 {W} {h}" role="img" aria-label="{html.escape(x_label)}">']
    for i, (name, v) in enumerate(items):
        y = 10 + i * 26
        w = (W - 220) * v / mx
        out.append(f'<text class="tick" x="190" y="{y + 15}" text-anchor="end">{html.escape(name)}</text>'
                   f'<rect x="200" y="{y}" width="{w:.1f}" height="18" rx="3" fill="var(--s1)">'
                   f'<title>{html.escape(name)}: {_fmt(v * 100)} %</title></rect>'
                   f'<text class="tick" x="{204 + w:.1f}" y="{y + 14}">{_fmt(v * 100)} %</text>')
    out.append("</svg>")
    return "\n".join(out)
