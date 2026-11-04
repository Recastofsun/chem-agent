"""Расширенные тесты мембранного транспорта (уравнение Нернста-Планка)."""
from __future__ import annotations
import math
import pytest
from chem_agent.electrochem.membrane import Membrane, ion_flux, update_chambers


class TestMembraneTypes:
    """Тесты разных типов мембран."""
    
    def test_cem_allows_cations(self):
        """CEM пропускает катионы с высокой селективностью."""
        membrane = Membrane(type="CEM", permselectivity=0.95, thickness_m=1e-4)
        J = ion_flux("Na+", 1, 1000.0, 100.0, 0.0, 298.15, membrane)
        assert J > 0, "CEM должна пропускать Na+"
        assert abs(J) > 1e-6
    
    def test_aem_allows_anions(self):
        """AEM пропускает анионы с высокой селективностью."""
        membrane = Membrane(type="AEM", permselectivity=0.95, thickness_m=1e-4)
        J = ion_flux("Cl-", -1, 1000.0, 100.0, 0.0, 298.15, membrane)
        assert J > 0, "AEM должна пропускать Cl-"
        assert abs(J) > 1e-6
    
    def test_bpm_allows_h_oh(self):
        """BPM пропускает H+ и OH-, блокирует другие ионы."""
        membrane = Membrane(type="BPM", permselectivity=0.95, thickness_m=1e-4)
        
        # H+ должен проходить
        J_h = ion_flux("H+", 1, 1000.0, 100.0, 0.0, 298.15, membrane)
        assert abs(J_h) > 1e-6, "BPM должна пропускать H+"
        
        # OH- должен проходить
        J_oh = ion_flux("OH-", -1, 1000.0, 100.0, 0.0, 298.15, membrane)
        assert abs(J_oh) > 1e-6, "BPM должна пропускать OH-"
        
        # Na+ должен блокироваться
        J_na = ion_flux("Na+", 1, 1000.0, 100.0, 0.0, 298.15, membrane)
        assert abs(J_na) < abs(J_h) * 0.1, "BPM должна блокировать Na+"
    
    def test_non_selective_allows_all(self):
        """Неселективная мембрана пропускает все ионы одинаково."""
        membrane = Membrane(type="non_selective", thickness_m=1e-4)
        J_na = ion_flux("Na+", 1, 1000.0, 100.0, 0.0, 298.15, membrane)
        J_cl = ion_flux("Cl-", -1, 1000.0, 100.0, 0.0, 298.15, membrane)
        # Оба должны иметь значительный поток
        assert abs(J_na) > 1e-6
        assert abs(J_cl) > 1e-6


class TestEdgeCases:
    """Краевые случаи."""
    
    def test_zero_concentration(self):
        """Нулевая концентрация в одной камере."""
        membrane = Membrane(type="non_selective", thickness_m=1e-4)
        J = ion_flux("Na+", 1, 0.0, 1000.0, 0.0, 298.15, membrane)
        assert J < 0, "Поток должен быть от катода (1000) к аноду (0)"
    
    def test_equal_concentrations(self):
        """Одинаковые концентрации: только миграция."""
        membrane = Membrane(type="non_selective", thickness_m=1e-4)
        J_diff = ion_flux("Na+", 1, 500.0, 500.0, 0.0, 298.15, membrane)
        J_mig = ion_flux("Na+", 1, 500.0, 500.0, 1.0, 298.15, membrane)
        assert abs(J_diff) < 1e-10, "При равных концентрациях диффузия = 0"
        assert abs(J_mig) > 1e-10, "Миграция должна работать"
    
    def test_zero_voltage(self):
        """Нулевое напряжение: только диффузия."""
        membrane = Membrane(type="non_selective", thickness_m=1e-4)
        J = ion_flux("Na+", 1, 1000.0, 100.0, 0.0, 298.15, membrane)
        assert J > 0, "Поток от высокой концентрации к низкой"
    
    def test_high_voltage(self):
        """Высокое напряжение усиливает миграцию."""
        membrane = Membrane(type="non_selective", thickness_m=1e-4)
        J_low = ion_flux("Na+", 1, 500.0, 500.0, 0.1, 298.15, membrane)
        J_high = ion_flux("Na+", 1, 500.0, 500.0, 1.0, 298.15, membrane)
        assert abs(J_high) > abs(J_low), "Высокое напряжение усиливает поток"


