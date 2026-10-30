"""Проверка реакции HS- в phreeqc.dat."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAT_PATH = ROOT / "data" / "phreeqc.dat"

lines = DAT_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()

print("=" * 60)
print("РЕАКЦИИ С УЧАСТИЕМ HS- В PHREEQC.DAT")
print("=" * 60)

# Показываем строки 255-270 (вокруг реакции HS- = S-2 + H+)
print("\n📋 Блок реакции HS- = S-2 + H+ (строки 255-270):")
for i in range(254, 270):
    if i < len(lines):
        print(f"  {i+1}: {lines[i].rstrip()}")

# Также ищем все упоминания HS-
print("\n📋 Все строки с HS-:")
for i, line in enumerate(lines):
    if "HS-" in line and "HSO" not in line:
        print(f"  {i+1}: {line.rstrip()}")