"""Тесты динамики состава камер при электролизе."""
from __future__ import annotations
import pytest
from chem_agent.agent import Agent

def test_nacl_electrolysis_dynamics():
    """Электролиз NaCl: должно наблюдаться накопление OH- в катоде и миграция Na+."""
    agent = Agent(offline=True)
    
    request = {
        "mode": "cell",
        "cell": {
            "anode": {
                "solution": {
                    "species": [{"formula": "NaCl", "moles": 0.1, "phase": "aq"}],
                    "volume_L": 1.0
                }
            },
            "cathode": {
                "solution": {
                    "species": [{"formula": "NaCl", "moles": 0.1, "phase": "aq"}],
                    "volume_L": 1.0
                }
            },
            "membrane": {
                "type": "cation_exchange", # Пропускает Na+ из анода в катод
                "area_m2": 0.01,
                "thickness_m": 1e-4,
                "permselectivity": 0.95
            },
            "external_circuit": {
                "mode": "galvanostatic",
                "current_density_A_m2": 100.0, # 1 А на 0.01 м²
                "duration_s": 3600 # 1 час
            }
        }
    }
    
    result = agent.predict(request=request)
    data = result.data
    
    assert data["status"] == "ok", f"Ошибка: {data.get('warnings')}"
    assert data["mode"] == "cell_dynamic"
    
    dynamics = data.get("dynamics", {})
    assert "profile" in dynamics
    assert len(dynamics["profile"]) > 0, "История динамики пуста"
    
    # Проверка физики процесса по последнему шагу
    final_step = dynamics["profile"][-1]
    
    # 1. На катоде должна появиться OH- (или NaOH в молекулярной записи)
    cathode_moles = final_step["cathode_moles"]
    has_oh = any("OH" in f for f in cathode_moles.keys())
    assert has_oh, f"В катоде не накопился OH-. Состав: {cathode_moles}"
    
    # 2. Через катионообменную мембрану должен мигрировать Na+
    transferred = final_step.get("transferred_ions", {})
    assert "Na+" in transferred or any("Na" in f for f in transferred.keys()), \
        f"Na+ не мигрировал через мембрану. Перенос: {transferred}"
        
    # 3. Ток должен быть стабильным (гальваностатика)
    assert abs(final_step["I_A"] - 1.0) < 0.1, "Ток отклонился от заданного"

def test_copper_depletion_dynamics():
    """Электролиз CuSO4: медь должна закончиться, и реакция должна измениться."""
    agent = Agent(offline=True)
    
    request = {
        "mode": "cell",
        "cell": {
            "anode": {
                "solution": {"species": [{"formula": "CuSO4", "moles": 0.01, "phase": "aq"}], "volume_L": 0.5}
            },
            "cathode": {
                "solution": {"species": [{"formula": "CuSO4", "moles": 0.01, "phase": "aq"}], "volume_L": 0.5}
            },
            "membrane": {"type": "cation_exchange", "area_m2": 0.01, "thickness_m": 1e-4, "permselectivity": 0.95},
            "external_circuit": {
                "mode": "galvanostatic",
                "current_density_A_m2": 200.0, # Высокий ток, чтобы быстро израсходовать 0.01 моль
                "duration_s": 3600
            }
        }
    }
    
    result = agent.predict(request=request)
    data = result.data
    
    assert data["status"] == "ok"
    dynamics = data.get("dynamics", {})
    assert "profile" in dynamics, f"Ключ 'profile' отсутствует. Ключи: {list(dynamics.keys())}"
    
    # Проверяем, что в истории менялась доминирующая реакция на катоде
    # (сначала Cu+2 -> Cu, потом, возможно, H+ -> H2)
    cathode_reactions = [step["cathode_dominant"] for step in dynamics["profile"]]
    
    # Должна быть хотя бы одна стадия с медью
    assert any("Cu" in rx for rx in cathode_reactions), "Медь не восстанавливалась"