(function () {
  "use strict";

  const statusEl = document.getElementById("status");
  const outputEl = document.getElementById("output");
  const verEl = document.getElementById("ver");

  const setOutput = (o) => { outputEl.textContent = JSON.stringify(o, null, 2); };
  const setStatus = (state, text) => {
    statusEl.dataset.state = state;
    statusEl.textContent = text;
  };

  function waitForApi(timeoutMs = 5000) {
    return new Promise((resolve, reject) => {
      const t0 = Date.now();
      (function check() {
        if (window.pywebview && window.pywebview.api) return resolve(window.pywebview.api);
        if (Date.now() - t0 > timeoutMs) return reject(new Error("pywebview API недоступен"));
        setTimeout(check, 50);
      })();
    });
  }

  async function call(method, ...args) {
    try {
      const api = await waitForApi();
      const res = await api[method](...args);
      setOutput(res);
      if (res && res.status === "ok") setStatus("ok", "связь с Python: OK");
      else setStatus("error", "ошибка: " + (res?.error?.code ?? "?"));
      return res;
    } catch (e) {
      setOutput({ transport_error: String(e) });
      setStatus("error", "транспортная ошибка");
    }
  }

  document.getElementById("btn-ping").addEventListener("click", () => call("ping"));
  document.getElementById("btn-version").addEventListener("click", () => call("get_version"));
  document.getElementById("btn-broken").addEventListener("click", () => call("predict", ["HCl", "NaOH"]));

  window.addEventListener("pywebviewready", async () => {
    setStatus("ok", "pywebview готов");
    const res = await call("get_version");
    if (res?.status === "ok") verEl.textContent = "v" + res.data.version;
  });
})();