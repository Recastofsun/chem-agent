import { apiCall } from "./core.js";

export async function render(container) {
  container.innerHTML = `
    <h1>Таблица Менделеева</h1>
    <p>Нажмите на элемент, чтобы увидеть список соединений в базе.</p>
    
    <div class="ptable-wrapper">
      <div class="ptable" id="ptable-grid"></div>
    </div>
    
    <div id="element-details" class="element-details" style="display: none;">
      <!-- Сюда выводится инфа об элементе -->
    </div>
  `;

  const grid = document.getElementById("ptable-grid");
  const detailsPanel = document.getElementById("element-details");

  try {
    const response = await fetch("./assets/elements.json");
    const elements = await response.json();

    elements.forEach(el => {
      const cell = document.createElement("div");
      cell.className = `ptable-cell cat-${el.cat}`;
      cell.style.gridColumn = el.x;
      cell.style.gridRow = el.y;
      cell.dataset.sym = el.sym;
      
      cell.innerHTML = `
        <div class="num">${el.z}</div>
        <div class="sym">${el.sym}</div>
        <div class="name">${el.name}</div>
        <div class="mass">${el.mass}</div>
      `;
      
      cell.onclick = () => loadElementDetails(el, cell);
      grid.appendChild(cell);
    });
  } catch (e) {
    grid.innerHTML = `<p style="color: var(--err)">Ошибка загрузки таблицы: ${e.message}</p>`;
  }

  async function loadElementDetails(el, cell) {
    // Подсветка
    document.querySelectorAll(".ptable-cell").forEach(c => c.classList.remove("active"));
    cell.classList.add("active");

    detailsPanel.style.display = "block";
    detailsPanel.innerHTML = `<h2>${el.name} (${el.sym}) <span>Атомная масса: ${el.mass}</span></h2>
                              <p>Загрузка соединений из базы...</p>`;

    const res = await apiCall("get_element_compounds", el.sym);

    if (res.status === "error") {
      detailsPanel.innerHTML = `<h2>${el.name} (${el.sym})</h2><p style="color: var(--err)">Ошибка: ${res.error.message}</p>`;
      return;
    }

    const compounds = res.data;
    if (compounds.length === 0) {
      detailsPanel.innerHTML = `<h2>${el.name} (${el.sym})</h2><p style="color: var(--muted)">В базе нет соединений с этим элементом.</p>`;
      return;
    }

    let tableHtml = `
      <h2>${el.name} (${el.sym}) <span>Атомная масса: ${el.mass} &middot; Найдено веществ: ${compounds.length}</span></h2>
      <div class="table-wrap">
        <table class="sortable">
          <thead>
            <tr>
              <th>Формула</th>
              <th>Фаза</th>
              <th>Название</th>
              <th class="n">ΔfG° (кДж/моль)</th>
              <th class="n">ΔfH° (кДж/моль)</th>
              <th>Действие</th>
            </tr>
          </thead>
          <tbody>
    `;

    compounds.forEach(c => {
      tableHtml += `
        <tr>
          <td class="eqcell"><b>${c.formula}</b></td>
          <td>${c.phase_ru}</td>
          <td>${c.name_ru}</td>
          <td class="n">${c.dGf !== null ? c.dGf.toFixed(1) : "—"}</td>
          <td class="n">${c.dHf !== null ? c.dHf.toFixed(1) : "—"}</td>
          <td><button class="secondary btn-add-reag" data-formula="${c.formula}" style="padding: 2px 8px; font-size: 12px;">➕ В Конструктор</button></td>
        </tr>
      `;
    });

    tableHtml += `</tbody></table></div>`;
    detailsPanel.innerHTML = tableHtml;

    // Обработчик для кнопок "В Конструктор"
   document.querySelectorAll(".btn-add-reag").forEach(btn => {
      btn.onclick = () => {
        // Читаем текущее состояние Конструктора
        const stateStr = localStorage.getItem("constructor_reagents");
        let state = stateStr ? JSON.parse(stateStr) : [];
        
        // Добавляем новое вещество в конец массива
        state.push({ formula: btn.dataset.formula, moles: 1.0 });
        
        // Сохраняем обратно
        localStorage.setItem("constructor_reagents", JSON.stringify(state));
        
        // Переключаем экран
        window.location.hash = "#constructor";
      };
    });
  } 
} 