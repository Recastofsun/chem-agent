"""Тесты W-13: температурная зависимость Ea(T)."""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CRC_DB = ROOT / "chem_agent" / "data" / "crc.db"


class TestEyringExtended:
    """Тесты расширенных функций уравнения Эйринга."""
    
    def test_rate_constant_eyring_basic(self):
        from chem_agent.kinetics.eyring import rate_constant_eyring
        k = rate_constant_eyring(50.0, -50.0, 298.15)
        assert k > 0 and math.isfinite(k)
    
    def test_rate_constant_eyring_temperature_dependence(self):
        from chem_agent.kinetics.eyring import rate_constant_eyring
        k_298 = rate_constant_eyring(50.0, -50.0, 298.15)
        k_350 = rate_constant_eyring(50.0, -50.0, 350.0)
        k_400 = rate_constant_eyring(50.0, -50.0, 400.0)
        assert k_350 > k_298 and k_400 > k_350
    
    def test_ea_at_temperature_interpolation(self):
        from chem_agent.kinetics.eyring import ea_at_temperature
        ea_350 = ea_at_temperature(40.0, 300.0, 45.0, 400.0, 350.0)
        assert abs(ea_350 - 42.5) < 1e-6
    
    def test_ea_at_temperature_extrapolation(self):
        from chem_agent.kinetics.eyring import ea_at_temperature
        assert ea_at_temperature(40.0, 300.0, 45.0, 400.0, 250.0) < 40.0
        assert ea_at_temperature(40.0, 300.0, 45.0, 400.0, 500.0) > 45.0
    
    def test_dh_ds_from_ea_roundtrip(self):
        from chem_agent.kinetics.eyring import dh_ds_from_ea, rate_constant, rate_constant_eyring
        ea = 50.0
        t_ref = 298.15
        dh, ds = dh_ds_from_ea(ea, t_ref)
        k_ea = rate_constant(ea, t_ref)
        k_dh_ds = rate_constant_eyring(dh, ds, t_ref)
        assert abs(k_ea - k_dh_ds) / k_ea < 0.01
    
    def test_ea_from_dh_ds(self):
        from chem_agent.kinetics.eyring import ea_from_dh_ds, R_KJ
        ea = ea_from_dh_ds(50.0, 0.0, 298.15)
        assert abs(ea - (50.0 + R_KJ * 298.15)) < 0.01


class TestDatabaseMigration:
    """Проверка миграции БД и формата get_barrier."""
    
    def test_kinetic_barriers_table_has_new_columns(self):
        con = sqlite3.connect(str(CRC_DB))
        cur = con.cursor()
        cur.execute("PRAGMA table_info(kinetic_barriers)")
        columns = {row[1] for row in cur.fetchall()}
        con.close()
        required = {"dh_act_kj_mol", "ds_act_j_mol_k", "t_ref_2", "ea_t2_kj_mol"}
        assert required.issubset(columns), f"Отсутствуют колонки: {required - columns}"
    
    def test_get_barrier_returns_dict(self):
        """get_barrier возвращает dict с расширенными полями."""
        from chem_agent.energy.database import ThermoDB
        db = ThermoDB(str(CRC_DB))
        
        if not db.kinetic_barriers:
            pytest.skip("kinetic_barriers пуст")
        
        key = next(iter(db.kinetic_barriers))
        params = db.get_barrier(key)
        
        assert isinstance(params, dict)
        assert "ea_kj_mol" in params
        assert "dh_act_kj_mol" in params
        assert "ds_act_j_mol_k" in params
    
    def test_get_barrier_unknown_returns_none(self):
        from chem_agent.energy.database import ThermoDB
        db = ThermoDB(str(CRC_DB))
        assert db.get_barrier("nonexistent_reaction_key") is None
    
    def test_extended_fields_populated(self):
        """После миграции хотя бы некоторые записи имеют ΔH‡ и ΔS‡."""
        from chem_agent.energy.database import ThermoDB
        db = ThermoDB(str(CRC_DB))
        
        has_extended = any(
            p.get("dh_act_kj_mol") is not None 
            for p in db.kinetic_barriers.values()
        )
        assert has_extended, "Ни одна запись не имеет dh_act_kj_mol — миграция не выполнена"


class TestBarrierResolve:
    """Интеграция resolve() с расширенными параметрами."""
    
    def test_resolve_with_dh_ds(self):
        from chem_agent.kinetics.barrier import resolve
        params = {
            "ea_kj_mol": 50.0, "t_ref": 298.15,
            "dh_act_kj_mol": 47.5, "ds_act_j_mol_k": -30.0,
            "t_ref_2": None, "ea_t2_kj_mol": None,
        }
        result = resolve(None, 298.15, "other", barrier_params=params)
        assert result.rate_constant is not None and result.rate_constant > 0
        assert "ΔH‡" in result.model or "Eyring" in result.model
    
    def test_resolve_with_two_point_calibration(self):
        from chem_agent.kinetics.barrier import resolve
        params = {
            "ea_kj_mol": 40.0, "t_ref": 300.0,
            "dh_act_kj_mol": None, "ds_act_j_mol_k": None,
            "t_ref_2": 400.0, "ea_t2_kj_mol": 45.0,
        }
        r_300 = resolve(None, 300.0, "other", barrier_params=params)
        r_400 = resolve(None, 400.0, "other", barrier_params=params)
        assert r_300.rate_constant is not None and r_400.rate_constant is not None
        assert r_400.rate_constant > r_300.rate_constant
    
    def test_resolve_fallback_to_constant_ea(self):
        from chem_agent.kinetics.barrier import resolve
        params = {
            "ea_kj_mol": 50.0, "t_ref": 298.15,
            "dh_act_kj_mol": None, "ds_act_j_mol_k": None,
            "t_ref_2": None, "ea_t2_kj_mol": None,
        }
        result = resolve(None, 298.15, "other", barrier_params=params)
        assert result.rate_constant is not None
        assert result.barrier_kJ_mol == 50.0
    
    def test_resolve_proton_transfer_unchanged(self):
        from chem_agent.kinetics.barrier import resolve, PROTON_TRANSFER_K
        result = resolve(None, 298.15, "proton_transfer")
        assert result.rate_constant == PROTON_TRANSFER_K