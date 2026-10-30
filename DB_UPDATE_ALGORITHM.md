# Алгоритм обновления базы данных crc.db

**Версия документа:** 1.0 (2026-10-30)  
**Статус:** Актуальный для v2.5.1+  
**Ответственный:** Recastofsun  
**Задача:** W-26 — Универсальный импортер термодинамических баз

---

## 1. Обзор

Обновление базы `chem_agent/data/crc.db` из внешних источников (PHREEQC, MINTEQ, WATEQ4F, LLNL) выполняется через **4-Stage Pipeline** с гарантией сохранения целостности существующих данных.

### Ключевые принципы

- **CRC Priority**: существующие вещества никогда не перезаписываются.
- **Только INSERT**: при merge никогда не делается UPDATE существующих записей.
- **Безопасный откат**: бэкап создаётся автоматически перед каждым merge.
- **Воспроизводимость**: manifest.json + sha256 источника фиксируют каждое изменение.
- **Регрессионный контроль**: merge запрещён, если точность pool-тестов падает ниже порога.
- **Читаемость формул**: комплексы сохраняются со скобками (`Cu(CO3)2-2`), минералы — в эмпирической форме (`CaCO3`).

---

## 2. Архитектура

tools/universal_importer/
├── init.py
├── formats/
│ ├── init.py # Реестр форматов
│ ├── base.py # Базовый класс парсера
│ └── phreeqc.py # Парсер PHREEQC (.dat)
├── core/
│ ├── init.py
│ ├── normalizer.py # clean_formula_complex / clean_formula_mineral
│ ├── calculator.py # Расчёт dGf, lookup в CRC
│ └── log_manager.py # Ротация логов (макс. 10 файлов)
├── pipeline.py # Stage 1: Parsing + Staging + Manifest
├── stage2_test_generator.py # Stage 2: Генерация тестов
├── stage4_merge.py # Stage 4: Merge с версионированием
├── diagnose_missed.py # Диагностика пропущенных реакций
└── orchestrator.py # Точка входа (Stage 1 + Stage 2)
scripts/
── add_hs_ion.py # Добавление базовых ионов в CRC (опционально)
└── diagnose_regression.py # Анализ влияния новых веществ на регрессию
chem_agent/data/
├── crc.db # Основная база (целевая)
├── staging.db # Промежуточная копия (удаляется после merge)
└── backups/
└── crc_backup_2.5.0_20261030_170546.db # Автоматические бэкапы
logs/importer/
└── stage1.log # Логи с ротацией (макс. 10 файлов)

---

## 3. Пошаговый алгоритм

### Stage 1: Parsing + Staging + Manifest

**Цель:** Распарсить внешний файл и создать staging.db с новыми веществами.

