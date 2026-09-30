# chem-agent 1.0

Локальный офлайн-агент, который по набору реагентов и условиям предсказывает продукты
неорганических реакций, их равновесные количества, ΔG и константу равновесия, кинетику (где есть
данные) и погрешность каждого числа. Работает без интернета, без облачных API и без LLM.

Метод: минимизация энергии Гиббса по всем веществам из локальной базы, которые можно собрать из
элементов системы, плюс кинетические правила, отсекающие известные заторможенные превращения
(`chem_agent/data/rules.yaml`). Если данных для вещества нет - оно не рассматривается, система
пишет «неизвестно», а не угадывает.

## Область применимости

- Неорганика в разбавленных водных растворах (до ~0,5 моль/кг) и «сухие» системы: газы, твердые
  вещества, высокие температуры.
- Нейтрализация, осаждение, выделение газов, ОВР, вытеснение металлов, аммиачные комплексы,
  термическое разложение, синтез из простых веществ.
- Органика вне области применимости: такие реакции система не предсказывает (см. `LIMITATIONS.md`).

Точность (главный продукт в тройке лучших, Accuracy@3):

- эталон из 205 реакций, 195 в области применимости: **90,8 %**;
- слепая отложенная выборка из 60 реакций, которую писал отдельный агент без доступа к правилам: **100 %**
  (реакции там проще, чем в основном эталоне).

Подробности - в `CHANGELOG.md`, ограничения - в `LIMITATIONS.md`.

## Установка на Windows 10/11

Нужен Python 3.11 x64 с python.org (при установке оставить галочку «py launcher»). Скрипты работают
и в PowerShell 7 (`pwsh`), и во встроенном Windows PowerShell 5.1: `.bat`-обертки сами выбирают доступный.

### Вариант А: папка или архив с колесами (без интернета)

1. Распаковать `chem-agent-offline-YYYYMMDD.zip` в любую папку (кириллица и пробелы в пути допустимы)
   или открыть уже готовую папку `chem-agent`.
2. Запустить `install_offline.bat`. Скрипт создаст `.venv`,
   поставит пакеты из `offline_cache\wheels` и прогонит самопроверку.

### Вариант Б: папка без колес (один раз нужен интернет)

1. Запустить `setup_offline.bat`. Это единственный скрипт, который ходит в сеть: скачивает колеса
   в `offline_cache\wheels`, ставит их и прогоняет самопроверку.
2. Дальше всё работает офлайн. `build_offline_bundle.bat` соберет переносимый архив.

Если PowerShell ругается на политику выполнения:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Windows Defender может замедлять первый запуск numpy/scipy. Можно добавить папку проекта в
исключения, но это не обязательно.

