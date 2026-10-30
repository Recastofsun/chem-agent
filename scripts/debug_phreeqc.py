"""Диагностика структуры phreeqc.dat для полного парсинга (W-26)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAT_PATH = ROOT / "data" / "phreeqc.dat"

def main():
    if not DAT_PATH.exists():
        print(f"Файл {DAT_PATH} не найден!")
        return

    lines = DAT_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    
    blocks = ["SOLUTION_MASTER_SPECIES", "SOLUTION_SPECIES", "PHASES"]
    current_block = None
    
    counts = {b: 0 for b in blocks}
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if line in blocks:
            current_block = line
            print(f"\n=== Блок {line} (первые 5 записей) ===")
            i += 1
            continue
            
        if line == "END" or (line and line[0].isupper() and line in blocks):
            current_block = None
            
        if current_block and line and not line.startswith("#"):
            # Выводим только начало каждой записи (первые 60 символов)
            if counts[current_block] < 5:
                print(f"  {line[:60]}")
                counts[current_block] += 1
        i += 1

    print(f"\nВсего строк в файле: {len(lines)}")
    print(f"Найдено записей (первые 5):")
    for b in blocks:
        print(f"  {b}: {counts[b]} (показаны первые 5)")

if __name__ == "__main__":
    main()