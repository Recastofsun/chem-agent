import { apiCall } from "./core.js";

export function render(container) {
  container.innerHTML = `
    <h1>Sandbox</h1>
    <p>Проверка базовых методов Bridge.</p>
    <div class="row">
      <button id="btn-ping">Ping</button>
      <button id="btn-version">Версия</button>
      <button id="btn-broken">Вызвать ошибку</button>
    </div>
    <pre id="output" class="output">—</pre>
  `;
  
  const out = document.getElementById("output");
  
  const call = async (method, ...args) => {
    out.textContent = "Загрузка...";
    const res = await apiCall(method, ...args);
    out.textContent = JSON.stringify(res, null, 2);
  };

  document.getElementById("btn-ping").onclick = () => call("ping");
  document.getElementById("btn-version").onclick = () => call("get_version");
  document.getElementById("btn-broken").onclick = () => call("predict", { reagents: [], conditions: {} });
}