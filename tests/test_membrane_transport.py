"""Тесты мембранного транспорта (уравнение Нернста-Планка)."""
from __future__ import annotations
import math
import pytest
from chem_agent.electrochem.membrane import Membrane, ion_flux, update_chambers


class TestIonFlux:
    """Тесты функции ion_flux."""
    
    def test_diffusion_only(self):
        """Чистая диффузия (Δφ = 0): поток от высокой концентрации к низкой."""
        membrane = Membrane(type="porous", thickness_m=1e-4)
        J = ion_flux("Na+", 1, 1000.0, 100.0, 0.0, 298.15, membrane)
        assert J > 0, "Поток должен быть от анода (1000) к катоду (100)"
        # D_Na = 1.3e-9, dC = 900, thickness = 1e-4
        # J = 1.3e-9 / 1e-4 * 900 = 0.0117
        assert abs(J - 0.0117) < 0.001
    
    def test_migration_cation(self):
        """Катион в электрическом поле: движется к катоду (отрицательный электрод)."""
        membrane = Membrane(type="non_selective", thickness_m=1e-4)
        # Анод при +1V, катод при -1V, Δφ = 2V
        J = ion_flux("Na+", 1, 500.0, 500.0, 2.0, 298.15, membrane)
        assert J < 0, "Катион должен двигаться от анода к катоду (отрицательный поток)"
    
    def test_migration_anion(self):
        """Анион в электрическом поле: движется к аноду (положительный электрод)."""
        membrane = Membrane(type="non_selective", thickness_m=1e-4)
        J = ion_flux("Cl-", -1, 500.0, 500.0, 2.0, 298.15, membrane)
        assert J > 0, "Анион должен двигаться от катода к аноду (положительный поток)"
    
    def test_cem_blocks_anion(self):
        """Катионообменная мембрана блокирует анионы."""
        membrane = Membrane(type="CEM", permselectivity=0.95, thickness_m=1e-4)
        J_cem = ion_flux("Cl-", -1, 1000.0, 100.0, 0.0, 298.15, membrane)
        J_non = ion_flux("Cl-", -1, 1000.0, 100.0, 0.0, 298.15, Membrane(type="porous", thickness_m=1e-4))
        # CEM: selectivity = 0.05, porous: selectivity = 1.0
        assert abs(J_cem) < abs(J_non) * 0.1, f"CEM должна блокировать анионы: J_cem={J_cem}, J_non={J_non}"
    
    def test_aem_blocks_cation(self):
        """Анионообменная мембрана блокирует катионы."""
        membrane = Membrane(type="AEM", permselectivity=0.95, thickness_m=1e-4)
        J_aem = ion_flux("Na+", 1, 1000.0, 100.0, 0.0, 298.15, membrane)
        J_non = ion_flux("Na+", 1, 1000.0, 100.0, 0.0, 298.15, Membrane(type="porous", thickness_m=1e-4))
        assert abs(J_aem) < abs(J_non) * 0.1, f"AEM должна блокировать катионы: J_aem={J_aem}, J_non={J_non}"


class TestUpdateChambers:
    """Тесты функции update_chambers."""
    
    def test_concentration_change(self):
        """Концентрации должны измениться после транспорта."""
        membrane = Membrane(type="non_selective", area_m2=0.01, thickness_m=1e-4)
        anode = {"Na+": 1000.0, "Cl-": 1000.0}
        cathode = {"Na+": 100.0, "Cl-": 100.0}
        charges = {"Na+": 1, "Cl-": -1}
        
        new_anode, new_cathode, transfers = update_chambers(
            anode, cathode, charges, 0.0, 298.15, membrane, 3600.0, 1e-3, 1e-3
        )
        
        assert new_anode["Na+"] < 1000.0, "Na+ должен уйти из анода"
        assert new_cathode["Na+"] > 100.0, "Na+ должен прийти в катод"
        assert "Na+" in transfers
    
    def test_charge_balance(self):
        """Суммарный заряд должен сохраняться."""
        membrane = Membrane(type="non_selective", area_m2=0.01, thickness_m=1e-4)
        anode = {"Na+": 1000.0, "Cl-": 1000.0}
        cathode = {"Na+": 100.0, "Cl-": 100.0}
        charges = {"Na+": 1, "Cl-": -1}
        
        new_anode, new_cathode, transfers = update_chambers(
            anode, cathode, charges, 0.0, 298.15, membrane, 3600.0, 1e-3, 1e-3
        )
        
        # Суммарный заряд в системе должен сохраниться
        total_charge_before = (1000.0 * 1 + 1000.0 * (-1) + 100.0 * 1 + 100.0 * (-1)) * 1e-3
        total_charge_after = (
            new_anode["Na+"] * 1 + new_anode["Cl-"] * (-1) +
            new_cathode["Na+"] * 1 + new_cathode["Cl-"] * (-1)
        ) * 1e-3
        assert abs(total_charge_before - total_charge_after) < 1e-6