ТЗ: Chem-Agent v2.5 — Multiagent + Pipeline + Pitzer
Версия: 2.5.0
Дата: 26.10.2026
Репозиторий: https://github.com/Recastofsun/chem-agent
Ветка: dev
Режим работы: Локальный (без push в GitHub, через patch-файлы)
Ограничения: Только неорганика. UI и .exe не трогаем.

1. Контекст и цель
1.1. Текущее состояние (v2.4)
Точность на holdout_105.json: 93.3% (основной продукт).

1300 веществ в crc.db (CRC Handbook).

24 эмпирических правила forbid_new в rules.yaml.

Есть Anderson+Newton для γ (W-01), Cp-интеграция (W-02), электрохимия.

Нет: Pitzer, Pipeline, Staged balancer, внешних БД, MCP.

1.2. Цель v2.5
Точность 99+% на пуле из 100 реакций (первый этап), затем 1000.

Pitzer вместо SIT/Davies (блокирует точность на сульфатах).

Сократить rules.yaml до 5–7 фундаментальных правил.

Pipeline: разбить реакцию на этапы (диссоциация → комплекс → осаждение → газ → финал).

Staged balancer: если уравнение не сходится, разбить на элементарные стадии.

fetch_external.py: запросы к PubChem, кэш в data/external/.

MCP-сервер: 6 методов для внешних агентов.

5 методов синтеза: photochemical, sonochemical, hydrothermal, mechanochemical, sol-gel.

1.3. Иерархия доверия
Эксперимент (NIST, CRC, статьи) — высший приоритет.

Эксперт (Claude) — если эксперимент неоднозначен.

PHREEQC — золотой стандарт расчётов.

Наш кернел — только если три выше молчат.

2. Архитектура (Pipeline)
2.1. Пять этапов
Stage 1: Диссоциация реагентов (FeCl3 -> Fe³⁺ + 3Cl⁻)
Stage 2: Комплексообразование (Fe³⁺ + SCN⁻ -> FeSCN²⁺ -> ...)
Stage 3: Осаждение (если Ksp превышен)
Stage 4: Газовыделение (если P_i > P_sat)
Stage 5: Финальное равновесие (докрутка)

Ранний выход: если на этапе 1 все реагенты израсходованы — идём к 5.

Тупик: если solve() не сходится на этапе 3 → пробуем другой порядок → fallback на staged balancer → если None → status: "unknown".

2.2. Где живёт
chem_agent/pipeline/stages.py + chem_agent/pipeline/orchestrator.py.

2.3. Что видит пользователь
options.pipeline_mode: "compact" (default) — только финальный.

options.pipeline_mode: "detailed" — отчёт по этапам в explanation.

3. Staged Balancer
3.1. Когда используется
Только когда balance() вернул None.

3.2. Алгоритм
Найти промежуточные частицы (комплексы, ионные пары, гидроксо-формы).

Построить граф стадий.

Балансировать каждую.

Суммировать.

Если сумма не сходится → None.

3.3. Где живёт
chem_agent/search/staged_balancer.py.

3.4. Константы β
Из data/external/ (кэш fetch_external) или complex_constants в БД.

4. Pitzer (P0, блокирующее)
4.1. Формула
ln γ_i = ln γ_i^DH + Σ_j m_j (2β_ij^(0) + (2β_ij^(1) / α²I) * (1 - e^(-α√I) * (1 + α√I))) + Σ_j Σ_k m_j m_k C_ijk

где α = 2.0.

4.2. Таблица pitzer_parameters
CREATE TABLE pitzer_parameters (
ion1 TEXT,
ion2 TEXT,
beta0 REAL,
beta1 REAL,
beta2 REAL,
C_phi REAL,
theta REAL DEFAULT 0.0,
psi REAL DEFAULT 0.0,
source TEXT,
PRIMARY KEY (ion1, ion2)
);

4.3. Константы (NIST/CRC)
ion1	ion2	β⁰	β¹	β²	C^φ
Na⁺	Cl⁻	0.0765	0.2664	0.0	0.00127
Ca²⁺	SO₄²⁻	0.2000	3.1973	-54.24	-0.0
Ca²⁺	Cl⁻	0.3159	1.614	0.0	-0.00034
Mg²⁺	SO₄²⁻	0.2210	3.343	-37.23	0.025
Na⁺	SO₄²⁻	0.0196	1.113	0.0	0.0045
K⁺	Cl⁻	0.0483	0.2122	0.0	-0.00084
H⁺	Cl⁻	0.1775	0.2945	0.0	0.00080
4.4. Реализация
Метод get_pitzer в database.py.

Замена заглушки в activity.py.

Тест: phreeqc_01_gypsum → 0.0152 (было 0.0219).

5. Сокращение rules.yaml (P0)
5.1. Что остаётся (5–7 правил)
ID	Правило	Почему
n2_inert	N2 инертен	Тройная связь, огромная Ea
water_not_reduced	H2O не восстанавливается	Ea > 100 кДж/моль
gas_mix_no_igniter	H2 + O2 без искры	Ea > 150 кДж/моль
hydroxides_not_oxides	Гидроксиды вместо оксидов	Эмпирика (фундаментальная)
no_perchlorate	ClO4- не образуется	Ea > 200 кДж/моль
5.2. Куда уходит остальное
kinetic_barriers — Ea для OВР.

complex_constants — β для комплексов.

