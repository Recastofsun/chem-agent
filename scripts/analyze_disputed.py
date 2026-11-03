"""Глубокий анализ расхождений в pool_disputed_1000.json.
Для каждой реакции запускает модель и сравнивает с эталоном.
Классифицирует причины: нехватка данных, термодинамический спор, кинетические правила.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import json
from chem_agent.agent import Agent
from chem_agent.energy.database import get_db

POOL_PATH = ROOT / "data" / "pool_1000.json"
DISPUTED_PATH = ROOT / "data" / "pool_disputed_1000.json"


def analyze_disputed():
    if not POOL_PATH.exists() or not DISPUTED_PATH.exists():
        print("❌ Файлы pool_1000.json или pool_disputed_1000.json не найдены.")
        return
    
    with open(POOL_PATH, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    
    with open(DISPUTED_PATH, 'r', encoding='utf-8') as f:
        disputed_raw = json.load(f)
    
    # Нормализация: поддерживаем и список строк, и список dict
    disputed_ids = []
    for item in disputed_raw:
        if isinstance(item, dict):
            r_id = item.get("id")
        else:
            r_id = item
        if r_id:
            disputed_ids.append(r_id)
    
    pool_dict = {r["id"]: r for r in pool}
    
    print(f"🔍 Глубокий анализ {len(disputed_ids)} расхождений")
    print("   Для каждой реакции запускаем модель и сравниваем с эталоном\n")
    print("=" * 90)
    
    agent = Agent(offline=True)
    db = get_db()
    
    categories = {
        "missing_data": [],
        "model_predicts_no_reaction": [],
        "model_predicts_different": [],
        "model_predicts_correct": [],
        "unknown": []
    }
    
    for r_id in disputed_ids:
        reaction = pool_dict.get(r_id)
        if not reaction:
            print(f"⚠️  Реакция {r_id} не найдена в pool_1000.json")
            categories["unknown"].append({"id": r_id, "reason": "не найдена в pool"})
            continue
        
        # ИСПРАВЛЕНО: правильное имя поля
        reagents = reaction.get("reagents", [])
        expected_main = reaction.get("expected_main", "")
        
        if not reagents:
            categories["unknown"].append({"id": r_id, "reason": "пустой список reagents"})
            continue
        
        # Проверяем наличие данных в БД
        missing_species = []
        for r in reagents:
            formula = r.get("formula")
            phase = r.get("phase", "aq")
            species = db.find_formula(formula, phase)
            if not species or species[0].dGf is None:
                missing_species.append(f"{formula}({phase})")
        
        if missing_species:
            categories["missing_data"].append({
                "id": r_id,
                "reagents": [r["formula"] for r in reagents],
                "expected": expected_main,
                "missing": missing_species
            })
            continue
        
        # Запускаем модель
        try:
            conditions = {"solvent": "water", "volume_L": 1.0}
            if "conditions" in reaction and "temperature_K" in reaction["conditions"]:
                conditions["temperature_K"] = reaction["conditions"]["temperature_K"]

            request = {
                "reagents": reagents,
                "conditions": conditions,
                "options": {"accuracy": "fast", "include_uncertainty": False}
            }
            result = agent.predict(request=request)
            data = result.data
            
            if data.get("status") == "error":
                categories["unknown"].append({
                    "id": r_id,
                    "reason": f"ошибка модели: {data.get('message', '')}"
                })
                continue
            
            products = data.get("products", [])
            predicted_main = products[0]["formula"] if products else None
            reaction_occurred = data.get("status") == "ok"
            
            # Сравниваем с эталоном
            if not reaction_occurred:
                categories["model_predicts_no_reaction"].append({
                    "id": r_id,
                    "reagents": [r["formula"] for r in reagents],
                    "expected": expected_main,
                    "model_says": "реакция не идет"
                })
            elif predicted_main == expected_main:
                categories["model_predicts_correct"].append({
                    "id": r_id,
                    "reagents": [r["formula"] for r in reagents],
                    "expected": expected_main,
                    "predicted": predicted_main,
                    "note": "модель предсказывает верно — расхождение в другом продукте?"
                })
            else:
                categories["model_predicts_different"].append({
                    "id": r_id,
                    "reagents": [r["formula"] for r in reagents],
                    "expected": expected_main,
                    "predicted": predicted_main,
                    "delta_G": data.get("summary", {}).get("delta_G_kJ_mol")
                })
        except Exception as e:
            categories["unknown"].append({
                "id": r_id,
                "reason": f"исключение: {e}"
            })
    
    # Вывод отчетов
    print(f"\n📊 ИТОГОВАЯ КЛАССИФИКАЦИЯ:")
    print(f"   • Нехватка данных в БД: {len(categories['missing_data'])}")
    print(f"   • Модель предсказывает 'нет реакции': {len(categories['model_predicts_no_reaction'])}")
    print(f"   • Модель предсказывает другой продукт: {len(categories['model_predicts_different'])}")
    print(f"   • Модель предсказывает верно (эталон упрощен): {len(categories['model_predicts_correct'])}")
    print(f"   • Неизвестно/ошибка: {len(categories['unknown'])}")
    print("=" * 90)
    
    if categories["missing_data"]:
        print("\n🔴 1. НЕХВАТКА ДАННЫХ (требуется добавление в crc.db):")
        for item in categories["missing_data"]:
            print(f"   [{item['id']}] {', '.join(item['reagents'])} -> {item['expected']}")
            print(f"      Отсутствуют: {', '.join(item['missing'])}")
    
    if categories["model_predicts_no_reaction"]:
        print("\n🟡 2. МОДЕЛЬ ГОВОРИТ 'НЕТ РЕАКЦИИ' (эталон ожидает продукт):")
        for item in categories["model_predicts_no_reaction"]:
            print(f"   [{item['id']}] {', '.join(item['reagents'])} -> {item['expected']}")
            print(f"      Модель: {item['model_says']}")
    
    if categories["model_predicts_different"]:
        print("\n🔵 3. МОДЕЛЬ ПРЕДСКАЗЫВАЕТ ДРУГОЙ ПРОДУКТ:")
        for item in categories["model_predicts_different"]:
            print(f"   [{item['id']}] {', '.join(item['reagents'])}")
            print(f"      Ожидалось: {item['expected']}")
            print(f"      Модель:    {item['predicted']}")
            if item.get("delta_G") is not None:
                print(f"      ΔG = {item['delta_G']:.1f} кДж/моль")
    
    if categories["model_predicts_correct"]:
        print("\n🟢 4. МОДЕЛЬ ПРЕДСКАЗЫВАЕТ ВЕРНО (эталон упрощен или ошибка в disputed):")
        for item in categories["model_predicts_correct"]:
            print(f"   [{item['id']}] {', '.join(item['reagents'])} -> {item['expected']}")
            print(f"      Модель тоже предсказывает: {item['predicted']}")
            print(f"      {item['note']}")
    
    if categories["unknown"]:
        print("\n⚪ 5. НЕИЗВЕСТНО/ОШИБКА:")
        for item in categories["unknown"]:
            print(f"   [{item['id']}] {item['reason']}")
    
    print("=" * 90)
    print("💡 РЕКОМЕНДАЦИЯ: Разберем каждую категорию по очереди.")


if __name__ == "__main__":
    analyze_disputed()