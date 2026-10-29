"""Local REST API (127.0.0.1 only) + minimal web UI.

Run:  uvicorn chem_agent.api.server:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import os

os.environ.setdefault("CHEM_AGENT_OFFLINE", "1")

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402

from .. import __version__  # noqa: E402
from ..agent import Agent  # noqa: E402
from ..energy import dft, ml_potential  # noqa: E402
from ..parser.validator import ValidationError  # noqa: E402
from ..report.html import HTMLReport  # noqa: E402
from ..report.json_report import to_public  # noqa: E402
from ..utils import offline_guard  # noqa: E402
from .schemas import PredictRequest  # noqa: E402

offline_guard.enable_from_env()
app = FastAPI(title="chem-agent", version=__version__, docs_url="/docs", redoc_url=None)
_agent: Agent | None = None
_store: dict[str, dict] = {}
_MAX_STORE = 200
_LOCAL = {"127.0.0.1", "::1", "localhost", "testclient"}


def agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent


@app.middleware("http")
async def only_local(request: Request, call_next):
    host = request.client.host if request.client else "testclient"
    if host not in _LOCAL:
        return JSONResponse({"detail": "Доступ только с 127.0.0.1"}, status_code=403)
    return await call_next(request)


@app.post("/predict")
def predict(req: PredictRequest):
    try:
        res = agent().predict(request=req.model_dump())
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    d = res.data
    _store[d["reaction_id"]] = d
    while len(_store) > _MAX_STORE:
        _store.pop(next(iter(_store)))
    return to_public(d)


@app.get("/report/{rid}.json")
def report_json(rid: str):
    if rid not in _store:
        raise HTTPException(404, "Нет такого расчета")
    return to_public(_store[rid])


@app.get("/report/{rid}", response_class=HTMLResponse)
def report_html(rid: str, theme: str = "light"):
    if rid.endswith(".json"):
        return report_json(rid[:-5])
    if rid not in _store:
        raise HTTPException(404, "Нет такого расчета")
    return HTMLReport(_store[rid], theme=theme).render()


@app.get("/health")
def health():
    return {"status": "ok", "offline": offline_guard.is_active()}


@app.get("/version")
def version():
    return {"version": __version__}


@app.get("/databases")
def databases():
    return agent().db.summary()


@app.get("/models")
def models():
    return {"ml_potential": ml_potential.status(), "dft": dft.status(),
            "kinetics": ["eyring (барьер пользователя)", "diffusion-limit (Eigen) для H+ + OH-"]}


@app.get("/history")
def history():
    out = []
    for k, v in reversed(list(_store.items())):
        eqs = v.get("balanced_equations") or []
        out.append({
            "reaction_id": k,
            "reagents": [r["formula"] for r in v["input"]["reagents"]],
            "status": v["status"],
            "main_product": (v.get("summary") or {}).get("main_product"),
            "equation": eqs[0]["equation"] if eqs else None,  # <-- добавили
        })
    return out


UI = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>chem-agent</title><style>
body{font:15px system-ui,Segoe UI,Arial;margin:0;background:#f6f7f9;color:#1d2330}
main{max-width:900px;margin:0 auto;padding:16px}textarea,input{width:100%;font:14px Consolas,monospace;box-sizing:border-box}
textarea{height:260px}.row{display:flex;gap:8px;margin:8px 0;flex-wrap:wrap}button{padding:6px 14px}
.card{background:#fff;border:1px solid #dfe3ea;border-radius:10px;padding:14px;margin:12px 0}
li{margin:4px 0}#presets button{margin:3px 4px 3px 0;font-size:13px}</style></head><body><main>
<h1>chem-agent</h1><div class="card"><p>Быстрый ввод (моль): <input id="quick" value="NaOH:0.05, HCl:0.05"></p>
<div class="row"><label>T, K <input id="t" value="298.15" style="width:100px"></label>
<label><input type="checkbox" id="dry"> без растворителя</label>
<button id="go">Рассчитать</button></div>
<p>Или JSON-запрос (схема из README), можно загрузить файл: <input type="file" id="file" accept=".json"></p>
<textarea id="json"></textarea><div class="row"><button id="gojson">Рассчитать JSON</button></div>
<div id="out"></div></div><div class="card"><h3>Готовые примеры</h3><div id="presets"></div></div><div class="card"><h3>История</h3><ul id="hist"></ul></div></main><script>
function show(d){var o=document.getElementById('out');if(d.detail){o.textContent='Ошибка: '+JSON.stringify(d.detail);return}
o.innerHTML='<p><b>'+(d.summary&&d.summary.main_product||d.status)+'</b> - <a href="/report/'+d.reaction_id+'" target="_blank">HTML-отчет</a> · <a href="/report/'+d.reaction_id+'.json" target="_blank">JSON</a></p>';hist()}
function post(body){fetch('/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()).then(show)}
document.getElementById('go').onclick=function(){var r=document.getElementById('quick').value.split(',').map(function(x){var p=x.trim().split(':');return{formula:p[0].trim(),moles:parseFloat((p[1]||'1').replace(',','.'))}});
post({reagents:r,conditions:{temperature_K:parseFloat(document.getElementById('t').value),solvent:document.getElementById('dry').checked?'none':'water'},options:{accuracy:'fast'}})};
document.getElementById('gojson').onclick=function(){try{post(JSON.parse(document.getElementById('json').value))}catch(e){alert('JSON: '+e)}};
document.getElementById('file').onchange=function(e){var f=e.target.files[0];if(!f)return;f.text().then(function(t){document.getElementById('json').value=t})};
function hist(){fetch('/history').then(r=>r.json()).then(function(h){document.getElementById('hist').innerHTML=h.map(function(x){return '<li><a href="/report/'+x.reaction_id+'" target="_blank">'+(x.equation||(x.reagents.join(' + ')+' → '+(x.main_product||x.status)))+'</a></li>'}).join('')})}
var PRESETS=[
  {name:"NaOH + HCl (Eigen)",body:{reagents:[{formula:"NaOH",moles:0.1,phase:"aq"},{formula:"HCl",moles:0.1,phase:"aq"}],options:{output_formats:["html"],include_kinetics:true}}},
  {name:"NH4Cl + NaOH (acid-base)",body:{reagents:[{formula:"NH4Cl",moles:0.05,phase:"aq"},{formula:"NaOH",moles:0.05,phase:"aq"}],options:{output_formats:["html"],include_kinetics:true}}},
  {name:"AgNO3 + NaCl (осадок)",body:{reagents:[{formula:"AgNO3",moles:0.01,phase:"aq"},{formula:"NaCl",moles:0.01,phase:"aq"}],options:{output_formats:["html"],include_kinetics:true}}},
  {name:"Zn + CuSO4 (Eyring 45)",body:{reagents:[{formula:"Zn",moles:0.05,phase:"s"},{formula:"CuSO4",moles:0.05,phase:"aq"}],options:{output_formats:["html"],include_kinetics:true,kinetics:{barrier_kJ_mol:45,uncertainty:3,order:2}}}},
  {name:"N2 + H2 (кат. Fe)",body:{reagents:[{formula:"N2",moles:1.0,phase:"g"},{formula:"H2",moles:3.0,phase:"g"}],conditions:{temperature_K:700,pressure_atm:200,solvent:{name:"none"},catalyst:{formula:"Fe",loading_mol_percent:1.0,barrier_kJ_mol:150,barrier_uncertainty:10}},options:{include_catalysis:true,kinetics:{order:2},output_formats:["html"]}}},
  {name:"CuSO4 + NH3 (избыток)",body:{reagents:[{formula:"CuSO4",moles:0.01,phase:"aq"},{formula:"NH3",moles:0.5,phase:"aq"}],options:{output_formats:["html"]}}},
  {name:"CuSO4 + NH3 (недостаток)",body:{reagents:[{formula:"CuSO4",moles:0.01,phase:"aq"},{formula:"NH3",moles:0.02,phase:"aq"}],options:{output_formats:["html"]}}},
  {name:"BaCl2 + Na2SO4 (осадок)",body:{reagents:[{formula:"BaCl2",moles:0.02,phase:"aq"},{formula:"Na2SO4",moles:0.02,phase:"aq"}],options:{output_formats:["html"]}}},
  {name:"CaCO3 (разложение)",body:{reagents:[{formula:"CaCO3",moles:0.1,phase:"s"}],conditions:{temperature_K:1200,solvent:{name:"none"}},options:{output_formats:["html"]}}}
];
document.getElementById("presets").innerHTML=PRESETS.map(function(p,i){return '<button data-i="'+i+'">'+p.name+'</button>'}).join('');
document.querySelectorAll("#presets button").forEach(function(b){b.onclick=function(){document.getElementById("json").value=JSON.stringify(PRESETS[+b.dataset.i].body,null,2);post(PRESETS[+b.dataset.i].body)}});
hist();</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def ui():
    return UI
