"""Парсер формата PHREEQC (.dat)."""
import re
from pathlib import Path
from .base import (
    BaseFormat, BlockType, MasterSpecies, ParsedDatabase, Reaction
)


class PhreeqcFormat(BaseFormat):
    """Парсер для файлов PHREEQC (phreeqc.dat, llnl.dat, wateq4f.dat)."""
    
    FORMAT_NAME = "phreeqc"
    FILE_EXTENSIONS = (".dat",)
    SUPPORTED_BLOCKS = (
        BlockType.MASTER_SPECIES,
        BlockType.SOLUTION_SPECIES,
        BlockType.PHASES,
    )
    
    PROPERTY_ALIASES = {
        "logk": "log_k",
        "log_k": "log_k",
        "delta_h": "delta_h",
        "deltah": "delta_h",
        "analytical_expression": "analytical_expression",
        "analytical": "analytical_expression",
        "gamma": "gamma",
    }
    
    def parse(self) -> ParsedDatabase:
        self.load()
        db = ParsedDatabase(
            format_name=self.FORMAT_NAME,
            source_file=str(self.file_path.name),
        )
        
        i = 0
        current_block = None
        
        while i < len(self.lines):
            line = self.strip_comment(self.lines[i])
            
            # Определение блоков
            if line in ("SOLUTION_MASTER_SPECIES", "SOLUTION_SPECIES", "PHASES",
                        "EXCHANGE_MASTER_SPECIES", "SURFACE_MASTER_SPECIES",
                        "GAS_PHASE", "RATES", "END"):
                if line == "SOLUTION_MASTER_SPECIES":
                    current_block = BlockType.MASTER_SPECIES
                elif line == "SOLUTION_SPECIES":
                    current_block = BlockType.SOLUTION_SPECIES
                elif line == "PHASES":
                    current_block = BlockType.PHASES
                else:
                    current_block = None
                i += 1
                continue
            
            # Парсинг в зависимости от блока
            if current_block == BlockType.MASTER_SPECIES:
                ms = self._parse_master_species(line)
                if ms:
                    db.master_species.append(ms)
            elif current_block == BlockType.SOLUTION_SPECIES:
                if "=" in line:
                    reaction, i = self._parse_reaction_block(i)
                    if reaction:
                        reaction.source_block = BlockType.SOLUTION_SPECIES
                        db.reactions.append(reaction)
                    continue
            elif current_block == BlockType.PHASES:
                if "=" in line:
                    reaction, i = self._parse_phase_block(i)
                    if reaction:
                        reaction.source_block = BlockType.PHASES
                        db.reactions.append(reaction)
                    continue
            
            i += 1
        
        db.stats = {
            "master_species": len(db.master_species),
            "reactions": len(db.reactions),
            "solution_species": sum(
                1 for r in db.reactions 
                if r.source_block == BlockType.SOLUTION_SPECIES
            ),
            "phases": sum(
                1 for r in db.reactions 
                if r.source_block == BlockType.PHASES
            ),
        }
        return db
    
    def _parse_master_species(self, line: str) -> MasterSpecies | None:
        parts = line.split()
        if len(parts) < 3:
            return None
        try:
            return MasterSpecies(
                element=parts[0],
                master_formula=parts[1],
                alkalinity=float(parts[2]) if parts[2] != "0" else 0.0,
            )
        except (ValueError, IndexError):
            return None
    
    def _parse_reaction_block(self, start: int) -> tuple[Reaction | None, int]:
        """Парсит блок реакции SOLUTION_SPECIES."""
        line = self.strip_comment(self.lines[start])
        if "=" not in line:
            return None, start
        
        left_str, right_str = [s.strip() for s in line.split("=", 1)]
        
        props = {}
        i = start + 1
        while i < len(self.lines):
            next_line = self.lines[i].strip()
            if not next_line or next_line.startswith("#"):
                i += 1
                continue
            if next_line.startswith("-"):
                parsed = self._parse_property_line(next_line)
                props.update(parsed)
                i += 1
            else:
                break
        
        if "log_k" not in props:
            return None, i
        
        return Reaction(
            left=left_str,
            right=right_str,
            log_k=props["log_k"],
            delta_h=props.get("delta_h"),
            analytical_expression=props.get("analytical_expression"),
            gamma=props.get("gamma"),
        ), i
    
    def _parse_phase_block(self, start: int) -> tuple[Reaction | None, int]:
        """Парсит блок PHASES."""
        phase_name = None
        k = start - 1
        while k >= 0:
            prev = self.strip_comment(self.lines[k])
            if prev:
                phase_name = prev
                break
            k -= 1
        
        line = self.strip_comment(self.lines[start])
        if "=" not in line:
            return None, start
        
        left_str, right_str = [s.strip() for s in line.split("=", 1)]
        
        props = {}
        i = start + 1
        while i < len(self.lines):
            next_line = self.lines[i].strip()
            if not next_line or next_line.startswith("#"):
                i += 1
                continue
            if next_line.startswith("-"):
                parsed = self._parse_property_line(next_line)
                props.update(parsed)
                i += 1
            else:
                break
        
        if "log_k" not in props or not phase_name:
            return None, i
        
        return Reaction(
            left=left_str,
            right=right_str,
            log_k=props["log_k"],
            delta_h=props.get("delta_h"),
            analytical_expression=props.get("analytical_expression"),
            raw_name=phase_name,
        ), i
    
    def _parse_property_line(self, line: str) -> dict[str, float]:
        """Парсит строку свойств вида '-log_k -8.45; -delta_h -3.15 kcal'."""
        import re
        props = {}
        pattern = r'-([a-zA-Z0-9_]+)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)'
        for key, val in re.findall(pattern, line):
            key_lower = key.lower()
            if key_lower in self.PROPERTY_ALIASES:
                key_lower = self.PROPERTY_ALIASES[key_lower]
            try:
                props[key_lower] = float(val)
            except ValueError:
                pass
        return props
    