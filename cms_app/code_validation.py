"""Quick code validation - check if codes exist in dataset before expensive search."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .cms_query import get_paths
from .cms_columns import detect_hcpcs_col


@lru_cache(maxsize=100)
def check_codes_exist(codes_tuple: tuple[str, ...], sample_size: int = 1_000_000) -> dict[str, bool]:
    """
    Quickly check if codes exist in the dataset by sampling.
    
    Args:
        codes_tuple: Tuple of normalized codes to check
        sample_size: Number of rows to sample (default 1M for speed)
    
    Returns:
        Dictionary mapping code -> exists (True/False)
    """
    if not codes_tuple:
        return {}
    
    path = get_paths().physician_puf
    header = list(pd.read_csv(path, nrows=0, low_memory=False).columns)
    hcpcs_col = detect_hcpcs_col(header)
    
    # Sample the dataset
    chunk = pd.read_csv(path, usecols=[hcpcs_col], nrows=sample_size, low_memory=False)
    codes_in_data = set(chunk[hcpcs_col].astype(str).str.strip().str.upper().unique())
    
    result = {}
    for code in codes_tuple:
        result[code] = code in codes_in_data
    
    return result


def validate_codes_before_search(codes: list[str]) -> tuple[list[str], list[str]]:
    """
    Validate codes and return (valid_codes, missing_codes).
    
    Args:
        codes: List of codes to validate
    
    Returns:
        Tuple of (codes that exist, codes that don't exist)
    """
    from .cms_columns import normalize_codes
    
    codes_n = normalize_codes(codes)
    if not codes_n:
        return [], []
    
    exists_map = check_codes_exist(tuple(codes_n))
    valid = [c for c in codes_n if exists_map.get(c, False)]
    missing = [c for c in codes_n if not exists_map.get(c, False)]
    
    return valid, missing

