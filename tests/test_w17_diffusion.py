"""Тесты W-17: диффузионный контроль в кинетике."""
from __future__ import annotations

import math

import pytest


class TestDiffusionRateConstant:
    """Тесты функции diffusion_rate_constant."""
    
    def test_typical_ions(self):
        """Типичные ионы (D ~ 1e-9, R ~ 5 Å): k_diff ~ 7.5e9 M^-1 s^-1."""
        from chem_agent.kinetics.eyring import diffusion_rate_constant
        
        k = diffusion_rate_constant(T=298.15, D_A=1e-9, D_B=1e-9, R_encounter=5e-10)
        assert 7e9 <= k <= 8e9, f"k_diff = {k:.2e}, ожидалось ~7.5e9"
    
    def test_proton_transfer_grotthuss(self):
        """Протонный перенос (Grotthuss): формула Смолуховского дает ~3.3e10,
        экспериментальное значение 1.4e11 (механизм Гротгуса, прыжковый перенос)."""
        from chem_agent.kinetics.eyring import diffusion_rate_constant
        
        # Для типичных ионов (D ~ 1e-9, R ~ 5 Å): k_diff ~ 7.5e9
        k = diffusion_rate_constant(T=298.15, D_A=1e-9, D_B=1e-9, R_encounter=5e-10)
        assert 7e9 <= k <= 8e9, f"k_diff = {k:.2e}, ожидалось ~7.5e9"
        
        # Для протонного переноса с аномально высоким D_H+:
        k_h = diffusion_rate_constant(T=298.15, D_A=9.3e-9, D_B=5.3e-9, R_encounter=3e-10)
        # Формула дает ~3.3e10, но реальное значение 1.4e11 (механизм Гротгуса)
        assert 3e10 <= k_h <= 4e10, f"k_diff = {k_h:.2e}, ожидалось ~3.3e10"
    
    def test_temperature_dependence(self):
        """При росте T коэффициенты диффузии растут, k_diff растёт."""
        from chem_agent.kinetics.eyring import diffusion_rate_constant
        
        # D растёт с T (приближённо D ~ T/η, где η — вязкость)
        k_298 = diffusion_rate_constant(T=298.15, D_A=1e-9, D_B=1e-9)
        k_350 = diffusion_rate_constant(T=350.0, D_A=1.5e-9, D_B=1.5e-9)
        
        assert k_350 > k_298, f"k_diff(350K)={k_350} должно быть > k_diff(298K)={k_298}"


class TestCombinedRateConstant:
    """Тесты функции combined_rate_constant."""
    
    def test_activation_controlled(self):
        """При k_act << k_diff: k_obs ≈ k_act (активационный контроль)."""
        from chem_agent.kinetics.eyring import combined_rate_constant
        
        k_act = 1e5
        k_diff = 1e11
        
        k_obs = combined_rate_constant(k_act, k_diff)
        assert abs(k_obs - k_act) / k_act < 0.01, f"k_obs = {k_obs}, ожидалось ~{k_act}"
    
    def test_diffusion_controlled(self):
        """При k_act >> k_diff: k_obs ≈ k_diff (диффузионный контроль)."""
        from chem_agent.kinetics.eyring import combined_rate_constant
        
        k_act = 1e15
        k_diff = 1e10
        
        k_obs = combined_rate_constant(k_act, k_diff)
        assert abs(k_obs - k_diff) / k_diff < 0.01, f"k_obs = {k_obs}, ожидалось ~{k_diff}"
    
    def test_mixed_control(self):
        """При k_act ≈ k_diff: k_obs ≈ k_act/2."""
        from chem_agent.kinetics.eyring import combined_rate_constant
        
        k_act = 1e10
        k_diff = 1e10
        
        k_obs = combined_rate_constant(k_act, k_diff)
        assert abs(k_obs - 5e9) / 5e9 < 0.01, f"k_obs = {k_obs}, ожидалось ~5e9"
    
    def test_invalid_values(self):
        """Отрицательные или нулевые значения должны вызывать ошибку."""
        from chem_agent.kinetics.eyring import combined_rate_constant
        
        with pytest.raises(ValueError):
            combined_rate_constant(0, 1e10)
        
        with pytest.raises(ValueError):
            combined_rate_constant(1e10, -1)


class TestBarrierResolveDiffusion:
    """Интеграция resolve() с диффузионным контролем."""
    
    def test_proton_transfer_unchanged(self):
        """Протонный перенос работает как раньше (k = 1.4e11)."""
        from chem_agent.kinetics.barrier import resolve, PROTON_TRANSFER_K
        
        result = resolve(None, 298.15, "proton_transfer")
        assert result.rate_constant == PROTON_TRANSFER_K
        assert "diffusion" in result.model.lower()
    
    def test_acid_base_diffusion_limit(self):
        """Кислотно-основные реакции: диффузионный контроль."""
        from chem_agent.kinetics.barrier import resolve, TYPICAL_ION_DIFFUSION_K
        
        result = resolve(None, 298.15, "acid_base")
        assert result.rate_constant is not None
        assert result.rate_constant > 0
        assert "diffusion" in result.model.lower()
    
    def test_precipitation_diffusion_limit(self):
        """Осаждение: диффузионный контроль."""
        from chem_agent.kinetics.barrier import resolve, TYPICAL_ION_DIFFUSION_K
        
        result = resolve(None, 298.15, "precipitation")
        assert result.rate_constant is not None
        assert result.rate_constant > 0
        assert "diffusion" in result.model.lower()
    
    def test_combined_with_barrier_params(self):
        """Если задан барьер из БД, комбинирование с k_diff для быстрых реакций."""
        from chem_agent.kinetics.barrier import resolve, TYPICAL_ION_DIFFUSION_K
        
        # Маленький барьер (быстрая реакция)
        params = {
            "ea_kj_mol": 10.0,  # очень маленький барьер
            "t_ref": 298.15,
            "dh_act_kj_mol": None,
            "ds_act_j_mol_k": None,
            "t_ref_2": None,
            "ea_t2_kj_mol": None,
        }
        
        result = resolve(None, 298.15, "acid_base", barrier_params=params)
        assert result.rate_constant is not None
        # k_obs должно быть меньше k_diff (т.к. k_act конечен)
        assert result.rate_constant <= TYPICAL_ION_DIFFUSION_K * 1.1, \
            f"k_obs = {result.rate_constant:.2e}, k_diff = {TYPICAL_ION_DIFFUSION_K:.2e}"
    
    def test_slow_reaction_no_diffusion(self):
        """Медленные реакции (other) не используют диффузионный контроль."""
        from chem_agent.kinetics.barrier import resolve
        
        params = {
            "ea_kj_mol": 100.0,  # большой барьер
            "t_ref": 298.15,
            "dh_act_kj_mol": None,
            "ds_act_j_mol_k": None,
            "t_ref_2": None,
            "ea_t2_kj_mol": None,
        }
        
        result = resolve(None, 298.15, "other", barrier_params=params)
        assert result.rate_constant is not None
        # Для "other" диффузионный контроль не применяется
        assert "diffusion" not in result.model.lower()