Пути длиннее 260 символов chem-agent пишет сам (префикс `\\?\`). Для остальных программ можно
включить системную поддержку: `enable_long_paths.ps1` (нужны права администратора).

## Запуск

Без активации окружения:

```bat
run_cli.bat predict --reagents "NaOH:0.1,HCl:0.1" --output html --open
run_cli.bat predict --input examples\redox.json --output html,json,markdown
run_cli.bat self-test
run_cli.bat benchmark -v
run_api.bat
```

С активацией:

```powershell
.\.venv\Scripts\Activate.ps1
chem-agent predict --reagents "Zn(s):0.02,HCl:0.05" --temp 298 --output html
chem-agent predict --reagents "CaCO3:0.1" --solvent none --temp 1200
chem-agent version
```

Формат `--reagents`: `формула:моль` через запятую. Фазу можно указать в формуле: `Zn(s)`,
`CO2(g)`, `NaCl(aq)`. Без указания фаза выбирается автоматически и это отмечается в предупреждениях.

Отчеты по умолчанию сохраняются в `%LOCALAPPDATA%\chem-agent\reports\`, имя
`chem-agent_<reaction_id>_<время>.html|json|md`. Папку можно задать `--output-dir` или
`options.output_dir`.

### REST API и веб-интерфейс

`run_api.bat` поднимает сервер только на `127.0.0.1:8000` и открывает браузер с формой ввода.

| Метод | Путь | Что делает |
|---|---|---|
| POST | /predict | расчет, тело - JSON-запрос (схема ниже) |
| GET | /report/{id} | HTML-отчет |
| GET | /report/{id}.json | JSON-результат |
| GET | /health, /version | состояние, версия |
| GET | /databases, /models | сводка базы, статус ML/DFT |
| GET | /history | расчеты текущей сессии |

### Python SDK

```python
from chem_agent import Agent

agent = Agent(offline=True)
result = agent.predict(
    reagents=[{"formula": "NaOH", "moles": 0.2, "phase": "aq"},
              {"formula": "H2SO4", "moles": 0.1, "phase": "aq"}],
    conditions={"temperature_K": 298.15, "solvent": "water"},
    known_energies={"H2SO4": {"delta_Gf_kJ_mol": -690.0, "source": "user", "phase": "aq"}},
    options={"output_formats": ["html", "json"]},
)
result.save_html(r"C:\Users\Public\chem-agent-reports\report.html")
print(result["summary"])
```

## Входные данные

Полная схема - в `examples\neutralization.json` (совпадает со схемой из ТЗ). Главное:

- `reagents[]`: `formula`, `moles` (или `mass_g`), `phase` (aq/s/l/g), `concentration_M`,
  `known_energy` (ручная ΔfG для этого реагента).
- `conditions`: `temperature_K`, `temperature_profile` (ramp/points), `pressure_atm`, `volume_L`,
  `water_kg`, `solvent` (`water` или `none`; `dielectric_constant`, `ionic_strength_M`,
  `activity_model`), `pH` (`initial`, `buffered`), `atmosphere` (`composition`, `mode`:
  closed/open, `headspace_L`), `catalyst` (`formula`, `barrier_kJ_mol`), `time`.
- `known_energies`: ΔfG, ΔfH, S, Cp по формулам - высший приоритет.
- `constraints.forbidden_products`, `constraints.max_products`.
- `options`: `accuracy` (fast/balanced/accurate = 8/24/64 членов ансамбля), `activity_model`
  (ideal/debye_huckel/davies; pitzer - см. ограничения), `uncertainty_method`
  (ensemble/bootstrap/none), `kinetics` (`barrier_kJ_mol`, `order`), `disabled_rules`
  (отключить кинетические правила по id), `random_seed`, `theme`, `output_formats`.

## Приоритет источников энергии

1. `known_energies` и `reagents[].known_energy` из запроса.
2. Локальная база: CRC Handbook (1 248 веществ и ионов), 26 значений NBS-1982, 16 твердых фаз из
   произведений растворимости, 1 ион из стандартного потенциала.
3. ML-потенциал - не используется (см. ограничения).
4. DFT - не используется.
5. Эмпирическая оценка - только пересчет ΔfG на другую температуру при постоянных ΔfH и ΔfS.
6. «неизвестно».

Источник каждого значения указан в отчете.

## Отчет

Один HTML-файл без внешних ссылок: открывается двойным кликом, светлая и
темная темы, сортировка таблиц, раскрытие разделов, увеличение графиков по клику, печать в PDF
(Ctrl+P), скачивание JSON. Разделы: резюме, вход, реакции, продукты, термодинамика, кинетика,
неопределенность, объяснение (включая сработавшие кинетические правила), метаданные.

## Тесты

```powershell
self_test.bat            # весь набор pytest (152 теста), офлайн
run_cli.bat self-test    # быстрая встроенная проверка без pytest
run_cli.bat benchmark -v # Accuracy@3 на эталоне
```

## Структура

См. ТЗ, раздел 5. Отличия от ТЗ перечислены в `CHANGELOG.md`.
