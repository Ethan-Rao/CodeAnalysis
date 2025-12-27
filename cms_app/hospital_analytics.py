"""Hospital-Level Analytics System.

Provides hospital-level usage statistics for medical device companies.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .cms_query import attach_hospital_affiliations, get_paths, normalize_codes, normalize_states
from .cms_columns import (
    detect_hcpcs_col,
    detect_npi_col,
    detect_services_col,
    detect_state_col,
    detect_total_payment_col,
)


def hospitals_by_codes(
    codes: list[str],
    states: list[str] | None = None,
    min_procedures: int | None = None,
    max_rows: int = 250,
) -> pd.DataFrame:
    """
    Hospital aggregation - routes to appropriate dataset based on code type.
    - HCPCS codes (letter-prefixed like A4344) -> refHCPCS.csv (referring providers)
    - CPT codes (numeric like 62270) -> physHCPCS.csv (rendering providers)
    """
    from .code_type_detection import split_codes_by_type
    from .hospital_analytics_optimized import hospitals_by_codes_optimized
    from .referring_provider_analytics import hospitals_by_hcpcs_codes
    
    # Split codes by type
    hcpcs_codes, cpt_codes = split_codes_by_type(codes)
    
    results = []
    
    # Search HCPCS codes in referring provider dataset
    if hcpcs_codes:
        hcpcs_df = hospitals_by_hcpcs_codes(hcpcs_codes, states, min_procedures, max_rows)
        if not hcpcs_df.empty:
            results.append(hcpcs_df)
    
    # Search CPT codes in physician dataset
    if cpt_codes:
        cpt_df = hospitals_by_codes_optimized(cpt_codes, states, min_procedures, max_rows)
        if not cpt_df.empty:
            results.append(cpt_df)
    
    # Combine results
    if not results:
        return pd.DataFrame(
            columns=[
                "facility_id",
                "hospital_name",
                "hospital_city",
                "hospital_state",
                "total_procedures",
                "total_payments",
                "num_physicians",
                "avg_procedures_per_physician",
                "code_breakdown",
            ]
        )
    
    # Combine and re-aggregate if needed (in case same hospital appears in both)
    combined = pd.concat(results, ignore_index=True)
    
    # Group by facility_id and aggregate properly
    facility_dict = {}
    for _, row in combined.iterrows():
        fac_id = row["facility_id"]
        if fac_id not in facility_dict:
            facility_dict[fac_id] = {
                "hospital_name": row["hospital_name"],
                "hospital_city": row["hospital_city"],
                "hospital_state": row["hospital_state"],
                "total_procedures": 0.0,
                "total_payments": 0.0,
                "max_physicians": 0,
                "code_breakdowns": [],
            }
        
        facility_dict[fac_id]["total_procedures"] += float(row["total_procedures"])
        facility_dict[fac_id]["total_payments"] += float(row["total_payments"])
        facility_dict[fac_id]["max_physicians"] = max(
            facility_dict[fac_id]["max_physicians"],
            int(row.get("num_physicians", 0))
        )
        if pd.notna(row.get("code_breakdown")):
            facility_dict[fac_id]["code_breakdowns"].append(str(row["code_breakdown"]))
    
    # Convert to DataFrame
    rows = []
    for fac_id, data in facility_dict.items():
        code_breakdown = ", ".join([cb for cb in data["code_breakdowns"] if cb and cb != "nan"])[:200]
        avg_procedures = data["total_procedures"] / data["max_physicians"] if data["max_physicians"] > 0 else 0.0
        
        rows.append({
            "facility_id": fac_id,
            "hospital_name": data["hospital_name"],
            "hospital_city": data["hospital_city"],
            "hospital_state": data["hospital_state"],
            "total_procedures": data["total_procedures"],
            "total_payments": data["total_payments"],
            "num_physicians": data["max_physicians"],
            "avg_procedures_per_physician": avg_procedures,
            "code_breakdown": code_breakdown,
        })
    
    grouped = pd.DataFrame(rows)
    
    # Sort and limit
    grouped = grouped.sort_values("total_procedures", ascending=False)
    
    if min_procedures is not None:
        grouped = grouped[grouped["total_procedures"] >= min_procedures]
    
    return grouped.head(max_rows)


def hospitals_by_codes_original(
    codes: list[str],
    states: list[str] | None = None,
    min_procedures: int | None = None,
    max_rows: int = 250,
) -> pd.DataFrame:
    """
    Return a DataFrame of hospitals ranked by total procedures for selected HCPCS/CPT codes,
    with usage statistics.
    
    Args:
        codes: List of HCPCS/CPT codes to search
        states: Optional list of 2-letter state codes to filter by
        min_procedures: Optional minimum number of procedures per hospital
        max_rows: Maximum number of results to return
    
    Returns:
        DataFrame with columns:
        - facility_id: Hospital facility ID/CCN
        - hospital_name: Hospital name
        - hospital_city: Hospital city
        - hospital_state: Hospital state
        - total_procedures: Total procedures for selected codes
        - total_payments: Total Medicare payments
        - num_physicians: Number of physicians performing procedures
        - avg_procedures_per_physician: Average procedures per physician
        - code_breakdown: String showing code distribution
    """
    codes_n = normalize_codes(codes)
    states_n = normalize_states(states)
    
    if not codes_n:
        return pd.DataFrame(
            columns=[
                "facility_id",
                "hospital_name",
                "hospital_city",
                "hospital_state",
                "total_procedures",
                "total_payments",
                "num_physicians",
                "avg_procedures_per_physician",
                "code_breakdown",
            ]
        )
    
    # Load physician data and aggregate by hospital
    path = get_paths().physician_puf
    header = list(pd.read_csv(path, nrows=0, low_memory=False).columns)
    
    npi_col = detect_npi_col(header)
    hcpcs_col = detect_hcpcs_col(header)
    state_col = detect_state_col(header)
    services_col = detect_services_col(header)
    total_payment_col = detect_total_payment_col(header)
    
    usecols = [c for c in [npi_col, hcpcs_col, state_col, services_col, total_payment_col] if c]
    
    # Aggregate by NPI first, then by hospital
    npi_totals: dict[str, dict[str, float]] = {}  # npi -> {services, payments}
    npi_codes: dict[str, dict[str, float]] = {}  # npi -> {code: services}
    npi_states: dict[str, str] = {}  # npi -> state
    
    chunksize = 250_000
    for chunk in pd.read_csv(path, usecols=usecols, low_memory=False, chunksize=chunksize):
        chunk = chunk.rename(
            columns={
                npi_col: "npi",
                hcpcs_col: "code",
                state_col: "state",
                services_col: "services",
                (total_payment_col or ""): "total_payment",
            }
        )
        if "" in chunk.columns:
            chunk = chunk.drop(columns=[""])
        
        chunk["npi"] = chunk["npi"].astype(str).str.strip()
        chunk["code"] = chunk["code"].astype(str).str.strip().str.upper()
        chunk["state"] = chunk["state"].astype(str).str.strip().str.upper()
        
        if states_n:
            chunk = chunk[chunk["state"].isin(states_n)]
        chunk = chunk[chunk["code"].isin(codes_n)]
        if chunk.empty:
            continue
        
        chunk["services"] = pd.to_numeric(chunk["services"], errors="coerce").fillna(0)
        if "total_payment" in chunk.columns:
            chunk["total_payment"] = pd.to_numeric(chunk["total_payment"], errors="coerce").fillna(0)
        else:
            chunk["total_payment"] = 0.0
        
        # Aggregate by NPI
        for _, row in chunk.iterrows():
            npi = str(row["npi"])
            code = str(row["code"])
            services = float(row["services"])
            payment = float(row.get("total_payment", 0))
            state = str(row.get("state", ""))
            
            if npi not in npi_totals:
                npi_totals[npi] = {"services": 0.0, "payments": 0.0}
                npi_codes[npi] = {}
                npi_states[npi] = state
            
            npi_totals[npi]["services"] += services
            npi_totals[npi]["payments"] += payment
            npi_codes[npi][code] = npi_codes[npi].get(code, 0.0) + services
    
    if not npi_totals:
        return pd.DataFrame(
            columns=[
                "facility_id",
                "hospital_name",
                "hospital_city",
                "hospital_state",
                "total_procedures",
                "total_payments",
                "num_physicians",
                "avg_procedures_per_physician",
                "code_breakdown",
            ]
        )
    
    # Load hospital affiliations
    from .cms_query import load_facility_affiliations, load_hospital_metadata
    
    try:
        affiliations = load_facility_affiliations()
        hospitals = load_hospital_metadata()
    except Exception:
        # If affiliations can't be loaded, return empty
        return pd.DataFrame(
            columns=[
                "facility_id",
                "hospital_name",
                "hospital_city",
                "hospital_state",
                "total_procedures",
                "total_payments",
                "num_physicians",
                "avg_procedures_per_physician",
                "code_breakdown",
            ]
        )
    
    # Aggregate by hospital
    hospital_stats: dict[str, dict[str, Any]] = {}
    
    for npi, totals in npi_totals.items():
        # Find hospitals for this NPI
        npi_affiliations = affiliations[affiliations["npi"] == npi]
        
        if npi_affiliations.empty:
            # No hospital affiliation - skip or create "Unknown" hospital
            continue
        
        for _, aff_row in npi_affiliations.iterrows():
            facility_id = str(aff_row["facility_id"])
            
            # Get hospital info
            hosp_info = hospitals[hospitals["facility_id"] == facility_id]
            if hosp_info.empty:
                continue
            
            hosp_row = hosp_info.iloc[0]
            
            if facility_id not in hospital_stats:
                hospital_stats[facility_id] = {
                    "facility_id": facility_id,
                    "hospital_name": str(hosp_row.get("hospital_name", "")),
                    "hospital_city": str(hosp_row.get("hospital_city", "")),
                    "hospital_state": str(hosp_row.get("hospital_state", "")),
                    "total_procedures": 0.0,
                    "total_payments": 0.0,
                    "physicians": set(),
                    "code_breakdown": {},
                }
            
            hospital_stats[facility_id]["total_procedures"] += totals["services"]
            hospital_stats[facility_id]["total_payments"] += totals["payments"]
            hospital_stats[facility_id]["physicians"].add(npi)
            
            # Add to code breakdown
            for code, code_services in npi_codes[npi].items():
                hospital_stats[facility_id]["code_breakdown"][code] = (
                    hospital_stats[facility_id]["code_breakdown"].get(code, 0.0) + code_services
                )
    
    # Convert to DataFrame
    rows = []
    for facility_id, stats in hospital_stats.items():
        num_physicians = len(stats["physicians"])
        avg_procedures = (
            stats["total_procedures"] / num_physicians if num_physicians > 0 else 0.0
        )
        
        # Build code breakdown string
        code_breakdown_parts = []
        for code, services in sorted(
            stats["code_breakdown"].items(), key=lambda x: x[1], reverse=True
        ):
            code_breakdown_parts.append(f"{code} ({int(services):,})")
        code_breakdown = ", ".join(code_breakdown_parts[:5])  # Top 5 codes
        if len(code_breakdown_parts) > 5:
            code_breakdown += f" (+{len(code_breakdown_parts) - 5} more)"
        
        rows.append({
            "facility_id": facility_id,
            "hospital_name": stats["hospital_name"],
            "hospital_city": stats["hospital_city"],
            "hospital_state": stats["hospital_state"],
            "total_procedures": stats["total_procedures"],
            "total_payments": stats["total_payments"],
            "num_physicians": num_physicians,
            "avg_procedures_per_physician": avg_procedures,
            "code_breakdown": code_breakdown,
        })
    
    df = pd.DataFrame(rows)
    
    # Apply min_procedures filter
    if min_procedures is not None:
        df = df[df["total_procedures"] >= min_procedures]
    
    # Sort by total procedures descending
    df = df.sort_values("total_procedures", ascending=False)
    
    # Limit results
    df = df.head(max_rows)
    
    return df


def get_hospital_physicians(
    facility_id: str,
    codes: list[str] | None = None,
    max_rows: int = 100,
) -> pd.DataFrame:
    """
    Get physicians affiliated with a specific hospital - optimized version.
    Delegates to optimized implementation.
    """
    if not codes:
        return pd.DataFrame()
    
    # Import here to avoid circular dependency
    from .hospital_analytics_optimized import get_hospital_physicians_optimized
    return get_hospital_physicians_optimized(facility_id, codes, max_rows)