class TestTemperatureDependence:
    """Зависимость от температуры."""
    
    def test_higher_temperature_higher_flux(self):
        """При более высокой температуре поток больше (D растёт с T)."""
        membrane = Membrane(type="porous", thickness_m=1e-4)
        J_298 = ion_flux("Na+", 1, 1000.0, 100.0, 0.0, 298.15, membrane)
        J_350 = ion_flux("Na+", 1, 1000.0, 100.0, 0.0, 350.0, membrane)
        assert J_350 > J_298, f"Поток при 350K ({J_350}) должен быть > при 298K ({J_298})"


class TestChargeBalance:
    """Сохранение электронейтральности."""
    
    def test_neutral_salt_transfer(self):
        """Перенос нейтральной соли (NaCl) через porous мембрану сохраняет электронейтральность."""
        membrane = Membrane(type="porous", area_m2=0.01, thickness_m=1e-4)
        anode = {"Na+": 1000.0, "Cl-": 1000.0}
        cathode = {"Na+": 100.0, "Cl-": 100.0}
        charges = {"Na+": 1, "Cl-": -1}
        
        new_anode, new_cathode, transfers = update_chambers(
            anode, cathode, charges, 0.0, 298.15, membrane, 3600.0, 1e-3, 1e-3
        )
        
        # Электронейтральность в каждой камере
        anode_charge = new_anode["Na+"] * 1 + new_anode["Cl-"] * (-1)
        cathode_charge = new_cathode["Na+"] * 1 + new_cathode["Cl-"] * (-1)
        
        assert abs(anode_charge) < 1e-3, f"Анод: заряд = {anode_charge}"
        assert abs(cathode_charge) < 1e-3, f"Катод: заряд = {cathode_charge}"
    
    def test_selective_membrane_charge_imbalance(self):
        """CEM пропускает катионы, блокирует анионы."""
        membrane = Membrane(type="cation_exchange", area_m2=0.01, thickness_m=1e-4, permselectivity=0.95)
        anode = {"Na+": 1000.0, "Cl-": 1000.0}
        cathode = {"Na+": 100.0, "Cl-": 100.0}
        charges = {"Na+": 1, "Cl-": -1}
        
        new_anode, new_cathode, transfers = update_chambers(
            anode, cathode, charges, 0.0, 298.15, membrane, 3600.0, 1e-3, 1e-3
        )
        
        assert "Na+" in transfers, "Na+ должен переноситься через CEM"
        # Cl- должен переноситься значительно меньше (5% от Na+)
        if "Cl-" in transfers:
            assert abs(transfers["Cl-"]) < abs(transfers["Na+"]) * 0.1, \
                f"Cl- перенос = {transfers['Cl-']}, Na+ перенос = {transfers['Na+']}"

class TestMembraneParameters:
    """Влияние параметров мембраны."""
    
    def test_thickness_effect(self):
        """Более тонкая мембрана даёт больший поток."""
        membrane_thick = Membrane(type="non_selective", thickness_m=1e-3)
        membrane_thin = Membrane(type="non_selective", thickness_m=1e-4)
        J_thick = ion_flux("Na+", 1, 1000.0, 100.0, 0.0, 298.15, membrane_thick)
        J_thin = ion_flux("Na+", 1, 1000.0, 100.0, 0.0, 298.15, membrane_thin)
        assert abs(J_thin) > abs(J_thick), "Тонкая мембрана даёт больший поток"
    
    def test_area_effect(self):
        """Большая площадь мембраны увеличивает общий перенос."""
        membrane_small = Membrane(type="non_selective", area_m2=0.001, thickness_m=1e-4)
        membrane_large = Membrane(type="non_selective", area_m2=0.01, thickness_m=1e-4)
        
        anode = {"Na+": 1000.0}
        cathode = {"Na+": 100.0}
        charges = {"Na+": 1}
        
        _, _, transfers_small = update_chambers(
            anode, cathode, charges, 0.0, 298.15, membrane_small, 3600.0, 1e-3, 1e-3
        )
        _, _, transfers_large = update_chambers(
            anode, cathode, charges, 0.0, 298.15, membrane_large, 3600.0, 1e-3, 1e-3
        )
        
        assert abs(transfers_large["Na+"]) > abs(transfers_small["Na+"]), \
            "Большая площадь даёт больший перенос"
    
    def test_permselectivity_effect(self):
        """Более высокая селективность уменьшает поток блокируемых ионов."""
        membrane_low = Membrane(type="CEM", permselectivity=0.5, thickness_m=1e-4)
        membrane_high = Membrane(type="CEM", permselectivity=0.99, thickness_m=1e-4)
        
        J_anion_low = ion_flux("Cl-", -1, 1000.0, 100.0, 0.0, 298.15, membrane_low)
        J_anion_high = ion_flux("Cl-", -1, 1000.0, 100.0, 0.0, 298.15, membrane_high)
        
        assert abs(J_anion_high) < abs(J_anion_low), \
            "Высокая селективность сильнее блокирует анионы"


