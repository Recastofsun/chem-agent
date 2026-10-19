import { apiCall } from "./core.js";

export function render(container) {
  container.innerHTML = `
    <h1>Настройки</h1>
    <p>Управление интерфейсом приложения.</p>
    
    <div class="card">
      <h3>Полноэкранный режим</h3>
      <p style="font-size: 13px; color: var(--muted); margin-bottom: 12px;">
        Развернуть приложение на весь экран (скрыть панель задач Windows). 
        Выйти из режима можно повторным нажатием или клавишей <b>Esc</b>.
      </p>
      <button id="btn-fullscreen">Переключить режим</button>
    </div>
  `;

  document.getElementById("btn-fullscreen").onclick = async () => {
    const res = await apiCall("toggle_fullscreen");
    if (res.status === "error") {
      alert("Ошибка: " + res.error.message);
    } else {
      // Запоминаем состояние глобально, чтобы Esc знал, что делать
      window.isAppFullscreen = !window.isAppFullscreen;
    }
  };
}