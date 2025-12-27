"""Detect whether codes are HCPCS (letter-prefixed) or CPT (numeric)."""
from __future__ import annotations

import re


def is_hcpcs_code(code: str) -> bool:
    """
    Determine if a code is HCPCS (starts with letter) or CPT (numeric).
    
    Args:
        code: Code string (e.g., 'A4344', '62270')
    
    Returns:
        True if HCPCS (letter-prefixed), False if CPT (numeric)
    """
    code_clean = str(code).strip().upper()
    if not code_clean:
        return False
    # HCPCS codes start with a letter (A-Z)
    # CPT codes are numeric (0-9)
    return bool(re.match(r'^[A-Z]', code_clean))


def split_codes_by_type(codes: list[str]) -> tuple[list[str], list[str]]:
    """
    Split codes into HCPCS and CPT lists.
    
    Args:
        codes: List of code strings
    
    Returns:
        Tuple of (hcpcs_codes, cpt_codes)
    """
    hcpcs = []
    cpt = []
    for code in codes:
        if is_hcpcs_code(code):
            hcpcs.append(code)
        else:
            cpt.append(code)
    return hcpcs, cpt

