import json
import logging
from pathlib import Path
from .history import get_appdata_dir

log = logging.getLogger("chem-agent.settings")

DEFAULT_SETTINGS = {
    "theme": "dark",
    "modules": {
        "learning": False,
        "viewer3d": True
    }
}

class SettingsManager:
    def __init__(self):
        self.settings_path = get_appdata_dir() / "settings.json"
        self._settings = self._load()

    def _load(self) -> dict:
        if self.settings_path.exists():
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    return {**DEFAULT_SETTINGS, **json.load(f)}
            except Exception as e:
                log.error(f"Ошибка чтения settings.json: {e}")
        return DEFAULT_SETTINGS.copy()

    def get_all(self) -> dict:
        return self._settings

    def save(self, new_settings: dict):
        self._settings.update(new_settings)
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"Ошибка сохранения settings.json: {e}")