import { waitForApi, apiCall } from "./modules/core.js";
import * as Constructor from "./modules/constructor.js";
import * as Sandbox from "./modules/sandbox.js";
import * as History from "./modules/history.js"; 
import * as Periodic from "./modules/periodic.js"; 
import * as Settings from "./modules/settings.js";

const routes = {
  constructor: Constructor,
  periodic: Periodic, 
  history: History,
  sandbox: Sandbox,
  settings: Settings
};

const container = document.getElementById("view-container");
const statusEl = document.getElementById("status");

function router() {
  const hash = window.location.hash.replace("#", "") || "constructor";
  const module = routes[hash] || routes.constructor;
  
  // Подсветка меню
  document.querySelectorAll(".nav-link").forEach(link => {
    link.classList.toggle("active", link.dataset.target === hash);
  });

  module.render(container);
}

window.addEventListener("hashchange", router);

window.addEventListener("pywebviewready", () => {
  statusEl.dataset.state = "ok";
  statusEl.textContent = "Python: OK";
  router();
});

window.addEventListener("keydown", async (e) => {
  if (e.key === "Escape" || e.code === "Escape") {
    await apiCall("exit_fullscreen");
  }
}, true);