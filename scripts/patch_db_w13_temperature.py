"""Миграция crc.db для W-13: температурная зависимость Ea(T).

Добавляет в kinetic_barriers:
- dh_act_kj_mol, ds_act_j_mol_k (полное уравнение Эйринга)
- t_ref_2, ea_t2_kj_mol (двухточечная калибровка)

Пересчитывает существующие Ea (при T_ref) в ΔH‡ и ΔS‡ через соотношение:
    ΔH‡ ≈ Ea - R·T_ref  (для реакций в растворе)
    k_ref = ln(2) / 3600  (t1/2 = 1 ч)
    ΔS‡ = R·ln(k_ref·h/(kB·T_ref)) + ΔH‡/T_ref

Скрипт идемпотентен: повторный запуск обновляет значения, не дублирует.
"""
import math
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"

# Физические константы
KB = 1.380649e-23       # J/K
H_PLANCK = 6.62607015e-34  # J·s
R_J = 8.314462618       # J/(mol·K)
R_KJ = 8.314462618e-3   # kJ/(mol·K)

# Условие t1/2 = 1 ч (использовалось при расчёте исходных Ea)
HALF_LIFE_S = 3600.0
K_REF = math.log(2) / HALF_LIFE_S  # s^-1


def add_columns(cur: sqlite3.Cursor):
    """Добавляет новые колонки, если их нет."""
    # Получаем список существующих колонок
    cur.execute("PRAGMA table_info(kinetic_barriers)")
    existing = {row[1] for row in cur.fetchall()}
    
    new_columns = [
        ("dh_act_kj_mol", "REAL"),
        ("ds_act_j_mol_k", "REAL"),
        ("t_ref_2", "REAL"),
        ("ea_t2_kj_mol", "REAL"),
    ]
    
    for col_name, col_type in new_columns:
        if col_name not in existing:
            cur.execute(f"ALTER TABLE kinetic_barriers ADD COLUMN {col_name} {col_type}")
            print(f"   + Добавлена колонка {col_name}")
        else:
            print(f"   ✓ Колонка {col_name} уже существует")


def ea_to_dh_ds(ea_kj_mol: float, t_ref: float) -> tuple[float, float]:
    """
    Пересчёт Ea при T_ref в ΔH‡ и ΔS‡.
    
    Для реакций в растворе: ΔH‡ ≈ Ea - R·T_ref
    Из уравнения Эйринга при T_ref:
        k_ref = (kB·T_ref/h) · exp(ΔS‡/R) · exp(-ΔH‡/(R·T_ref))
    Отсюда:
        ΔS‡ = R · [ln(k_ref·h/(kB·T_ref)) + ΔH‡/(R·T_ref)]
    """
    dh_act = ea_kj_mol - R_KJ * t_ref  # кДж/моль
    
    # k_ref в s^-1, переводим в формулу Эйринга
    # ln(k·h/(kB·T)) = ΔS‡/R - ΔH‡/(R·T)
    ln_prefactor = math.log(K_REF * H_PLANCK / (KB * t_ref))
    ds_act = R_J * (ln_prefactor + dh_act * 1000.0 / (R_J * t_ref))  # J/(mol·K)
    
    return dh_act, ds_act


def migrate():
    if not DB_PATH.exists():
        print(f"❌ База не найдена: {DB_PATH}")
        return
    
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    # Проверяем наличие таблицы
    table_exists = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='kinetic_barriers'"
    ).fetchone()
    if not table_exists:
        print("❌ Таблица kinetic_barriers не найдена")
        con.close()
        return
    
    print("🔧 Шаг 1: Добавление новых колонок")
    add_columns(cur)
    con.commit()
    
    print("\n🔧 Шаг 2: Пересчёт существующих Ea → ΔH‡/ΔS‡")
    
    # Получаем все записи с Ea и T_ref
    rows = cur.execute(
        "SELECT id, reaction_key, ea_kj_mol, T_ref FROM kinetic_barriers "
        "WHERE ea_kj_mol IS NOT NULL"
    ).fetchall()
    
    updated = 0
    skipped = 0
    
    for row_id, reaction_key, ea, t_ref in rows:
        if t_ref is None:
            # Нет опорной температуры — используем стандартную 298.15 K
            t_ref = 298.15
        
        dh_act, ds_act = ea_to_dh_ds(ea, t_ref)
        
        cur.execute(
            "UPDATE kinetic_barriers SET dh_act_kj_mol = ?, ds_act_j_mol_k = ? WHERE id = ?",
            (round(dh_act, 4), round(ds_act, 4), row_id)
        )
        updated += 1
    
    con.commit()
    
    print(f"\n✅ Миграция завершена:")
    print(f"   Обновлено записей: {updated}")
    print(f"   Пропущено (нет Ea): {skipped}")
    print(f"   Всего записей в kinetic_barriers: {cur.execute('SELECT count(*) FROM kinetic_barriers').fetchone()[0]}")
    
    # Выводим примеры
    print("\n📋 Примеры пересчёта:")
    examples = cur.execute(
        "SELECT reaction_key, ea_kj_mol, T_ref, dh_act_kj_mol, ds_act_j_mol_k "
        "FROM kinetic_barriers WHERE dh_act_kj_mol IS NOT NULL LIMIT 5"
    ).fetchall()
    
    for key, ea, t_ref, dh, ds in examples:
        t_ref_str = f"{t_ref:.0f}K" if t_ref is not None else "N/A"
        print(f" {key[:40]:40s} | Ea={ea:6.2f} @ {t_ref_str} → ΔH‡={dh:7.3f} кДж/моль, ΔS‡={ds:7.2f} Дж/(моль·К)")
    
    con.close()


if __name__ == "__main__":
    migrate()