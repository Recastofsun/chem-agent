"""Stage 4: Merge staging.db в crc.db с версионированием (W-26)."""
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

CRC_PATH = ROOT / "chem_agent" / "data" / "crc.db"
STAGING_PATH = ROOT / "chem_agent" / "data" / "staging.db"
MANIFEST_PATH = ROOT / "tools" / "universal_importer" / "manifest.json"
BACKUP_DIR = ROOT / "chem_agent" / "data" / "backups"


class Stage4Merge:
    def __init__(self):
        self.crc_path = CRC_PATH
        self.staging_path = STAGING_PATH
        self.manifest_path = MANIFEST_PATH
        self.backup_dir = BACKUP_DIR

    def run(self, dry_run: bool = False) -> dict:
        print("=" * 60)
        print("STAGE 4: Merge с версионированием")
        print("=" * 60)

        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest не найден: {self.manifest_path}")
        
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        new_species = manifest["new_species"]
        
        print(f"📦 Новых веществ для импорта: {len(new_species)}")
        print(f"📅 Timestamp: {manifest['timestamp']}")
        print(f"🔐 Source hash: {manifest['source_hash']}")
        
        if dry_run:
            print("\n🔍 DRY RUN - никаких изменений в crc.db не будет внесено")
            print(f"   Будет добавлено {len(new_species)} записей (только INSERT, без UPDATE).")
            return {"dry_run": True, "count": len(new_species)}

        # Шаг 1: Бэкап
        backup_path = self._create_backup()
        print(f"💾 Бэкап создан: {backup_path.name}")
        
        # Шаг 2: Merge (только INSERT, без UPDATE)
        count = self._merge_species(new_species)
        print(f"✅ Добавлено {count} новых веществ в crc.db")
        
        # Шаг 3: Версионирование
        version = self._update_version(manifest)
        print(f"🏷️  Новая версия БД: {version}")
        
        # Шаг 4: Лог
        self._log_import(manifest, count)
        print(" Лог импорта записан в таблицу import_log")
        
        return {
            "backup": backup_path.name,
            "imported": count,
            "version": version,
        }

    def _create_backup(self) -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        version = self._get_current_version()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"crc_backup_{version}_{timestamp}.db"
        backup_path = self.backup_dir / backup_name
        shutil.copy(str(self.crc_path), str(backup_path))
        return backup_path

    def _merge_species(self, new_species: list[dict]) -> int:
        """Копирует новые вещества из staging.db в crc.db (только INSERT, CRC Priority)."""
        staging_con = sqlite3.connect(str(self.staging_path))
        staging_cur = staging_con.cursor()
        
        crc_con = sqlite3.connect(str(self.crc_path))
        crc_cur = crc_con.cursor()
        
        count = 0
        skipped = 0
        
        for species in new_species:
            formula = species["formula"]
            phase = species["phase"]
            
            # CRC Priority: если уже есть в CRC, пропускаем
            existing = crc_cur.execute(
                "SELECT id, dGf FROM species WHERE formula = ? AND phase = ?",
                (formula, phase)
            ).fetchone()
            
            if existing:
                skipped += 1
                print(f"   ⚠️  Пропущен {formula}({phase}): уже есть в CRC (dGf={existing[1]})")
                continue
            
            # Копируем из staging.db
            staging_row = staging_cur.execute(
                """SELECT formula, hill, phase, elements, charge, dGf, source, sigma, name_en
                   FROM species WHERE formula = ? AND phase = ?""",
                (formula, phase)
            ).fetchone()
            
            if staging_row:
                crc_cur.execute(
                    """INSERT INTO species 
                       (formula, hill, phase, elements, charge, dGf, source, sigma, name_en)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    staging_row
                )
                count += 1
        
        crc_con.commit()
        staging_con.close()
        crc_con.close()
        
        print(f"\n   Добавлено: {count}, Пропущено (CRC exists): {skipped}")
        return count

    def _get_current_version(self) -> str:
        con = sqlite3.connect(str(self.crc_path))
        cur = con.cursor()
        
        table_exists = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'"
        ).fetchone()
        
        if not table_exists:
            cur.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
            cur.execute("INSERT INTO metadata (key, value) VALUES ('version', '2.5.0')")
            con.commit()
            version = "2.5.0"
        else:
            row = cur.execute("SELECT value FROM metadata WHERE key = 'version'").fetchone()
            version = row[0] if row else "2.5.0"
        
        con.close()
        return version

    def _update_version(self, manifest: dict) -> str:
        current_version = self._get_current_version()
        parts = current_version.split(".")
        if len(parts) == 3:
            parts[2] = str(int(parts[2]) + 1)
        new_version = ".".join(parts)
        
        con = sqlite3.connect(str(self.crc_path))
        cur = con.cursor()
        
        cur.execute("UPDATE metadata SET value = ? WHERE key = 'version'", (new_version,))
        cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('last_import', ?)", (manifest["timestamp"],))
        cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('source_hash', ?)", (manifest["source_hash"],))
        
        con.commit()
        con.close()
        return new_version

    def _log_import(self, manifest: dict, count: int):
        con = sqlite3.connect(str(self.crc_path))
        cur = con.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS import_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                source TEXT,
                source_hash TEXT,
                species_count INTEGER,
                manifest_json TEXT
            )
        """)
        
        cur.execute(
            """INSERT INTO import_log (timestamp, source, source_hash, species_count, manifest_json)
               VALUES (?, ?, ?, ?, ?)""",
            (
                manifest["timestamp"],
                manifest["source"],
                manifest["source_hash"],
                count,
                json.dumps(manifest, ensure_ascii=False)
            )
        )
        
        con.commit()
        con.close()


def main():
    print("=" * 60)
    print("УНИВЕРСАЛЬНЫЙ ИМПОРТЕР - STAGE 4 (MERGE)")
    print("=" * 60)
    
    merge = Stage4Merge()
    
    # 1. Dry Run
    print("\n🔍 ЭТАП 1: ПРОВЕРКА (DRY RUN)")
    result = merge.run(dry_run=True)
    
    # 2. Запрос подтверждения
    answer = input("\n⚠️  Продолжить реальный merge в crc.db? (y/n): ")
    if answer.lower().strip() != "y":
        print("❌ Merge отменен пользователем.")
        return
    
    # 3. Реальный Merge
    print("\n🚀 ЭТАП 2: ВЫПОЛНЕНИЕ MERGE")
    result = merge.run(dry_run=False)
    
    print("\n" + "=" * 60)
    print(" STAGE 4 ЗАВЕРШЕН УСПЕШНО!")
    print("=" * 60)
    print(f"💾 Бэкап сохранен: {result['backup']}")
    print(f"📦 Веществ импортировано: {result['imported']}")
    print(f"🏷️  Текущая версия crc.db: {result['version']}")


if __name__ == "__main__":
    main()