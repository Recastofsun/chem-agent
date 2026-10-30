"""Автоматически сгенерированные тесты для новых веществ (W-26)."""
import pytest
from chem_agent.agent import Agent


@pytest.fixture
def agent_staging():
    """Agent с staging.db для тестирования новых веществ."""
    return Agent(offline=True, db_path='chem_agent/data/staging.db')


class TestNewSpeciesPresence:
    """Unit-тесты: проверка наличия новых веществ в БД."""

    def test_nh4so4_aq_exists(self, agent_staging):
        """Проверка наличия NH4SO4-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "NH4SO4-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"NH4SO4-(aq) не найден в staging.db"

    def test_caco3_aq_exists(self, agent_staging):
        """Проверка наличия CaCO3(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CaCO3" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CaCO3(aq) не найден в staging.db"

    def test_cahco3_aq_exists(self, agent_staging):
        """Проверка наличия CaHCO3+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CaHCO3+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CaHCO3+(aq) не найден в staging.db"

    def test_caso4_aq_exists(self, agent_staging):
        """Проверка наличия CaSO4(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CaSO4" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CaSO4(aq) не найден в staging.db"

    def test_cahso4_aq_exists(self, agent_staging):
        """Проверка наличия CaHSO4+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CaHSO4+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CaHSO4+(aq) не найден в staging.db"

    def test_capo4_aq_exists(self, agent_staging):
        """Проверка наличия CaPO4-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CaPO4-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CaPO4-(aq) не найден в staging.db"

    def test_cahpo4_aq_exists(self, agent_staging):
        """Проверка наличия CaHPO4(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CaHPO4" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CaHPO4(aq) не найден в staging.db"

    def test_cah2po4_aq_exists(self, agent_staging):
        """Проверка наличия CaH2PO4+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CaH2PO4+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CaH2PO4+(aq) не найден в staging.db"

    def test_mgco3_aq_exists(self, agent_staging):
        """Проверка наличия MgCO3(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "MgCO3" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"MgCO3(aq) не найден в staging.db"

    def test_mghco3_aq_exists(self, agent_staging):
        """Проверка наличия MgHCO3+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "MgHCO3+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"MgHCO3+(aq) не найден в staging.db"

    def test_mgso4_aq_exists(self, agent_staging):
        """Проверка наличия MgSO4(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "MgSO4" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"MgSO4(aq) не найден в staging.db"

    def test_mg_so4_2_2_aq_exists(self, agent_staging):
        """Проверка наличия Mg(SO4)2-2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Mg(SO4)2-2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Mg(SO4)2-2(aq) не найден в staging.db"

    def test_mgpo4_aq_exists(self, agent_staging):
        """Проверка наличия MgPO4-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "MgPO4-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"MgPO4-(aq) не найден в staging.db"

    def test_mghpo4_aq_exists(self, agent_staging):
        """Проверка наличия MgHPO4(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "MgHPO4" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"MgHPO4(aq) не найден в staging.db"

    def test_mgh2po4_aq_exists(self, agent_staging):
        """Проверка наличия MgH2PO4+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "MgH2PO4+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"MgH2PO4+(aq) не найден в staging.db"

    def test_mgf_aq_exists(self, agent_staging):
        """Проверка наличия MgF+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "MgF+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"MgF+(aq) не найден в staging.db"

    def test_naso4_aq_exists(self, agent_staging):
        """Проверка наличия NaSO4-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "NaSO4-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"NaSO4-(aq) не найден в staging.db"

    def test_nahpo4_aq_exists(self, agent_staging):
        """Проверка наличия NaHPO4-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "NaHPO4-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"NaHPO4-(aq) не найден в staging.db"

    def test_kso4_aq_exists(self, agent_staging):
        """Проверка наличия KSO4-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "KSO4-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"KSO4-(aq) не найден в staging.db"

    def test_khpo4_aq_exists(self, agent_staging):
        """Проверка наличия KHPO4-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "KHPO4-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"KHPO4-(aq) не найден в staging.db"

    def test_fecl_aq_exists(self, agent_staging):
        """Проверка наличия FeCl+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeCl+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeCl+(aq) не найден в staging.db"

    def test_feco3_aq_exists(self, agent_staging):
        """Проверка наличия FeCO3(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeCO3" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeCO3(aq) не найден в staging.db"

    def test_fehco3_aq_exists(self, agent_staging):
        """Проверка наличия FeHCO3+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeHCO3+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeHCO3+(aq) не найден в staging.db"

    def test_feso4_aq_exists(self, agent_staging):
        """Проверка наличия FeSO4(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeSO4" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeSO4(aq) не найден в staging.db"

    def test_fehso4_aq_exists(self, agent_staging):
        """Проверка наличия FeHSO4+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeHSO4+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeHSO4+(aq) не найден в staging.db"

    def test_fe_hs_2_aq_exists(self, agent_staging):
        """Проверка наличия Fe(HS)2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Fe(HS)2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Fe(HS)2(aq) не найден в staging.db"

    def test_fe_hs_3_aq_exists(self, agent_staging):
        """Проверка наличия Fe(HS)3-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Fe(HS)3-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Fe(HS)3-(aq) не найден в staging.db"

    def test_fehpo4_aq_exists(self, agent_staging):
        """Проверка наличия FeHPO4(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeHPO4" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeHPO4(aq) не найден в staging.db"

    def test_feh2po4_aq_exists(self, agent_staging):
        """Проверка наличия FeH2PO4+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeH2PO4+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeH2PO4+(aq) не найден в staging.db"

    def test_fef_aq_exists(self, agent_staging):
        """Проверка наличия FeF+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeF+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeF+(aq) не найден в staging.db"

    def test_fecl_2_aq_exists(self, agent_staging):
        """Проверка наличия FeCl+2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeCl+2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeCl+2(aq) не найден в staging.db"

    def test_fecl2_aq_exists(self, agent_staging):
        """Проверка наличия FeCl2+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeCl2+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeCl2+(aq) не найден в staging.db"

    def test_fecl3_aq_exists(self, agent_staging):
        """Проверка наличия FeCl3(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeCl3" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeCl3(aq) не найден в staging.db"

    def test_feso4_aq_exists(self, agent_staging):
        """Проверка наличия FeSO4+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeSO4+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeSO4+(aq) не найден в staging.db"

    def test_fehso4_2_aq_exists(self, agent_staging):
        """Проверка наличия FeHSO4+2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeHSO4+2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeHSO4+2(aq) не найден в staging.db"

    def test_fe_so4_2_aq_exists(self, agent_staging):
        """Проверка наличия Fe(SO4)2-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Fe(SO4)2-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Fe(SO4)2-(aq) не найден в staging.db"

    def test_fehpo4_aq_exists(self, agent_staging):
        """Проверка наличия FeHPO4+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeHPO4+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeHPO4+(aq) не найден в staging.db"

    def test_feh2po4_2_aq_exists(self, agent_staging):
        """Проверка наличия FeH2PO4+2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeH2PO4+2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeH2PO4+2(aq) не найден в staging.db"

    def test_fef_2_aq_exists(self, agent_staging):
        """Проверка наличия FeF+2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeF+2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeF+2(aq) не найден в staging.db"

    def test_fef2_aq_exists(self, agent_staging):
        """Проверка наличия FeF2+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeF2+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeF2+(aq) не найден в staging.db"

    def test_fef3_aq_exists(self, agent_staging):
        """Проверка наличия FeF3(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "FeF3" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"FeF3(aq) не найден в staging.db"

    def test_mncl_aq_exists(self, agent_staging):
        """Проверка наличия MnCl+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "MnCl+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"MnCl+(aq) не найден в staging.db"

    def test_mncl2_aq_exists(self, agent_staging):
        """Проверка наличия MnCl2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "MnCl2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"MnCl2(aq) не найден в staging.db"

    def test_mnco3_aq_exists(self, agent_staging):
        """Проверка наличия MnCO3(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "MnCO3" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"MnCO3(aq) не найден в staging.db"

    def test_mnhco3_aq_exists(self, agent_staging):
        """Проверка наличия MnHCO3+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "MnHCO3+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"MnHCO3+(aq) не найден в staging.db"

    def test_mnso4_aq_exists(self, agent_staging):
        """Проверка наличия MnSO4(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "MnSO4" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"MnSO4(aq) не найден в staging.db"

    def test_mn_no3_2_aq_exists(self, agent_staging):
        """Проверка наличия Mn(NO3)2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Mn(NO3)2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Mn(NO3)2(aq) не найден в staging.db"

    def test_mnf_aq_exists(self, agent_staging):
        """Проверка наличия MnF+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "MnF+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"MnF+(aq) не найден в staging.db"

    def test_also4_aq_exists(self, agent_staging):
        """Проверка наличия AlSO4+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "AlSO4+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"AlSO4+(aq) не найден в staging.db"

    def test_al_so4_2_aq_exists(self, agent_staging):
        """Проверка наличия Al(SO4)2-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Al(SO4)2-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Al(SO4)2-(aq) не найден в staging.db"

    def test_alhso4_2_aq_exists(self, agent_staging):
        """Проверка наличия AlHSO4+2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "AlHSO4+2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"AlHSO4+2(aq) не найден в staging.db"

    def test_alf_2_aq_exists(self, agent_staging):
        """Проверка наличия AlF+2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "AlF+2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"AlF+2(aq) не найден в staging.db"

    def test_alf2_aq_exists(self, agent_staging):
        """Проверка наличия AlF2+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "AlF2+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"AlF2+(aq) не найден в staging.db"

    def test_alf3_aq_exists(self, agent_staging):
        """Проверка наличия AlF3(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "AlF3" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"AlF3(aq) не найден в staging.db"

    def test_alf4_aq_exists(self, agent_staging):
        """Проверка наличия AlF4-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "AlF4-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"AlF4-(aq) не найден в staging.db"

    def test_baco3_aq_exists(self, agent_staging):
        """Проверка наличия BaCO3(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "BaCO3" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"BaCO3(aq) не найден в staging.db"

    def test_bahco3_aq_exists(self, agent_staging):
        """Проверка наличия BaHCO3+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "BaHCO3+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"BaHCO3+(aq) не найден в staging.db"

    def test_srhco3_aq_exists(self, agent_staging):
        """Проверка наличия SrHCO3+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "SrHCO3+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"SrHCO3+(aq) не найден в staging.db"

    def test_srco3_aq_exists(self, agent_staging):
        """Проверка наличия SrCO3(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "SrCO3" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"SrCO3(aq) не найден в staging.db"

    def test_srso4_aq_exists(self, agent_staging):
        """Проверка наличия SrSO4(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "SrSO4" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"SrSO4(aq) не найден в staging.db"

    def test_liso4_aq_exists(self, agent_staging):
        """Проверка наличия LiSO4-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "LiSO4-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"LiSO4-(aq) не найден в staging.db"

    def test_cucl2_aq_exists(self, agent_staging):
        """Проверка наличия CuCl2-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CuCl2-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CuCl2-(aq) не найден в staging.db"

    def test_cucl3_2_aq_exists(self, agent_staging):
        """Проверка наличия CuCl3-2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CuCl3-2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CuCl3-2(aq) не найден в staging.db"

    def test_cuco3_aq_exists(self, agent_staging):
        """Проверка наличия CuCO3(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CuCO3" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CuCO3(aq) не найден в staging.db"

    def test_cu_co3_2_2_aq_exists(self, agent_staging):
        """Проверка наличия Cu(CO3)2-2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Cu(CO3)2-2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Cu(CO3)2-2(aq) не найден в staging.db"

    def test_cuhco3_aq_exists(self, agent_staging):
        """Проверка наличия CuHCO3+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CuHCO3+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CuHCO3+(aq) не найден в staging.db"

    def test_cucl_aq_exists(self, agent_staging):
        """Проверка наличия CuCl+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CuCl+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CuCl+(aq) не найден в staging.db"

    def test_cucl2_aq_exists(self, agent_staging):
        """Проверка наличия CuCl2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CuCl2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CuCl2(aq) не найден в staging.db"

    def test_cuf_aq_exists(self, agent_staging):
        """Проверка наличия CuF+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CuF+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CuF+(aq) не найден в staging.db"

    def test_cuso4_aq_exists(self, agent_staging):
        """Проверка наличия CuSO4(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CuSO4" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CuSO4(aq) не найден в staging.db"

    def test_cu_hs_3_aq_exists(self, agent_staging):
        """Проверка наличия Cu(HS)3-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Cu(HS)3-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Cu(HS)3-(aq) не найден в staging.db"

    def test_zncl_aq_exists(self, agent_staging):
        """Проверка наличия ZnCl+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "ZnCl+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"ZnCl+(aq) не найден в staging.db"

    def test_zncl2_aq_exists(self, agent_staging):
        """Проверка наличия ZnCl2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "ZnCl2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"ZnCl2(aq) не найден в staging.db"

    def test_zncl3_aq_exists(self, agent_staging):
        """Проверка наличия ZnCl3-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "ZnCl3-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"ZnCl3-(aq) не найден в staging.db"

    def test_zncl4_2_aq_exists(self, agent_staging):
        """Проверка наличия ZnCl4-2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "ZnCl4-2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"ZnCl4-2(aq) не найден в staging.db"

    def test_zn_hs_2_aq_exists(self, agent_staging):
        """Проверка наличия Zn(HS)2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Zn(HS)2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Zn(HS)2(aq) не найден в staging.db"

    def test_zn_hs_3_aq_exists(self, agent_staging):
        """Проверка наличия Zn(HS)3-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Zn(HS)3-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Zn(HS)3-(aq) не найден в staging.db"

    def test_znco3_aq_exists(self, agent_staging):
        """Проверка наличия ZnCO3(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "ZnCO3" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"ZnCO3(aq) не найден в staging.db"

    def test_zn_co3_2_2_aq_exists(self, agent_staging):
        """Проверка наличия Zn(CO3)2-2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Zn(CO3)2-2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Zn(CO3)2-2(aq) не найден в staging.db"

    def test_znhco3_aq_exists(self, agent_staging):
        """Проверка наличия ZnHCO3+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "ZnHCO3+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"ZnHCO3+(aq) не найден в staging.db"

    def test_znso4_aq_exists(self, agent_staging):
        """Проверка наличия ZnSO4(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "ZnSO4" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"ZnSO4(aq) не найден в staging.db"

    def test_zn_so4_2_2_aq_exists(self, agent_staging):
        """Проверка наличия Zn(SO4)2-2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Zn(SO4)2-2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Zn(SO4)2-2(aq) не найден в staging.db"

    def test_znf_aq_exists(self, agent_staging):
        """Проверка наличия ZnF+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "ZnF+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"ZnF+(aq) не найден в staging.db"

    def test_cdno3_aq_exists(self, agent_staging):
        """Проверка наличия CdNO3+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CdNO3+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CdNO3+(aq) не найден в staging.db"

    def test_cdcl_aq_exists(self, agent_staging):
        """Проверка наличия CdCl+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CdCl+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CdCl+(aq) не найден в staging.db"

    def test_cdcl2_aq_exists(self, agent_staging):
        """Проверка наличия CdCl2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CdCl2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CdCl2(aq) не найден в staging.db"

    def test_cdcl3_aq_exists(self, agent_staging):
        """Проверка наличия CdCl3-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CdCl3-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CdCl3-(aq) не найден в staging.db"

    def test_cdco3_aq_exists(self, agent_staging):
        """Проверка наличия CdCO3(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CdCO3" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CdCO3(aq) не найден в staging.db"

    def test_cd_co3_2_2_aq_exists(self, agent_staging):
        """Проверка наличия Cd(CO3)2-2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Cd(CO3)2-2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Cd(CO3)2-2(aq) не найден в staging.db"

    def test_cdhco3_aq_exists(self, agent_staging):
        """Проверка наличия CdHCO3+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CdHCO3+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CdHCO3+(aq) не найден в staging.db"

    def test_cdso4_aq_exists(self, agent_staging):
        """Проверка наличия CdSO4(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CdSO4" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CdSO4(aq) не найден в staging.db"

    def test_cd_so4_2_2_aq_exists(self, agent_staging):
        """Проверка наличия Cd(SO4)2-2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Cd(SO4)2-2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Cd(SO4)2-2(aq) не найден в staging.db"

    def test_cdbr_aq_exists(self, agent_staging):
        """Проверка наличия CdBr+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CdBr+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CdBr+(aq) не найден в staging.db"

    def test_cdbr2_aq_exists(self, agent_staging):
        """Проверка наличия CdBr2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CdBr2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CdBr2(aq) не найден в staging.db"

    def test_cdf_aq_exists(self, agent_staging):
        """Проверка наличия CdF+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CdF+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CdF+(aq) не найден в staging.db"

    def test_cdf2_aq_exists(self, agent_staging):
        """Проверка наличия CdF2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CdF2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CdF2(aq) не найден в staging.db"

    def test_cdhs_aq_exists(self, agent_staging):
        """Проверка наличия CdHS+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "CdHS+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"CdHS+(aq) не найден в staging.db"

    def test_cd_hs_2_aq_exists(self, agent_staging):
        """Проверка наличия Cd(HS)2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Cd(HS)2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Cd(HS)2(aq) не найден в staging.db"

    def test_cd_hs_3_aq_exists(self, agent_staging):
        """Проверка наличия Cd(HS)3-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Cd(HS)3-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Cd(HS)3-(aq) не найден в staging.db"

    def test_cd_hs_4_2_aq_exists(self, agent_staging):
        """Проверка наличия Cd(HS)4-2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Cd(HS)4-2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Cd(HS)4-2(aq) не найден в staging.db"

    def test_pbcl_aq_exists(self, agent_staging):
        """Проверка наличия PbCl+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbCl+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbCl+(aq) не найден в staging.db"

    def test_pbcl2_aq_exists(self, agent_staging):
        """Проверка наличия PbCl2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbCl2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbCl2(aq) не найден в staging.db"

    def test_pbcl3_aq_exists(self, agent_staging):
        """Проверка наличия PbCl3-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbCl3-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbCl3-(aq) не найден в staging.db"

    def test_pbcl4_2_aq_exists(self, agent_staging):
        """Проверка наличия PbCl4-2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbCl4-2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbCl4-2(aq) не найден в staging.db"

    def test_pbco3_aq_exists(self, agent_staging):
        """Проверка наличия PbCO3(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbCO3" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbCO3(aq) не найден в staging.db"

    def test_pb_co3_2_2_aq_exists(self, agent_staging):
        """Проверка наличия Pb(CO3)2-2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Pb(CO3)2-2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Pb(CO3)2-2(aq) не найден в staging.db"

    def test_pbhco3_aq_exists(self, agent_staging):
        """Проверка наличия PbHCO3+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbHCO3+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbHCO3+(aq) не найден в staging.db"

    def test_pbso4_aq_exists(self, agent_staging):
        """Проверка наличия PbSO4(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbSO4" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbSO4(aq) не найден в staging.db"

    def test_pb_so4_2_2_aq_exists(self, agent_staging):
        """Проверка наличия Pb(SO4)2-2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Pb(SO4)2-2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Pb(SO4)2-2(aq) не найден в staging.db"

    def test_pb_hs_2_aq_exists(self, agent_staging):
        """Проверка наличия Pb(HS)2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Pb(HS)2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Pb(HS)2(aq) не найден в staging.db"

    def test_pb_hs_3_aq_exists(self, agent_staging):
        """Проверка наличия Pb(HS)3-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "Pb(HS)3-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"Pb(HS)3-(aq) не найден в staging.db"

    def test_pbno3_aq_exists(self, agent_staging):
        """Проверка наличия PbNO3+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbNO3+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbNO3+(aq) не найден в staging.db"

    def test_pbbr_aq_exists(self, agent_staging):
        """Проверка наличия PbBr+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbBr+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbBr+(aq) не найден в staging.db"

    def test_pbbr2_aq_exists(self, agent_staging):
        """Проверка наличия PbBr2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbBr2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbBr2(aq) не найден в staging.db"

    def test_pbf_aq_exists(self, agent_staging):
        """Проверка наличия PbF+(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbF+" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbF+(aq) не найден в staging.db"

    def test_pbf2_aq_exists(self, agent_staging):
        """Проверка наличия PbF2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbF2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbF2(aq) не найден в staging.db"

    def test_pbf3_aq_exists(self, agent_staging):
        """Проверка наличия PbF3-(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbF3-" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbF3-(aq) не найден в staging.db"

    def test_pbf4_2_aq_exists(self, agent_staging):
        """Проверка наличия PbF4-2(aq) в БД."""
        db = agent_staging.db
        found = any(
            s.formula == "PbF4-2" and s.phase == "aq"
            for s in db.species
        )
        assert found, f"PbF4-2(aq) не найден в staging.db"


class TestNewSpeciesReactions:
    """Химические тесты: проверка реакций с новыми веществами."""

    def test_ca_precipitation(self, agent_staging):
        """Проверка осаждения Ca из раствора."""
        # TODO: Реализовать тест на основе реакций
        pass

    def test_mg_precipitation(self, agent_staging):
        """Проверка осаждения Mg из раствора."""
        # TODO: Реализовать тест на основе реакций
        pass

    def test_na_precipitation(self, agent_staging):
        """Проверка осаждения Na из раствора."""
        # TODO: Реализовать тест на основе реакций
        pass

    def test_k_precipitation(self, agent_staging):
        """Проверка осаждения K из раствора."""
        # TODO: Реализовать тест на основе реакций
        pass

    def test_fe_precipitation(self, agent_staging):
        """Проверка осаждения Fe из раствора."""
        # TODO: Реализовать тест на основе реакций
        pass


class TestNoConflicts:
    """Проверка, что CRC вещества не были перезаписаны."""

    def test_crc_species_not_overwritten(self, agent_staging):
        """Проверка, что вещества из CRC не изменены."""
        db = agent_staging.db
        # Проверяем ключевые вещества CRC
        crc_species = [
            ("H2O", "l"),
            ("H+", "aq"),
            ("OH-", "aq"),
        ]
        for formula, phase in crc_species:
            species = next(
                (s for s in db.species if s.formula == formula and s.phase == phase),
                None
            )
            if species:
                assert species.source == "CRC", f"{formula}({phase}) был перезаписан!"
