import { apiCall } from "./core.js";

export function render(container) {
  container.innerHTML = `
    <h1>Конструктор реакций</h1>
    <p>Введите реагенты и условия. Ядро рассчитает продукты методом минимизации энергии Гиббса.</p>
    
    <div class="card">
      <div style="margin-bottom: 12px;">
      <button id="btn-load-preset" class="secondary" style="width: 100%; border-style: dashed;">📚 Выбрать из готовых пресетов</button></div>
      <div id="reagents-list"></div>
      <button id="btn-add-reagent" class="secondary" style="margin-top: 10px;">+ Добавить реагент</button>
      
      <div class="row" style="margin-top: 20px;">
        <div class="form-group">
          <label>Температура (K)</label>
          <input type="number" id="cond-t" value="298.15" step="1">
        </div>
        <div class="form-group">
          <label>Давление (атм)</label>
          <input type="number" id="cond-p" value="1.0" step="0.1">
        </div>
        <div class="form-group">
          <label>Объем (л)</label>
          <input type="number" id="cond-v" value="1.0" step="0.1">
        </div>
      </div>

      <button id="btn-predict" style="margin-top: 20px; width: 100%;">Рассчитать реакцию</button>
    </div>

    <div id="result-area" style="display: none;">
      <h2>Результат</h2>
      <div class="card">
        <div id="res-equation" style="font-size: 18px; font-family: monospace; margin-bottom: 16px; color: var(--accent);"></div>
        <div class="row">
          <div><span style="color: var(--muted);">ΔG:</span> <span id="res-dg"></span> кДж/моль</div>
          <div><span style="color: var(--muted);">Статус:</span> <span id="res-status"></span></div>
        </div>
      </div>
      <details>
        <summary style="cursor: pointer; color: var(--muted);">Показать сырой JSON (Data)</summary>
        <pre id="res-json" class="output" style="margin-top: 10px;"></pre>
      </details>
    </div>
  `;

  const list = document.getElementById("reagents-list");

  // Функция сохранения текущего состояния в localStorage
  const saveState = () => {
    const reagents = Array.from(document.querySelectorAll(".reagent-row")).map(row => ({
      formula: row.querySelector(".reag-formula").value.trim(),
      moles: parseFloat(row.querySelector(".reag-moles").value)
    }));
    localStorage.setItem("constructor_reagents", JSON.stringify(reagents));
  };

  const addReagentRow = (formula = "", moles = 1.0) => {
    const row = document.createElement("div");
    row.className = "row reagent-row";
    row.innerHTML = `
      <div class="form-group" style="flex: 2">
        <label>Формула</label>
        <input type="text" class="reag-formula" value="${formula}" placeholder="например, NaOH">
      </div>
      <div class="form-group">
        <label>Моли</label>
        <input type="number" class="reag-moles" value="${moles}" step="0.1">
      </div>
      <button class="secondary btn-remove" style="margin-bottom: 2px;">✕</button>
    `;
    
    // Сохраняем стейт при любом изменении в полях
    row.querySelector(".reag-formula").addEventListener("input", saveState);
    row.querySelector(".reag-moles").addEventListener("input", saveState);
    
    row.querySelector(".btn-remove").onclick = () => {
      row.remove();
      saveState(); // Сохраняем после удаления
    };
    
    list.appendChild(row);
  };

  // Восстанавливаем состояние при загрузке
  const savedState = localStorage.getItem("constructor_reagents");
  if (savedState) {
    try {
      const reagents = JSON.parse(savedState);
      if (reagents.length > 0) {
        reagents.forEach(r => addReagentRow(r.formula, r.moles));
      } else {
        addReagentRow("NaOH", 1.0);
        addReagentRow("HCl", 1.0);
      }
    } catch (e) {
      addReagentRow("NaOH", 1.0);
      addReagentRow("HCl", 1.0);
    }
  } else {
    // Самый первый запуск
    addReagentRow("NaOH", 1.0);
    addReagentRow("HCl", 1.0);
  }

  document.getElementById("btn-add-reagent").onclick = () => {
    addReagentRow();
    saveState();
  };
   
  document.getElementById("btn-load-preset").onclick = async () => {
    const res = await apiCall("get_presets");
    if (res.status === "error") return alert("Ошибка загрузки пресетов");
    const presets = res.data;
    if (!presets || presets.length === 0) return alert("Пресеты не найдены");
    
    const names = presets.map((p, i) => `${i + 1}. ${p.name}`).join("\n");
    const choice = prompt("Выберите пресет (введите номер):\n\n" + names);
    if (!choice) return;
    const idx = parseInt(choice) - 1;
    if (isNaN(idx) || !presets[idx]) return;

    const p = presets[idx];
    list.innerHTML = ""; // Очищаем текущие реагенты
    p.reagents.forEach(r => addReagentRow(r.formula, r.moles));
    saveState(); // Сохраняем пресет
    
    if (p.conditions) {
      document.getElementById("cond-t").value = p.conditions.temperature_K;
      document.getElementById("cond-p").value = p.conditions.pressure_atm;
      document.getElementById("cond-v").value = p.conditions.volume_L;
    }
  };

  document.getElementById("btn-predict").onclick = async (e) => {
    const btn = e.target;
    const resArea = document.getElementById("result-area");
    btn.disabled = true;
    btn.textContent = "Расчет... (при первом запуске грузится база)";

    const reagents = Array.from(document.querySelectorAll(".reagent-row")).map(row => ({
      formula: row.querySelector(".reag-formula").value.trim(),
      moles: parseFloat(row.querySelector(".reag-moles").value)
    })).filter(r => r.formula);

    const conditions = {
      temperature_K: parseFloat(document.getElementById("cond-t").value),
      pressure_atm: parseFloat(document.getElementById("cond-p").value),
      volume_L: parseFloat(document.getElementById("cond-v").value)
    };

    const requestData = { reagents, conditions };
    const res = await apiCall("predict", requestData);

    btn.disabled = false;
    btn.textContent = "Рассчитать реакцию";
    resArea.style.display = "block";

    if (res.status === "error") {
      document.getElementById("res-equation").textContent = "Ошибка: " + res.error.message;
      document.getElementById("res-dg").textContent = "—";
      document.getElementById("res-status").textContent = "error";
    } else {
      const data = res.data;
      const eq = data.balanced_equations?.[0];
      document.getElementById("res-equation").textContent = eq ? eq.equation : (data.message || "Реакция не идет");
      document.getElementById("res-dg").textContent = eq ? eq.delta_G_kJ_mol.toFixed(1) : "—";
      document.getElementById("res-status").textContent = data.status;
    }
    document.getElementById("res-json").textContent = JSON.stringify(res.data || res.error, null, 2);
  };
}