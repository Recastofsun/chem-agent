offline_cache - что здесь лежит и откуда взято
===============================================

crc_ions_raw.tsv
    CRC Handbook of Chemistry and Physics, "Thermodynamic Properties of Aqueous Ions":
    dfH, dfG, S, Cp для 173 ионов. Файл взят без изменений из пакета chemicals 1.5.2
    (MIT, Caleb Bell), каталог chemicals/Electrolytes.

crc_substances_raw.tsv
    CRC Handbook, "Standard Thermodynamic Properties of Chemical Substances":
    dfH, dfG, S, Cp в фазах s/l/g для 2470 веществ (ключ - CAS). Источник тот же,
    каталог chemicals/Heat Capacity.

crc_cas_formula.tsv
    Соответствие CAS -> брутто-формула из идентификаторов PubChem, поставляемых в chemicals
    (Inorganic db, pubchem small/large). Покрывает 2155 из 2470 записей CRC.

crc_name_fixes.tsv
    Ручные исправления: формулы для записей без CAS-соответствия (сера, графит, CaC2 и др.) и
    замена ошибочных формул PubChem (например, Fe3O4 был записан как Fe3H8O4, Li2O - как ион).

wheels\
    Колеса Python для Windows x64 / CPython 3.11 с точными версиями из requirements*.txt.
    Заполняется setup_offline.ps1 (единственный сетевой скрипт) или уже лежит в архиве поставки.

Чего здесь нет и почему
-----------------------
nist_raw.json - NIST не распространяет таблицы термодинамики одним файлом, условия WebBook
    запрещают массовую выгрузку. Вместо NIST используются таблицы CRC.
mace_mp_0.model - веса MACE-MP-0 не нужны: модель обучена на кристаллах и не дает энергий
    Гиббса ионов в растворе (см. LIMITATIONS.md).

База chem_agent\data\crc.db собирается из этих файлов командой:
    .venv\Scripts\python.exe -m chem_agent.data.build
