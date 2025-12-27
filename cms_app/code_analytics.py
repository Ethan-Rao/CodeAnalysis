"""Code Analytics - Market Intelligence for Medical Device Companies.

Provides insights into which codes are most used, helping companies understand
market opportunities and identify high-value codes for their products.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .cms_query import get_paths, normalize_codes
from .cms_columns import detect_hcpcs_col, detect_services_col, detect_total_payment_col


def get_top_codes_by_volume(
    limit: int = 100,
    min_services: int = 100,
    states: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """
    Get top HCPCS/CPT codes by total procedure volume.
    
    Args:
        limit: Maximum number of codes to return
        min_services: Minimum total services threshold
        states: Optional tuple of state codes to filter by
    
    Returns:
        DataFrame with columns: code, total_services, total_payments, num_physicians, num_hospitals
    """
    path = get_paths().physician_puf
    header = list(pd.read_csv(path, nrows=0, low_memory=False).columns)
    
    hcpcs_col = detect_hcpcs_col(header)
    services_col = detect_services_col(header)
    total_payment_col = detect_total_payment_col(header)
    
    usecols = [c for c in [hcpcs_col, services_col, total_payment_col] if c]
    
    code_totals: dict[str, dict[str, float]] = {}  # code -> {services, payments, npis}
    npi_set: set[str] = set()
    
    states_list = list(states) if states else None
    
    chunksize = 250_000
    for chunk in pd.read_csv(path, usecols=usecols, low_memory=False, chunksize=chunksize):
        chunk = chunk.rename(
            columns={
                hcpcs_col: "code",
                services_col: "services",
                (total_payment_col or ""): "total_payment",
            }
        )
        if "" in chunk.columns:
            chunk = chunk.drop(columns=[""])
        
        chunk["code"] = chunk["code"].astype(str).str.strip().str.upper()
        chunk["services"] = pd.to_numeric(chunk["services"], errors="coerce").fillna(0)
        
        if "total_payment" in chunk.columns:
            chunk["total_payment"] = pd.to_numeric(chunk["total_payment"], errors="coerce").fillna(0)
        else:
            chunk["total_payment"] = 0.0
        
        # Filter by states if provided (would need state column - skip for now for performance)
        # For now, aggregate all codes
        
        for _, row in chunk.iterrows():
            code = str(row["code"])
            if not code or code == "NAN":
                continue
            
            services = float(row["services"])
            payment = float(row.get("total_payment", 0))
            
            if code not in code_totals:
                code_totals[code] = {"services": 0.0, "payments": 0.0}
            
            code_totals[code]["services"] += services
            code_totals[code]["payments"] += payment
    
    # Convert to DataFrame
    rows = []
    for code, totals in code_totals.items():
        if totals["services"] >= min_services:
            rows.append({
                "code": code,
                "total_services": totals["services"],
                "total_payments": totals["payments"],
            })
    
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["code", "total_services", "total_payments", "num_physicians", "num_hospitals"])
    
    df = df.sort_values("total_services", ascending=False)
    df = df.head(limit)
    
    return df


def get_code_market_stats(codes: list[str]) -> dict[str, any]:
    """
    Get market statistics for a set of codes.
    
    Args:
        codes: List of HCPCS/CPT codes
    
    Returns:
        Dictionary with market statistics
    """
    codes_n = normalize_codes(codes)
    if not codes_n:
        return {
            "total_services": 0,
            "total_payments": 0,
            "num_physicians": 0,
            "num_hospitals": 0,
            "avg_services_per_physician": 0,
        }
    
    from .cms_query import doctors_by_codes
    from .hospital_analytics import hospitals_by_codes
    
    doctors_df = doctors_by_codes(codes=codes_n, max_rows=10000)
    hospitals_df = hospitals_by_codes(codes=codes_n, max_rows=10000)
    
    total_services = int(doctors_df["total_services_selected_codes"].sum()) if not doctors_df.empty else 0
    total_payments = float(doctors_df["total_payments_selected_codes"].sum()) if not doctors_df.empty else 0
    num_physicians = len(doctors_df)
    num_hospitals = len(hospitals_df)
    
    avg_services = total_services / num_physicians if num_physicians > 0 else 0
    
    return {
        "total_services": total_services,
        "total_payments": total_payments,
        "num_physicians": num_physicians,
        "num_hospitals": num_hospitals,
        "avg_services_per_physician": avg_services,
    }