classifier.py — свойства (is_inert, is_strong_oxidizer).

6. fetch_external.py (P0)
6.1. PubChem API
GET https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{formula}/property/MolecularWeight,IUPACName/JSON

Rate limit: 5 req/s, без ключа.

6.2. Кэш
data/external/<formula>.json.

6.3. Fallback
Если PubChem недоступен → {"error": "no_data"} → coverage_report.json → status: "unknown".

6.4. Приоритет
PubChem первым. NIST WebBook (HTML scraping) — вторым.

7. MCP-сервер (P2)
7.1. 6 методов
Метод	Приоритет
predict(request)	P0
get_version()	P0
get_history(limit)	P1
get_compounds_by_element(el)	P1
search(query)	P2
benchmark()	P2
7.2. Где живёт
chem_agent/mcp/server.py (FastMCP или своя реализация).

8. Методы синтеза (P1)
Метод	Параметры	Тест
Photochemical	wavelength_nm, intensity	H2 + Cl2 -> 2HCl под светом
Sonochemical	frequency_kHz, power_W	CaCO3 + SiO2 -> CaSiO3 + CO2 при 20 кГц
Hydrothermal	autoclave_P_bar, T_K	Al(OH)3 + SiO2 -> каолинит при 200°C, 15 бар
Mechanochemical	rpm, ball_material	CaCO3 + SiO2 -> CaSiO3 без растворителя
Sol-gel	pH, aging_time_h	Si(OC2H5)4 -> SiO2
9. Кинетика (P1)
Модель	Параметры	Применение
Eyring (есть)	barrier_kJ_mol, order	Общий случай
Butler-Volmer (есть)	exchange_current, alpha	Электрохимия
Marcus (новое)	lambda_kJ_mol	Внешнесферный OВР
BEP (новое)	alpha, beta	Катализ
10. Формат уравнений
10.1. Три формы
Молекулярная: CaCO3 + 2HCl -> CaCl2 + CO2↑ + H2O

Полная ионная: CaCO3(s) + 2H⁺(aq) + 2Cl⁻(aq) -> Ca²⁺(aq) + 2Cl⁻(aq) + CO2↑ + H2O

Сокращённая ионная: CaCO3(s) + 2H⁺(aq) -> Ca²⁺(aq) + CO2↑ + H2O

10.2. Сравнение
Структурное: {formula: coeff} + фазы. CaCO3(s) ≠ CaCO3(aq).

10.3. Порог отсечения боковых продуктов
n_i < max(10⁻⁴, 10⁻³ · n_main) → игнорируем.

11. Мультиагентность (Claude Code)
11.1. Режим работы
Клонируем dev из GitHub.

Работаем локально.

В GitHub не пушим.

Генерируем патчи: git format-patch dev --stdout > patches/W-XX.patch.

11.2. Роли
Lead — читает ТЗ, создаёт tasks/W-XX.md.

Worker — работает в dev/w-XX-<name>, коммитит.

Reviewer — прогоняет все тесты.

Merger — не нужен (патчи применяет человек).

11.3. Guardrails
Только dev и dev/w-XX-*.

БД — только через scripts/patch_db_*.py.

pytest — 100%.

11.4. Шаблон задачи tasks/W-XX.md
W-XX: <Название>
Цель
<Что сделать>

Файлы
<трогать>

<НЕ трогать>

Критерий приёмки
<Тест 1>

Статус
⬜ TODO

12. Бюджет и пул
12.1. Первая итерация
100 реакций × 3 прохода (Claude генерирует → проверяет → проверяет ещё раз).

Бюджет: ~$5–10.

12.2. Категории
Нейтрализация, осаждение, ОВР, комплексы, разложение, электрохимия, газовые.

12.3. Если компонента нет
status: "unknown" + LIMITATIONS.md + coverage_report.json.

13. Критерии приёмки
13.1. P0
Pitzer: phreeqc_01_gypsum = 0.0152.

Пул 100: data/pool_100.json.

Точность 99+%: main_product + уравнение структурно.

fetch_external.py: работает.

staged_balancer.py: работает.

rules.yaml: 5–7 правил.

Pipeline: compact/detailed.

Все старые тесты: ✅.

13.2. P1
5 методов синтеза: с тестами.

Marcus + BEP: заготовки.

БД: henry_constants, complex_constants, pitzer_parameters.

coverage_report.json.

13.3. Финальная приёмка
Пул 1000.

Точность 99+%.

Тесты ✅.

CHANGELOG, DEVLOG, LIMITATIONS обновлены.

Тег v2.5.0.

14. Ссылки
GitHub: https://github.com/Recastofsun/chem-agent

Ветка: dev

ТЗ (этот файл): TZ/TZ_v2.5_multiagent.md

Предыдущее ТЗ: TZ/TZ_v2.4_weaknesses_and_limits.md

15. Первые 10 задач (P0/P1)
ID	Название	Приоритет	Зависимости
W-14	Pitzer	P0	—
W-01	fetch_external.py (PubChem)	P0	—
W-03	Rules cleanup (5–7 правил)	P0	—
W-02	staged_balancer.py	P0	W-01
W-04	Pipeline (5 этапов)	P1	W-02
W-05	Photochemical	P1	W-04
W-06	Sonochemical	P1	W-04
W-07	Hydrothermal	P1	W-04
W-08	Mechanochemical	P1	W-04
W-09	Sol-gel	P1	W-04