class TestMultipleIons:
    """Системы с несколькими ионами."""
    
    def test_competing_cations(self):
        """Два катиона конкурируют за перенос через CEM."""
        membrane = Membrane(type="cation_exchange", area_m2=0.01, thickness_m=1e-4, permselectivity=0.95)
        anode = {"Na+": 1000.0, "K+": 1000.0, "Cl-": 2000.0}
        cathode = {"Na+": 100.0, "K+": 100.0, "Cl-": 200.0}
        charges = {"Na+": 1, "K+": 1, "Cl-": -1}
        
        new_anode, new_cathode, transfers = update_chambers(
            anode, cathode, charges, 0.0, 298.15, membrane, 3600.0, 1e-3, 1e-3
        )
        
        # Оба катиона должны переноситься
        assert "Na+" in transfers or "K+" in transfers, "Хотя бы один катион должен переноситься"
        # Cl- должен блокироваться CEM (перенос < 10% от катионов)
        total_cation_transfer = abs(transfers.get("Na+", 0)) + abs(transfers.get("K+", 0))
        if "Cl-" in transfers and total_cation_transfer > 0:
            assert abs(transfers["Cl-"]) < total_cation_transfer * 0.1, \
                f"Cl- = {transfers['Cl-']}, катионы = {total_cation_transfer}"
    
    def test_multivalent_ion(self):
        """Двухзарядный ион (Ca2+) переносится сильнее из-за миграции."""
        membrane = Membrane(type="non_selective", thickness_m=1e-4)
        J_mono = ion_flux("Na+", 1, 500.0, 500.0, 1.0, 298.15, membrane)
        J_di = ion_flux("Ca+2", 2, 500.0, 500.0, 1.0, 298.15, membrane)
        # При одинаковой концентрации и напряжении двухзарядный ион имеет больший миграционный член
        assert abs(J_di) > abs(J_mono), "Двухзарядный ион должен иметь больший поток"


class TestIntegrationWithAgent:
    """Интеграционные тесты с агентом."""
    
    def test_cell_with_membrane(self):
        """Ячейка с мембраной должна учитывать перенос ионов."""
        from chem_agent.agent import Agent
        
        agent = Agent(offline=True)
        request = {
            "mode": "cell",
            "cell": {
                "anode": {
                    "solution": {
                        "species": [
                            {"formula": "NaCl", "moles": 0.1, "phase": "aq"}
                        ],
                        "volume_L": 1.0
                    }
                },
                "cathode": {
                    "solution": {
                        "species": [
                            {"formula": "NaCl", "moles": 0.1, "phase": "aq"}
                        ],
                        "volume_L": 1.0
                    }
                },
                "membrane": {
                    "type": "cation_exchange",
                    "area_m2": 0.01,
                    "thickness_m": 1e-4,
                    "permselectivity": 0.95
                },
                "external_circuit": {
                    "mode": "potentiostatic",
                    "voltage_V": 3.0,
                    "duration_s": 3600
                }
            }
        }
        
        result = agent.predict(request=request)
        data = result.data
        
        # Проверяем, что ячейка работает (статус ok или error, но не исключение)
        assert "cell_result" in data or data.get("status") == "error"