"""Создание pitzer.db из JSON-источника (W-08/W-09).
Читает data/pitzer_parameters.json, валидирует и создает отдельную БД pitzer.db.
Идемпотентен: повторный запуск пересоздает БД.
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "data" / "pitzer_parameters.json"
DB_PATH = ROOT / "chem_agent" / "data" / "pitzer.db"

# Допустимые диапазоны параметров (физическая валидация)
RANGES = {
    "beta0": (-0.5, 1.0),
    "beta1": (-1.0, 5.0),
    "beta2": (-100.0, 100.0),
    "C_phi": (-0.1, 0.1),
    "theta": (-0.5, 0.5),
    "psi": (-1.0, 1.0),
}

REQUIRED_FIELDS = ["ion1", "ion2", "beta0", "beta1", "beta2", "C_phi", "theta", "psi", "source"]


def validate_parameter(p: dict, idx: int) -> list[str]:
    """Физическая валидация одной пары параметров. Возвращает список ошибок."""
    errors = []
    
    # Проверка обязательных полей
    for field in REQUIRED_FIELDS:
        if field not in p:
            errors.append(f"Пара #{idx}: отсутствует поле '{field}'")
    
    if errors:
        return errors
    
    # Проверка диапазонов
    for field, (lo, hi) in RANGES.items():
        val = p.get(field, 0.0)
        if val < lo or val > hi:
            errors.append(f"Пара #{idx} ({p['ion1']}/{p['ion2']}): {field}={val} вне диапазона [{lo}, {hi}]")
    
    # Проверка, что beta1 > 0 для большинства пар (физический смысл)
    if p.get("beta1", 0.0) < 0 and p.get("beta2", 0.0) == 0:
        errors.append(f"Пара #{idx} ({p['ion1']}/{p['ion2']}): beta1<0 при beta2=0 — подозрительно")
    
    return errors


def main():
    if not JSON_PATH.exists():
        print(f"❌ JSON не найден: {JSON_PATH}")
        return
    
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    
    # Удаляем старую БД
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"🗑️  Удалена старая pitzer.db")
    
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    # Создаем таблицу metadata
    cur.execute("""
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cur.execute("INSERT INTO metadata (key, value) VALUES ('version', ?)", (data.get("version", "1.0"),))
    cur.execute("INSERT INTO metadata (key, value) VALUES ('updated', ?)", (data.get("updated", ""),))
    cur.execute("INSERT INTO metadata (key, value) VALUES ('temperature_K', ?)", (str(data.get("temperature_K", 298.15)),))
    cur.execute("INSERT INTO metadata (key, value) VALUES ('source', ?)", (data.get("source", ""),))
    
    # Создаем таблицу parameters
    cur.execute("""
        CREATE TABLE parameters (
            ion1 TEXT NOT NULL,
            ion2 TEXT NOT NULL,
            beta0 REAL NOT NULL,
            beta1 REAL NOT NULL,
            beta2 REAL DEFAULT 0.0,
            C_phi REAL DEFAULT 0.0,
            theta REAL DEFAULT 0.0,
            psi REAL DEFAULT 0.0,
            source TEXT,
            validated INTEGER DEFAULT 0,
            notes TEXT,
            T_min REAL DEFAULT 298.15,
            T_max REAL DEFAULT 298.15,
            PRIMARY KEY (ion1, ion2)
        )
    """)
    
    # Валидируем и вставляем параметры
    errors = []
    validated_count = 0
    unvalidated_count = 0
    
    for idx, p in enumerate(data["parameters"], 1):
        param_errors = validate_parameter(p, idx)
        if param_errors:
            errors.extend(param_errors)
            continue
        
        cur.execute(
            "INSERT INTO parameters VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (p["ion1"], p["ion2"], p["beta0"], p["beta1"], p["beta2"],
             p["C_phi"], p["theta"], p["psi"], p["source"],
             1 if p.get("validated", False) else 0,
             p.get("notes", ""),
             data.get("temperature_K", 298.15),
             data.get("temperature_K", 298.15))
        )
        
        if p.get("validated", False):
            validated_count += 1
        else:
            unvalidated_count += 1
    
    if errors:
        print(f"❌ Ошибки валидации ({len(errors)}):")
        for err in errors:
            print(f"   - {err}")
        print("\n⚠️  Создание БД прервано. Исправьте JSON и повторите.")
        con.close()
        return
    
    con.commit()
    
    # Статистика
    total = cur.execute("SELECT count(*) FROM parameters").fetchone()[0]
    print(f"✅ pitzer.db создан:")
    print(f"   Всего пар: {total}")
    print(f"   Проверенных (validated=true): {validated_count}")
    print(f"   Требуют проверки (validated=false): {unvalidated_count}")
    print(f"   Температура: {data.get('temperature_K', 298.15)} K")
    print(f"   Источник: {JSON_PATH.name}")
    
    con.close()


if __name__ == "__main__":
    main()