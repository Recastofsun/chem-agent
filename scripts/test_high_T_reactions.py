"""Проверка высокотемпературных реакций из holdout (W-02 влияние)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chem_agent.agent import Agent


def run_test(name, request, expected_main):
    agent = Agent(offline=True)
    res = agent.predict(request=request)
    data = res.data
    actual = data.get("summary", {}).get("main_product")
    ok = (actual == expected_main) or (expected_main is None and actual is None)
    status = "✅" if ok else "❌"
    print(f"{status} {name}")
    print(f"   Ожидалось: {expected_main}, Получено: {actual} (статус: {data.get('status')})")
    if data.get("balanced_equations"):
        print(f"   Уравнение: {data['balanced_equations'][0]['equation']}")
    return ok


def main():
    results = []

    # h051: CaCO3 -> CaO при 1200 K (сухая, открытая)
    results.append(run_test(
        "h051: CaCO3 -> CaO (1200 K)",
        {"reagents": [{"formula": "CaCO3", "moles": 0.1, "phase": "s"}],
         "conditions": {"temperature_K": 1200.0, "solvent": {"name": "none"}}},
        "CaO"
    ))

    # h052: MgCO3 -> MgO при 800 K
    results.append(run_test(
        "h052: MgCO3 -> MgO (800 K)",
        {"reagents": [{"formula": "MgCO3", "moles": 0.1, "phase": "s"}],
         "conditions": {"temperature_K": 800.0, "solvent": {"name": "none"}}},
        "MgO"
    ))

    # h053: Cu(OH)2 -> CuO при 500 K
    results.append(run_test(
        "h053: Cu(OH)2 -> CuO (500 K)",
        {"reagents": [{"formula": "Cu(OH)2", "moles": 0.1, "phase": "s"}],
         "conditions": {"temperature_K": 500.0, "solvent": {"name": "none"}}},
        "CuO"
    ))

    # h058: CaCO3 при 700 K — НЕ разлагается (ниже порога)
    results.append(run_test(
        "h058: CaCO3 (700 K, должен быть устойчив)",
        {"reagents": [{"formula": "CaCO3", "moles": 0.1, "phase": "s"}],
         "conditions": {"temperature_K": 700.0, "solvent": {"name": "none"}}},
        None
    ))

    # h059: Fe(OH)3 -> Fe2O3 при 500 K
    results.append(run_test(
        "h059: Fe(OH)3 -> Fe2O3 (500 K)",
        {"reagents": [{"formula": "Fe(OH)3", "moles": 0.1, "phase": "s"}],
         "conditions": {"temperature_K": 500.0, "solvent": {"name": "none"}}},
        "Fe2O3"
    ))

    # h078: CaCO3 -> CaO при 1200 K (дубликат h051)
    results.append(run_test(
        "h078: CaCO3 -> CaO (1200 K, дубликат h051)",
        {"reagents": [{"formula": "CaCO3", "moles": 0.1, "phase": "s"}],
         "conditions": {"temperature_K": 1200.0, "solvent": {"name": "none"}}},
        "CaO"
    ))

    print(f"\n=== ИТОГО: {sum(results)}/{len(results)} пройдено ===")


if __name__ == "__main__":
    main()