**Команда:**
```bash
python tools/universal_importer/orchestrator.py

Что происходит:
Парсинг .dat файла через соответствующий формат-парсер (PhreeqcFormat).
Создание staging.db как полной копии crc.db (CRC Priority на уровне файлов).
Для каждой реакции из источника:
Нормализация формул: clean_formula_complex для комплексов (со скобками), clean_formula_mineral для минералов (с раскрытием скобок).
Проверка баланса элементов и заряда (check_balance).
CRC Lookup: если (formula, phase) уже есть в crc.db → пропуск + запись в conflicts.
Blacklist: проверка по формуле и log_k.
Расчёт dGf через log_k и dGf реагентов из CRC.
INSERT в staging.db.
Генерация manifest.json (новые вещества + конфликты + статистика + sha256 источника).
Результат:
chem_agent/data/staging.db — копия crc.db + новые вещества.
tools/universal_importer/manifest.json — паспорт изменений.
Логи в logs/importer/ (автоматическая ротация, макс. 10 файлов).


Stage 2: Test Generation
Цель: Сгенерировать тесты для новых веществ.
Автоматически (после Stage 1):
python tools/universal_importer/stage2_test_generator.py

Результат: tests/test_generated_imports.py
Unit-тесты: наличие каждого нового вещества в staging.db.
Химические тесты: реакции осаждения для металлов (до 5 тестов).
Тест на отсутствие конфликтов: CRC-вещества не перезаписаны.
Ручная доработка (опционально):
AI-агент или химик может добавить специфические тесты на основе manifest.json.

Stage 3: Validation
Цель: Убедиться, что новые вещества не ломают существующую функциональность.
Команды:

# Тесты новых веществ
python -m pytest tests/test_generated_imports.py -v

# Регрессионные тесты (ОБЯЗАТЕЛЬНО)
python -m pytest tests/test_pool.py tests/test_pool_1000.py tests/test_thermo.py tests/test_regression.py tests/test_separation.py -v

Критерии приёмки:
Все unit-тесты новых веществ: PASS.
Точность pool_100: ≥ 0.96.
Точность pool_1000: ≥ 0.98.
Критические тесты (нейтрализация NaOH+HCl, гипс, кальцит, барит): PASS.
test_neutralization_pH_and_dG: delta_G ≈ -79.9 кДж/моль (не +2.63!).
Если критерии не выполнены:
Анализ manifest.json — какие вещества могли вызвать регрессию.
Расширение blacklist.
Возврат к Stage 1.
Stage 4: Merge с версионированием
Цель: Безопасно перенести новые вещества в crc.db.
Команда:
python tools/universal_importer/stage4_merge.py

Что происходит:
Dry Run: показ количества веществ для импорта без изменений.
Запрос подтверждения: ⚠️ Продолжить реальный merge в crc.db? (y/n):
Бэкап: crc_backup_{version}_{YYYYMMDD_HHMMSS}.db в chem_agent/data/backups/.
Merge: только INSERT новых веществ (CRC Priority на уровне merge).
Версионирование: инкремент patch-версии в таблице metadata (2.5.0 → 2.5.1).
Лог: запись в таблицу import_log (timestamp, source, source_hash, species_count, manifest_json).
Результат:
crc.db обновлён до новой версии.
Бэкап предыдущей версии сохранён.
Полная история импортов в таблице import_log.
4. Blacklist и критерии фильтрации
4.1. Blacklist по формуле
Сильные электролиты, которые полностью диссоциируют в воде:
BLACKLIST_FORMULAS = {
    # Сильные кислоты
    "HCl", "HBr", "HI", "HNO3", "H2SO4", "HClO4", "HClO3",
    
    # Сильные основания
    "NaOH", "KOH", "LiOH",
    
    # Странные вещества
    "C2O4",  # (CO2)2 - димер CO2, нестандартное
}

Обоснование: Эти вещества в воде полностью диссоциируют. Их добавление в базу ломает расчёты нейтрализации (delta_G NaOH+HCl стал +2.63 вместо -79.9 кДж/моль).
4.2. Blacklist по log_k
Вещества с log_k < -0.1 считаются полностью диссоциирующими и исключаются:
BLACKLIST_BY_LOGK_THRESHOLD = -0.1
Обоснование: log_k = -0.1 соответствует K = 0.79, т.е. равновесие смещено в сторону реагентов. Такие "комплексы" существуют в ничтожно малых количествах и ломают расчёты (Na2SO4, NaF, KF, NaHCO3, KHCO3, CuCl3-, CuCl4-2, MnCl3-, ZnBr+, ZnBr2 и др.).
4.3. CRC Priority
Если (formula, phase) уже существует в crc.db:
Действие: пропуск (никогда UPDATE).
Логирование: запись в conflicts manifest.json с указанием crc_dGf.
Ручной разбор: конфликты анализируются отдельно (например, HSO4⁻, H2S, HF, HPO4-2, H2PO4-, HF2-, Cu+).
4.4. Мастер-ионы
Мастер-ионы из блока SOLUTION_MASTER_SPECIES + {"H2O", "e-", "H+", "OH-"} автоматически исключаются из импорта.
5. Нормализация формул
5.1. clean_formula_complex (для водных комплексов)
НЕ раскрывает скобки — сохраняет читаемость:
Cu(CO3)2-2 → Cu(CO3)2-2 ✅
Fe(SO4)2- → Fe(SO4)2- ✅
Mn(NO3)2 → Mn(NO3)2 ✅
BF(OH)3- → BF(OH)3- ✅
Делает только:
Нормализацию зарядов: ++ → +2, --- → -3.
Удаление лишних пробелов.
Нормализацию гидратов: : → ·.
5.2. clean_formula_mineral (для минералов)
Раскрывает скобки — для эмпирической формулы:
Ca(CO3) → CaCO3 ✅
CaSO4·2H2O → CaSO4·2H2O ✅
6. Версионирование
6.1. Таблица metadata

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Пример данных:
-- ('version', '2.5.1')
-- ('last_import', '2026-10-30T15:58:45')
-- ('source_hash', 'sha256:5b2caeaa...')

6.2. Таблица import_log

CREATE TABLE import_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    source TEXT,
    source_hash TEXT,
    species_count INTEGER,
    manifest_json TEXT
);

6.3. Бэкапы
Расположение: chem_agent/data/backups/
Имя: crc_backup_{version}_{YYYYMMDD_HHMMSS}.db
Хранение: неограниченное (ручная очистка при необходимости).
7. Откат при регрессии
Если после merge обнаружена критическая регрессия:
# 1. Восстановить crc.db из последнего бэкапа
copy chem_agent\data\backups\crc_backup_2.5.0_20261030_170546.db chem_agent\data\crc.db

# 2. Проверить регрессионные тесты
python -m pytest tests/test_pool.py tests/test_pool_1000.py tests/test_thermo.py tests/test_regression.py -v

# 3. Проанализировать manifest.json и расширить blacklist
python scripts/diagnose_regression.py

# 4. Повторить Stage 1-4

8. Расширение на новые форматы
8.1. Добавление MINTEQ
Создать tools/universal_importer/formats/minteq.py:
from .base import BaseFormat, ParsedDatabase

class MinteqFormat(BaseFormat):
    FORMAT_NAME = "minteq"
    FILE_EXTENSIONS = (".dat", ".mint")
    
    def parse(self) -> ParsedDatabase:
        # Логика парсинга MINTEQ
        ...

Зарегистрировать в formats/__init__.py:
FORMAT_REGISTRY = {
    "phreeqc": PhreeqcFormat,
    "minteq": MinteqFormat,
}

Использовать:
from tools.universal_importer.formats import FORMAT_REGISTRY

parser = FORMAT_REGISTRY["minteq"](Path("minteq.dat"))
pipeline = Stage1Pipeline(...)
stats = pipeline.run(parser)

8.2. Требования к парсеру
Наследование от BaseFormat.
Возврат ParsedDatabase с полями:
master_species: список мастер-ионов.
reactions: список реакций с log_k.
stats: статистика парсинга.
9. Troubleshooting
9.1. Точность pool упала после merge
Симптомы: pool_100 < 0.96 или pool_1000 < 0.98.
Действия:
Откатить merge (раздел 7).
Проанализировать manifest.json — найти вещества с отрицательным log_k.
Расширить blacklist.
Повторить Stage 1-4.
Известный случай: После первого merge точность pool_1000 упала с 0.982 до 0.974 из-за добавления 127 веществ. После расширения blacklist (HCl, Na2SO4, NaF, KF) точность восстановилась.
9.2. Формулы раскрываются (MgO8S2-2 вместо Mg(SO4)2-2)
Причина: clean_formula_complex раскрывает скобки.
Решение: Убедиться, что в core/normalizer.py:
clean_formula_complex НЕ содержит цикл while "(" in formula:.
clean_formula_mineral содержит этот цикл.
В pipeline.py используются правильные функции для каждого типа.
9.3. Отсутствует базовый ион (например, HS⁻)
Симптомы: skipped_missing_reactants > 0 в статистике Stage 1.
Решение:
Добавить ион вручную в crc.db через scripts/add_{ion}_ion.py.
Использовать табличное значение dGf из CRC Handbook (НЕ рассчитывать из PHREEQC — разные референсы дают расхождение до 147 кДж/моль).
Повторить Stage 1.
9.4. Конфликты CRC Priority
Симптомы: skipped_crc_exists > 0 в статистике.
Действия:
Изучить conflicts в manifest.json.
Если разница dGf < 1 кДж/моль — игнорировать.
Если разница > 10 кДж/моль — ручной разбор (возможно, ошибка в CRC или PHREEQC использует относительные энергии).
9.5. Относительные энергии в PHREEQC
Проблема: PHREEQC использует внутренние референсы (например, dGf(H2O) относительный). Расчёт dGf(HS) через PHREEQC дал 12.09 и 159.54 кДж/моль, табличное значение CRC = -17.7 кДж/моль.
Решение: Всегда использовать табличные значения CRC Handbook для базовых ионов. Никогда не перезаписывать CRC данными из PHREEQC.
9.6. HCl(aq) ломает нейтрализацию
Симптомы: delta_G нейтрализации NaOH+HCl = +2.63 вместо -79.9 кДж/моль.
Причина: HCl(aq) с log_k = -0.46 — молекулярная форма, которая "перетягивает" равновесие.
Решение: Добавить HCl в blacklist. То же для всех сильных кислот/оснований.
10. Чеклист перед merge
Stage 1 завершён без ошибок.
manifest.json сгенерирован.
Stage 2: тесты сгенерированы.
Stage 3: все unit-тесты PASS.
Stage 3: pool_100 ≥ 0.96.
Stage 3: pool_1000 ≥ 0.98.
Stage 3: критические тесты (нейтрализация, гипс, кальцит, барит) PASS.
Blacklist проверен (нет HCl, NaOH, Na2SO4 в новых веществах).
Формулы со скобками сохранены (Cu(CO3)2-2, не CuC2O6-2).
Dry Run выполнен, количество веществ проверено.
Бэкап crc.db существует в chem_agent/data/backups/.
11. История изменений документа
Дата
Версия
Изменения
2026-10-30
1.0
Первоначальная версия на основе W-26. Включает все уроки из регрессии: blacklist по log_k, только INSERT, clean_formula_complex vs clean_formula_mineral, известные случаи (HCl, HS⁻).
12. Уроки и лучшие практики
Никогда не делать UPDATE при импорте из внешнего источника. Только INSERT + CRC Priority.
Blacklist по log_k эффективнее blacklist по формулам. Вещества с log_k < -0.1 полностью диссоциируют.
Табличные значения CRC надёжнее расчётов из PHREEQC. Разные референсы дают расхождение в 147 кДж/моль.
Manifest.json — ключ к воспроизводимости. sha256 источника + список веществ + конфликты.
Регрессионные тесты обязательны перед merge. Pool_100 и pool_1000 — детекторы поломок.
Сильные электролиты ломают расчёты. HCl, NaOH, Na2SO4 и аналоги полностью диссоциируют в воде.
Формулы комплексов должны сохранять скобки. Cu(CO3)2-2 читаемо, CuC2O6-2 — нет.
Откат должен занимать 1 команду. Всегда иметь свежий бэкап.