import { apiCall } from "./core.js";
import { show as show3D } from "./viewer3d.js";

export function render(container) {
  container.innerHTML = `
    <h1>История расчетов</h1>
    <p>Здесь сохраняются все ваши реакции. Нажмите на уравнение, чтобы посмотреть детали.</p>
    
    <div class="row" style="margin-bottom: 20px;">
      <button id="btn-refresh" class="secondary">Обновить</button>
      <button id="btn-clear" class="secondary" style="color: var(--err); border-color: var(--err);">Очистить историю</button>
    </div>

    <div id="history-list" class="card">
      <p style="color: var(--muted);">Загрузка...</p>
    </div>

    <!-- Модальное окно для деталей -->
    <div id="detail-modal" class="modal" style="display: none;">
      <div class="modal-content">
        <span class="close-btn" id="btn-close-modal">&times;</span>
        <h2>Детали реакции</h2>
        <div id="modal-body" style="margin-top: 16px;"></div>
      </div>
    </div>
  `;

  const listEl = document.getElementById("history-list");
  const modal = document.getElementById("detail-modal");
  const modalBody = document.getElementById("modal-body");

  async function loadHistory() {
    listEl.innerHTML = '<p style="color: var(--muted);">Загрузка...</p>';
    const res = await apiCall("get_history", 50);
    
    if (res.status === "error") {
      listEl.innerHTML = `<p style="color: var(--err);">Ошибка: ${res.error.message}</p>`;
      return;
    }

    const items = res.data;
    if (!items || items.length === 0) {
      listEl.innerHTML = '<p style="color: var(--muted);">История пуста. Сделайте первый расчет в Конструкторе.</p>';
      return;
    }

    let html = '<ul style="list-style: none; padding: 0;">';
    items.forEach(item => {
      const date = new Date(item.timestamp * 1000).toLocaleString();
      const eqText = item.equation || (item.reagents.join(" + ") + " → " + (item.main_product || item.status));
      html += `
        <li style="border-bottom: 1px solid var(--border); padding: 12px 0; display: flex; justify-content: space-between; align-items: center;">
          <div>
            <div style="font-family: monospace; font-size: 15px; margin-bottom: 4px; cursor: pointer; color: var(--accent);" class="eq-link" data-id="${item.reaction_id}">${eqText}</div>
            <div style="font-size: 12px; color: var(--muted);">${date} &middot; Статус: ${item.status}</div>
          </div>
          <button class="secondary btn-del" data-id="${item.reaction_id}" style="padding: 4px 8px; font-size: 12px;">Удалить</button>
        </li>
      `;
    });
    html += '</ul>';
    listEl.innerHTML = html;

    // Обработчики кликов
    document.querySelectorAll(".eq-link").forEach(el => {
      el.onclick = () => showDetails(el.dataset.id);
    });
    document.querySelectorAll(".btn-del").forEach(el => {
      el.onclick = async () => {
        if(confirm("Удалить эту запись?")) {
          await apiCall("delete_history_entry", el.dataset.id);
          loadHistory();
        }
      };
    });
  }

 async function showDetails(id) {
    modalBody.innerHTML = '<p>Загрузка...</p>';
    modal.style.display = "flex";
    const res = await apiCall("get_history_entry", id);
    if (res.status === "error") {
      modalBody.innerHTML = `<p style="color: var(--err);">${res.error.message}</p>`;
      return;
    }
    
    const data = res.data;
    const eq = data.balanced_equations?.[0];
    const mainProduct = data.summary?.main_product;

    let formulasToShow = [];
    if (data.products && data.products.length > 0) {
        // Берем только уникальные формулы
        formulasToShow = [...new Set(data.products.map(p => p.formula))];
    }
    
    // Кнопка 3D
    let btn3dHtml = "";
    if (formulasToShow.length > 0) {
      btn3dHtml = `<button id="btn-show-3d" style="margin-bottom: 16px;">👁 Показать 3D-структуру (${formulasToShow.join(" + ")})</button>
                   <div id="3d-container" style="margin-bottom: 16px; display: none;"></div>`;
    }

    modalBody.innerHTML = `
      ${btn3dHtml}
      <pre class="output">${JSON.stringify(data, null, 2)}</pre>
    `;

    if (formulasToShow.length > 0) {
      document.getElementById("btn-show-3d").onclick = () => {
        const c = document.getElementById("3d-container");
        c.style.display = "block";
        show3D(c, formulasToShow); // Передаем массив формул
        document.getElementById("btn-show-3d").style.display = "none";
      };
    }
  }

  document.getElementById("btn-refresh").onclick = loadHistory;
  document.getElementById("btn-clear").onclick = async () => {
    if(confirm("Вы уверены, что хотите удалить всю историю?")) {
      await apiCall("clear_history");
      loadHistory();
    }
  };
  document.getElementById("btn-close-modal").onclick = () => modal.style.display = "none";
  
  // Закрытие по клику на фон (вне модального окна)
  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.style.display = "none";
    }
  });

  // Закрытие по нажатию клавиши Escape (бонус для удобства)
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.style.display === "flex") {
      modal.style.display = "none";
    }
  });

  loadHistory();
}