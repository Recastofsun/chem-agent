"""Управление логами с автоматической ротацией."""
import logging
from pathlib import Path
from typing import Optional


class LogManager:
    """
    Менеджер логов с автоматической ротацией.
    Хранит максимум max_logs файлов в директории.
    """
    
    def __init__(
        self,
        log_dir: Path,
        log_name: str = "import",
        max_logs: int = 10,
        level: int = logging.INFO,
    ):
        self.log_dir = log_dir
        self.log_name = log_name
        self.max_logs = max_logs
        self.level = level
        self.logger: Optional[logging.Logger] = None
    
    def setup(self) -> logging.Logger:
        """Настраивает логгер с ротацией."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Создаем логгер
        self.logger = logging.getLogger(f"universal_importer.{self.log_name}")
        self.logger.setLevel(self.level)
        
        # Очищаем старые handlers
        self.logger.handlers.clear()
        
        # File handler
        log_file = self.log_dir / f"{self.log_name}.log"
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(self.level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(self.level)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        
        # Ротация старых логов
        self._rotate_logs()
        
        return self.logger
    
    def _rotate_logs(self):
        """Удаляет старые логи, оставляя максимум max_logs файлов."""
        log_files = sorted(
            self.log_dir.glob(f"{self.log_name}_*.log"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        # Удаляем файлы сверх лимита
        if len(log_files) >= self.max_logs:
            for old_file in log_files[self.max_logs - 1:]:
                old_file.unlink()
                if self.logger:
                    self.logger.info(f"Удален старый лог: {old_file.name}")
    
    def get_logger(self) -> logging.Logger:
        """Возвращает настроенный логгер."""
        if self.logger is None:
            self.setup()
        return self.logger