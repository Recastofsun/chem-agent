"""
Скрипт для извлечения параметров Pitzer при 25°C из файла pitzer.dat (Appelo 2015).
Первое число в каждой строке блока -B0, -B1, -B2, -C0 является значением при 298.15 K.
"""
import json
import re
from pathlib import Path

# Путь к файлу (лежит в data/pitzer.dat)
DAT_PATH = Path(__file__).parent.parent / "data" / "pitzer.dat"
OUTPUT_JSON = Path(__file__).parent.parent / "data" / "pitzer_parameters.json"

def extract_pitzer_25c(file_path: Path) -> list[dict]:
    if not file_path.exists():
        raise FileNotFoundError(f"Файл {file_path} не найден.")
    
    # Пробуем разные кодировки
    for encoding in ["utf-8", "cp1252", "latin-1", "iso-8859-1"]:
        try:
            content = file_path.read_text(encoding=encoding)
            print(f"✅ Успешно прочитано в кодировке {encoding}")
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"Не удалось прочитать файл {file_path} ни в одной из кодировок")
    
    # Ищем блоки -B0, -B1, -B2, -C0
    blocks = {
        "beta0": re.search(r'-B0\s+(.*?)(?=-B1|-B2|-C0|-THETA|\Z)', content, re.DOTALL),
        "beta1": re.search(r'-B1\s+(.*?)(?=-B2|-C0|-THETA|\Z)', content, re.DOTALL),
        "beta2": re.search(r'-B2\s+(.*?)(?=-C0|-THETA|\Z)', content, re.DOTALL),
        "C_phi": re.search(r'-C0\s+(.*?)(?=-THETA|-LAMDA|\Z)', content, re.DOTALL),
    }
    
    params_dict = {}
    
    for param_name, match in blocks.items():
        if not match:
            continue
        block_text = match.group(1)
        
        # Регулярка: ион1 ион2 число [число...] # комментарий
        pattern = re.compile(r'^\s*([A-Za-z0-9\+\-\.]+)\s+([A-Za-z0-9\+\-\.]+)\s+(-?\d+\.?\d*(?:e[+-]?\d+)?)', re.MULTILINE)
        
        for m in pattern.finditer(block_text):
            ion1 = m.group(1).replace(" ", "")
            ion2 = m.group(2).replace(" ", "")
            value = float(m.group(3))
            
            # Нормализуем порядок ионов для ключа (катион первый)
            key = tuple(sorted([ion1, ion2]))
            
            if key not in params_dict:
                params_dict[key] = {"ion1": key[0], "ion2": key[1], "beta0": 0.0, "beta1": 0.0, "beta2": 0.0, "C_phi": 0.0, "source": "Appelo2015"}
            
            params_dict[key][param_name] = value

    # Добавляем fallback для нитратов, которых нет в этом файле
    fallback_nitrates = [
        {"ion1": "H+", "ion2": "NO3-", "beta0": 0.111, "beta1": 0.35, "beta2": 0.0, "C_phi": 0.0, "source": "Pitzer1991", "notes": "Fallback: отсутствует в pitzer.dat"},
        {"ion1": "Na+", "ion2": "NO3-", "beta0": 0.011, "beta1": 0.15, "beta2": 0.0, "C_phi": -0.0005, "source": "Holmes&Mesmer1986", "notes": "Fallback: отсутствует в pitzer.dat"}
    ]
    
    for fb in fallback_nitrates:
        key = tuple(sorted([fb["ion1"], fb["ion2"]]))
        if key not in params_dict:
            params_dict[key] = fb

    return list(params_dict.values())

def main():
    print(f"Чтение {DAT_PATH}...")
    params = extract_pitzer_25c(DAT_PATH)
    print(f"✅ Извлечено {len(params)} уникальных пар параметров Pitzer при 25°C.")
    
    output_data = {
        "version": "1.1",
        "updated": "2026-10-30",
        "temperature_K": 298.15,
        "source": "Appelo 2015 (phreeqpython) + Holmes&Mesmer 1986 (fallback)",
        "description": "Параметры Pitzer при 25°C, извлеченные из современного файла pitzer.dat.",
        "parameters": [
            {**p, "theta": 0.0, "psi": 0.0, "validated": True if p["source"] == "Appelo2015" else False}
            for p in params
        ]
    }
    
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 Сохранено в {OUTPUT_JSON}")

if __name__ == "__main__":
    main()