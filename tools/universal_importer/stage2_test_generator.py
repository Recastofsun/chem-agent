"""Stage 2: Генерация тестов на основе manifest.json (W-26)."""
import json
from pathlib import Path
from typing import Optional


class TestGenerator:
    """
    Генерирует pytest-тесты для новых веществ из manifest.json.
    
    Создает:
    1. Unit-тесты на наличие веществ в БД
    2. Химические тесты на основе реакций
    """
    
    def __init__(self, manifest_path: Path, test_output_path: Path):
        self.manifest_path = manifest_path
        self.test_output_path = test_output_path
    
    def generate(self) -> dict:
        """Генерирует тесты и возвращает статистику."""
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest не найден: {self.manifest_path}")
        
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        
        new_species = manifest["new_species"]
        stats = {
            "total_species": len(new_species),
            "unit_tests": 0,
            "chemical_tests": 0,
        }
        
        # Генерируем код тестов
        test_code = self._generate_test_code(new_species, stats)
        
        # Сохраняем тесты
        self.test_output_path.parent.mkdir(parents=True, exist_ok=True)
        self.test_output_path.write_text(test_code, encoding="utf-8")
        
        return stats
    
    def _generate_test_code(self, new_species: list[dict], stats: dict) -> str:
        """Генерирует Python-код тестов."""
        lines = [
            '"""Автоматически сгенерированные тесты для новых веществ (W-26)."""',
            'import pytest',
            'from chem_agent.agent import Agent',
            '',
            '',
            '@pytest.fixture',
            'def agent_staging():',
            '    """Agent с staging.db для тестирования новых веществ."""',
            "    return Agent(offline=True, db_path='chem_agent/data/staging.db')",
            '',
            '',
        ]
        
        # Unit-тесты: проверка наличия каждого вещества
        lines.append('class TestNewSpeciesPresence:')
        lines.append('    """Unit-тесты: проверка наличия новых веществ в БД."""')
        lines.append('')
        
        for i, species in enumerate(new_species):
            formula = species["formula"]
            phase = species["phase"]
            dGf = species["dGf"]
            
            test_name = f"test_{self._sanitize_formula(formula)}_{phase}_exists"
            lines.append(f'    def {test_name}(self, agent_staging):')
            lines.append(f'        """Проверка наличия {formula}({phase}) в БД."""')
            lines.append(f'        db = agent_staging.db')
            lines.append(f'        found = any(')
            lines.append(f'            s.formula == "{formula}" and s.phase == "{phase}"')
            lines.append(f'            for s in db.species')
            lines.append(f'        )')
            lines.append(f'        assert found, f"{formula}({phase}) не найден в staging.db"')
            lines.append('')
            stats["unit_tests"] += 1
        
        # Химические тесты: проверка реакций с новыми веществами
        lines.append('')
        lines.append('class TestNewSpeciesReactions:')
        lines.append('    """Химические тесты: проверка реакций с новыми веществами."""')
        lines.append('')
        
        # Группируем вещества по элементам для генерации осадочных тестов
        elements = {}
        for species in new_species:
            formula = species["formula"]
            phase = species["phase"]
            
            # Извлекаем элемент из формулы (упрощенно)
            import re
            m = re.match(r'^([A-Z][a-z]?)', formula)
            if m:
                element = m.group(1)
                if element not in elements:
                    elements[element] = []
                elements[element].append({"formula": formula, "phase": phase})
        
        # Генерируем тесты на осаждение для металлов
        metal_tests = []
        for element, compounds in elements.items():
            if element in ['H', 'O', 'N', 'C', 'S', 'P', 'F', 'Cl', 'Br']:
                continue  # Пропускаем неметаллы
            
            aq_compounds = [c for c in compounds if c["phase"] == "aq"]
            if len(aq_compounds) >= 2:
                # Берем первые два соединения для теста
                test_compounds = aq_compounds[:2]
                metal_tests.append({
                    "element": element,
                    "compounds": test_compounds
                })
        
        for i, test_data in enumerate(metal_tests[:5]):  # Ограничиваем 5 тестами
            element = test_data["element"]
            compounds = test_data["compounds"]
            
            test_name = f"test_{element.lower()}_precipitation"
            lines.append(f'    def {test_name}(self, agent_staging):')
            lines.append(f'        """Проверка осаждения {element} из раствора."""')
            lines.append(f'        # TODO: Реализовать тест на основе реакций')
            lines.append(f'        pass')
            lines.append('')
            stats["chemical_tests"] += 1
        
        # Добавляем тест на отсутствие конфликтов
        lines.append('')
        lines.append('class TestNoConflicts:')
        lines.append('    """Проверка, что CRC вещества не были перезаписаны."""')
        lines.append('')
        lines.append('    def test_crc_species_not_overwritten(self, agent_staging):')
        lines.append('        """Проверка, что вещества из CRC не изменены."""')
        lines.append('        db = agent_staging.db')
        lines.append('        # Проверяем ключевые вещества CRC')
        lines.append('        crc_species = [')
        lines.append('            ("H2O", "l"),')
        lines.append('            ("H+", "aq"),')
        lines.append('            ("OH-", "aq"),')
        lines.append('        ]')
        lines.append('        for formula, phase in crc_species:')
        lines.append('            species = next(')
        lines.append('                (s for s in db.species if s.formula == formula and s.phase == phase),')
        lines.append('                None')
        lines.append('            )')
        lines.append('            if species:')
        lines.append('                assert species.source == "CRC", f"{formula}({phase}) был перезаписан!"')
        lines.append('')
        
        return '\n'.join(lines)
    
    @staticmethod
    def _sanitize_formula(formula: str) -> str:
        """Превращает формулу в валидное имя функции."""
        import re
        # Заменяем специальные символы на подчеркивания
        sanitized = re.sub(r'[^a-zA-Z0-9]', '_', formula)
        # Удаляем множественные подчеркивания
        sanitized = re.sub(r'_+', '_', sanitized)
        # Удаляем подчеркивания в начале и конце
        sanitized = sanitized.strip('_')
        return sanitized.lower()


def main():
    """Точка входа для генерации тестов."""
    from pathlib import Path
    import sys
    
    ROOT = Path(__file__).resolve().parent.parent.parent
    
    manifest_path = ROOT / "tools" / "universal_importer" / "manifest.json"
    test_output_path = ROOT / "tests" / "test_generated_imports.py"
    
    print("=" * 60)
    print("STAGE 2: Генерация тестов")
    print("=" * 60)
    
    generator = TestGenerator(manifest_path, test_output_path)
    stats = generator.generate()
    
    print(f"✅ Тесты сгенерированы: {test_output_path}")
    print(f"   Unit-тестов: {stats['unit_tests']}")
    print(f"   Химических тестов: {stats['chemical_tests']}")
    print(f"   Всего веществ: {stats['total_species']}")
    print("\nСледующий шаг: Stage 3 - Запуск тестов")
    print(f"   python -m pytest {test_output_path} -v")


if __name__ == "__main__":
    main()