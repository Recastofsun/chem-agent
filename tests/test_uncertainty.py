import math
import pytest
from chem_agent.agent import Agent

@pytest.fixture
def agent():
    return Agent(offline=True)

def test_uncertainty_grows_with_temperature(agent):
    """W-02: Ошибка должна расти при высоких T из-за Cp-интеграции."""
    reag = [{"formula": "CaCO3", "moles": 0.1, "phase": "s"}]
    
    # 1. Считаем при 1200 K (реакция уже точно идет)
    a1200 = agent.predict(
        reagents=reag, 
        conditions={"temperature_K": 1200.0, "solvent": "none"},
        options={"include_uncertainty": False, "include_kinetics": False}
    ).data
    assert a1200["balanced_equations"], "При 1200 K реакция должна идти"
    sigma_1200 = a1200["balanced_equations"][0]["delta_G_uncertainty"]
    
    # 2. Считаем при 1500 K (Cp-интеграция дает больший вклад)
    a1500 = agent.predict(
        reagents=reag, 
        conditions={"temperature_K": 1500.0, "solvent": "none"},
        options={"include_uncertainty": False, "include_kinetics": False}
    ).data
    assert a1500["balanced_equations"], "При 1500 K реакция должна идти"
    sigma_1500 = a1500["balanced_equations"][0]["delta_G_uncertainty"]
    
    # 3. Проверяем, что ошибка выросла
    assert sigma_1500 > sigma_1200, f"Ошибка при 1500K ({sigma_1500}) должна быть больше, чем при 1200K ({sigma_1200})"

def test_covariance_reduces_uncertainty(agent):
    """W-28: Ковариация должна уменьшать ошибку для реакций внутри одного справочника."""
    # Реакция разложения CaCO3 -> CaO + CO2 (все из CRC)
    reag = [{"formula": "CaCO3", "moles": 0.1, "phase": "s"}]
    
    res = agent.predict(
        reagents=reag, 
        conditions={"temperature_K": 1200.0, "solvent": "none"},
        options={"include_uncertainty": False, "include_kinetics": False}
    ).data
    
    assert res["balanced_equations"], "При 1200 K реакция должна идти"
    sigma = res["balanced_equations"][0]["delta_G_uncertainty"]
    
    # Без ковариации (независимые ошибки по 1 кДж/моль для 3 веществ) было бы sqrt(3) = 1.732
    # С ковариацией (rho=0.9) перекрестные члены сокращаются, ошибка должна быть меньше
    assert sigma < 1.732, f"Ковариация не сработала, ошибка слишком велика: {sigma}"

def test_bayesian_95_ci(agent):
    """W-35: Проверка наличия 95% доверительных интервалов в summary."""
    req = {
        "reagents": [
            {"formula": "CaCl2", "moles": 0.05, "phase": "aq"},
            {"formula": "Na2CO3", "moles": 0.05, "phase": "aq"}
        ],
        "conditions": {"temperature_K": 298.15, "solvent": {"name": "water"}, "volume_L": 1.0},
        "options": {"include_uncertainty": True, "uncertainty_method": "ensemble", "accuracy": "fast"}
    }
    
    res = agent.predict(request=req)
    summary = res.data.get("summary", {})
    
    # Проверяем, что новые ключи появились и интервалы не пустые
    assert "pH_95_CI" in summary
    assert summary["pH_95_CI"] is not None
    assert len(summary["pH_95_CI"]) == 2
    
    assert "delta_G_95_CI" in summary
    assert summary["delta_G_95_CI"] is not None
    
    # Проверяем логику: нижняя граница должна быть меньше верхней
    if summary.get("pH_95_CI"):
        assert summary["pH_95_CI"][0] <= summary["pH_95_CI"][1], "Нижняя граница pH CI больше верхней"
        
    if summary.get("delta_G_95_CI"):
        assert summary["delta_G_95_CI"][0] <= summary["delta_G_95_CI"][1], "Нижняя граница dG CI больше верхней"