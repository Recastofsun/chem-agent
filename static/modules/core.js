export function waitForApi(timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    const t0 = Date.now();
    (function check() {
      if (window.pywebview && window.pywebview.api) return resolve(window.pywebview.api);
      if (Date.now() - t0 > timeoutMs) return reject(new Error("pywebview API недоступен"));
      setTimeout(check, 50);
    })();
  });
}

export async function apiCall(method, ...args) {
  try {
    const api = await waitForApi();
    return await api[method](...args);
  } catch (e) {
    return { status: "error", data: null, error: { code: "TRANSPORT_ERROR", message: String(e) } };
  }
}