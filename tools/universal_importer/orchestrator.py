"""Оркестратор Stage 1 и Stage 2 (W-26)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from tools.universal_importer.formats.phreeqc import PhreeqcFormat
from tools.universal_importer.pipeline import Stage1Pipeline
from tools.universal_importer.stage2_test_generator import TestGenerator


def run_stage1():
    """Запускает Stage 1: Parsing + Staging + Manifest."""
    print("=" * 60)
    print("STAGE 1: Parsing + Staging + Manifest Generation")
    print("=" * 60)
    
    # Пути
    dat_path = ROOT / "data" / "phreeqc.dat"
    crc_db_path = ROOT / "chem_agent" / "data" / "crc.db"
    staging_db_path = ROOT / "chem_agent" / "data" / "staging.db"
    manifest_path = ROOT / "tools" / "universal_importer" / "manifest.json"
    log_dir = ROOT / "logs" / "importer"
    
    if not dat_path.exists():
        print(f"❌ Файл не найден: {dat_path}")
        sys.exit(1)
    
    if not crc_db_path.exists():
        print(f"❌ CRC DB не найден: {crc_db_path}")
        sys.exit(1)
    
    # Создаем парсер
    parser = PhreeqcFormat(dat_path)
    
    # Создаем пайплайн
    pipeline = Stage1Pipeline(
        crc_db_path=crc_db_path,
        staging_db_path=staging_db_path,
        manifest_path=manifest_path,
        log_dir=log_dir,
        overwrite_staging=True,
    )
    
    # Запускаем Stage 1
    stats = pipeline.run(parser)
    
    print("\n" + "=" * 60)
    print("✅ STAGE 1 ЗАВЕРШЕН!")
    print("=" * 60)
    print(f"📂 Staging DB: {staging_db_path}")
    print(f"📝 Manifest: {manifest_path}")
    print(f"📊 Новых веществ: {stats.added}")
    print(f"⚠️  Конфликтов (CRC priority): {stats.skipped_crc_exists}")
    
    return manifest_path


def run_stage2(manifest_path: Path):
    """Запускает Stage 2: Генерация тестов."""
    print("\n" + "=" * 60)
    print("STAGE 2: Генерация тестов")
    print("=" * 60)
    
    test_output_path = ROOT / "tests" / "test_generated_imports.py"
    
    generator = TestGenerator(manifest_path, test_output_path)
    stats = generator.generate()
    
    print(f"✅ Тесты сгенерированы: {test_output_path}")
    print(f"   Unit-тестов: {stats['unit_tests']}")
    print(f"   Химических тестов: {stats['chemical_tests']}")
    
    print("\n" + "=" * 60)
    print("✅ STAGE 2 ЗАВЕРШЕН!")
    print("=" * 60)
    print("\nСледующий шаг: Stage 3 - Запуск тестов")
    print(f"   python -m pytest {test_output_path} -v")


def main():
    print("=" * 60)
    print("УНИВЕРСАЛЬНЫЙ ИМПОРТЕР - STAGE 1 & 2")
    print("=" * 60)
    
    # Stage 1
    manifest_path = run_stage1()
    
    # Stage 2
    run_stage2(manifest_path)
    
    print("\n" + "=" * 60)
    print("🎉 STAGE 1 & 2 ЗАВЕРШЕНЫ!")
    print("=" * 60)
    print("\nТеперь вы можете:")
    print("1. Проверить сгенерированные тесты: tests/test_generated_imports.py")
    print("2. Запустить тесты: python -m pytest tests/test_generated_imports.py -v")
    print("3. После успешных тестов - перейти к Stage 3 (Merge)")


if __name__ == "__main__":
    main()