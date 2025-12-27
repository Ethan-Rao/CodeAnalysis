"""HCPCS Code Lookup System.

Provides code descriptions, metadata, and search functionality using HCPCS 2026 data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import Config


@dataclass
class HCPCSCode:
    """Represents a single HCPCS code with all its metadata."""
    code: str
    modifier: str | None
    long_description: str
    short_description: str
    pricing_indicator: str | None
    coverage_code: str | None
    betos_code: str | None
    type_of_service: str | None
    effective_date: str | None
    termination_date: str | None
    action_code: str | None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "modifier": self.modifier,
            "long_description": self.long_description,
            "short_description": self.short_description,
            "pricing_indicator": self.pricing_indicator,
            "coverage_code": self.coverage_code,
            "betos_code": self.betos_code,
            "type_of_service": self.type_of_service,
            "effective_date": self.effective_date,
            "termination_date": self.termination_date,
            "action_code": self.action_code,
        }


class HCPCSLookup:
    """HCPCS code lookup and search system."""
    
    def __init__(self, hcpcs_file: Path | None = None):
        """Initialize the lookup system.
        
        Args:
            hcpcs_file: Path to HCPCS fixed-width file. If None, uses default from config.
        """
        if hcpcs_file is None:
            config = Config()
            hcpcs_file = config.PROJECT_ROOT / "HCPCS" / "HCPC2026_JAN_ANWEB_12082025.txt"
        
        self.hcpcs_file = Path(hcpcs_file)
        self._codes: dict[str, HCPCSCode] = {}
        self._load_codes()
    
    def _parse_fixed_width_line(self, line: str) -> dict[str, Any] | None:
        """Parse a fixed-width HCPCS record line.
        
        Based on HCPC2026_recordlayout.txt (1-indexed positions):
        - Positions 1-5: HCPCS Code
        - Positions 6-10: Sequence Number
        - Position 11: Record ID (3=procedure first line, 4=procedure continuation, 7=modifier first, 8=modifier continuation)
        - Positions 12-91: Long Description (80 chars)
        - Positions 92-119: Short Description (28 chars)
        - Positions 120-121: Pricing Indicator (first)
        - Position 230: Coverage Code
        - Positions 257-259: BETOS Code
        - Position 261: Type of Service
        - Positions 269-276: Code Added Date
        - Positions 277-284: Action Effective Date
        - Positions 285-292: Termination Date
        - Position 293: Action Code
        """
        if len(line) < 293:
            return None
        
        # Convert to 0-indexed
        code = line[0:5].strip()  # positions 1-5
        sequence = line[5:10].strip() if len(line) > 10 else ""  # positions 6-10
        record_id = line[10:11] if len(line) > 10 else ""  # position 11
        long_desc = line[11:91].strip() if len(line) > 91 else ""  # positions 12-91
        short_desc = line[91:119].strip() if len(line) > 119 else ""  # positions 92-119
        pricing_ind = line[119:121].strip() if len(line) > 121 else None  # positions 120-121
        coverage = line[229:230].strip() if len(line) > 230 else None  # position 230
        betos = line[256:259].strip() if len(line) > 259 else None  # positions 257-259
        type_svc = line[260:261].strip() if len(line) > 261 else None  # position 261
        add_date = line[268:276].strip() if len(line) > 276 else None  # positions 269-276
        eff_date = line[276:284].strip() if len(line) > 284 else None  # positions 277-284
        term_date = line[284:292].strip() if len(line) > 292 else None  # positions 285-292
        action = line[292:293].strip() if len(line) > 293 else None  # position 293
        
        # Only process procedure records (record_id 3 or 4)
        # Modifiers (7, 8) are handled separately if needed
        if record_id not in ("3", "4"):
            return None
        
        return {
            "code": code,
            "sequence": sequence,
            "record_id": record_id,
            "long_description": long_desc,
            "short_description": short_desc,
            "pricing_indicator": pricing_ind if pricing_ind else None,
            "coverage_code": coverage if coverage else None,
            "betos_code": betos if betos else None,
            "type_of_service": type_svc if type_svc else None,
            "effective_date": eff_date if eff_date else None,
            "termination_date": term_date if term_date else None,
            "action_code": action if action else None,
            "code_added_date": add_date if add_date else None,
        }
    
    def _load_codes(self) -> None:
        """Load HCPCS codes from fixed-width file."""
        if not self.hcpcs_file.exists():
            # If file doesn't exist, start with empty dict
            self._codes = {}
            return
        
        codes_dict: dict[str, list[dict[str, Any]]] = {}
        
        try:
            with open(self.hcpcs_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    parsed = self._parse_fixed_width_line(line)
                    if not parsed or not parsed["code"]:
                        continue
                    
                    code = parsed["code"]
                    if code not in codes_dict:
                        codes_dict[code] = []
                    codes_dict[code].append(parsed)
            
            # Combine multi-line descriptions
            for code, records in codes_dict.items():
                # Sort by record_id (3 comes before 4) and sequence
                def sort_key(r):
                    rid = r.get("record_id", "")
                    seq = r.get("sequence", "")
                    try:
                        seq_num = int(seq) if seq else 0
                    except ValueError:
                        seq_num = 0
                    return (rid, seq_num)
                records.sort(key=sort_key)
                
                # Combine long descriptions
                long_desc_parts = []
                short_desc = ""
                pricing_ind = None
                coverage = None
                betos = None
                type_svc = None
                eff_date = None
                term_date = None
                action = None
                
                for record in records:
                    if record.get("long_description"):
                        long_desc_parts.append(record["long_description"])
                    if not short_desc and record.get("short_description"):
                        short_desc = record["short_description"]
                    if not pricing_ind and record.get("pricing_indicator"):
                        pricing_ind = record["pricing_indicator"]
                    if not coverage and record.get("coverage_code"):
                        coverage = record["coverage_code"]
                    if not betos and record.get("betos_code"):
                        betos = record["betos_code"]
                    if not type_svc and record.get("type_of_service"):
                        type_svc = record["type_of_service"]
                    if not eff_date and record.get("effective_date"):
                        eff_date = record["effective_date"]
                    if not term_date and record.get("termination_date"):
                        term_date = record["termination_date"]
                    if not action and record.get("action_code"):
                        action = record["action_code"]
                
                long_desc = " ".join(long_desc_parts).strip()
                
                self._codes[code] = HCPCSCode(
                    code=code,
                    modifier=None,  # Modifiers handled separately
                    long_description=long_desc,
                    short_description=short_desc,
                    pricing_indicator=pricing_ind,
                    coverage_code=coverage,
                    betos_code=betos,
                    type_of_service=type_svc,
                    effective_date=eff_date,
                    termination_date=term_date,
                    action_code=action,
                )
        
        except Exception as e:
            # If loading fails, start with empty dict
            self._codes = {}
    
    @lru_cache(maxsize=1000)
    def get_code(self, code: str) -> HCPCSCode | None:
        """Get details for a specific code.
        
        Args:
            code: HCPCS/CPT code (normalized to uppercase)
        
        Returns:
            HCPCSCode if found, None otherwise
        """
        normalized = str(code).strip().upper()
        return self._codes.get(normalized)
    
    def search_codes(self, query: str, limit: int = 50) -> list[HCPCSCode]:
        """Search codes by description.
        
        Args:
            query: Search query (searches in descriptions)
            limit: Maximum results to return
        
        Returns:
            List of matching HCPCSCode objects
        """
        query_lower = query.lower()
        results = []
        
        for code_obj in self._codes.values():
            if (query_lower in code_obj.long_description.lower() or
                query_lower in code_obj.short_description.lower() or
                query_lower in code_obj.code.lower()):
                results.append(code_obj)
                if len(results) >= limit:
                    break
        
        return results
    
    def autocomplete(self, prefix: str, limit: int = 20) -> list[dict[str, str]]:
        """Autocomplete codes by prefix.
        
        Args:
            prefix: Code prefix to match
            limit: Maximum results
        
        Returns:
            List of dicts with 'code' and 'description'
        """
        prefix_upper = prefix.upper()
        results = []
        
        for code_obj in self._codes.values():
            if code_obj.code.startswith(prefix_upper):
                results.append({
                    "code": code_obj.code,
                    "description": code_obj.short_description or code_obj.long_description[:50],
                })
                if len(results) >= limit:
                    break
        
        return results
    
    def get_codes_by_betos(self, betos_code: str) -> list[str]:
        """Get all codes with a specific BETOS classification.
        
        Args:
            betos_code: BETOS code (e.g., 'P1A', 'M1B')
        
        Returns:
            List of code strings
        """
        return [
            code_obj.code
            for code_obj in self._codes.values()
            if code_obj.betos_code == betos_code
        ]
    
    def get_all_codes(self) -> list[str]:
        """Get all loaded codes.
        
        Returns:
            List of all code strings
        """
        return list(self._codes.keys())


# Global instance (lazy-loaded)
_hcpcs_lookup: HCPCSLookup | None = None


def get_hcpcs_lookup() -> HCPCSLookup:
    """Get the global HCPCS lookup instance."""
    global _hcpcs_lookup
    if _hcpcs_lookup is None:
        _hcpcs_lookup = HCPCSLookup()
    return _hcpcs_lookup


