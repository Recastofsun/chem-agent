import pytest
from unittest.mock import patch
from chem_agent.storage.history import HistoryDB

@pytest.fixture
def temp_db(tmp_path):
    """Создаем временную БД для тестов, чтобы не трогать реальную историю пользователя."""
    test_db_path = tmp_path / "test_history.db"
    with patch("chem_agent.storage.history.get_appdata_dir", return_value=tmp_path):
        db = HistoryDB()
        yield db

def test_add_and_get_history(temp_db):
    # Имитируем ответ от ядра
    mock_data = {
        "reaction_id": "test-uuid-123",
        "status": "ok",
        "input": {"reagents": [{"formula": "NaOH"}, {"formula": "HCl"}]},
        "balanced_equations": [{"equation": "NaOH + HCl -> NaCl + H2O"}],
        "summary": {"main_product": "NaCl"}
    }
    
    temp_db.add_entry(mock_data)
    history = temp_db.get_history()
    
    assert len(history) == 1
    assert history[0]["reaction_id"] == "test-uuid-123"
    assert history[0]["equation"] == "NaOH + HCl -> NaCl + H2O"
    assert "NaOH" in history[0]["reagents"]

def test_delete_and_clear_history(temp_db):
    # Добавляем две записи
    temp_db.add_entry({"reaction_id": "1", "input": {"reagents": []}, "summary": {}})
    temp_db.add_entry({"reaction_id": "2", "input": {"reagents": []}, "summary": {}})
    
    assert len(temp_db.get_history()) == 2
    
    # Удаляем одну
    temp_db.delete_entry("1")
    assert len(temp_db.get_history()) == 1
    assert temp_db.get_history()[0]["reaction_id"] == "2"
    
    # Очищаем всё
    temp_db.clear()
    assert len(temp_db.get_history()) == 0