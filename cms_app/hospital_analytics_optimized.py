"""Optimized Hospital-Level Analytics System.

Performance-optimized version focusing on hospital systems.
Key optimizations:
- Early filtering by codes/states before aggregation
- Efficient set-based lookups
- Minimal data loading
- Direct hospital aggregation without intermediate NPI aggregation where possible
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from .cms_query import get_paths, load_facility_affiliations, load_hospital_metadata, normalize_codes, normalize_states
from .cms_columns import (
    detect_hcpcs_col,
    detect_npi_col,
    detect_services_col,
    detect_state_col,
    detect_total_payment_col,
)


def hospitals_by_codes_optimized(
    codes: List[str],
    states: Optional[List[str]] = None,
    min_procedures: Optional[int] = None,
    max_rows: int = 250,
) -> pd.DataFrame:
    """
    Optimized hospital aggregation - filters early and uses efficient data structures.
    
    Performance improvements:
    1. Filter by codes/states in the chunk loop (early exit)
    2. Use sets for fast lookups
    3. Pre-load and cache hospital metadata
    4. Direct aggregation to hospital level
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
    
    # Convert to sets for O(1) lookup
    codes_set = set(codes_n)
    states_set = set(states_n) if states_n else None
    
    # Pre-load hospital data (cached)
    try:
        affiliations_df = load_facility_affiliations()
        hospitals_df = load_hospital_metadata()
    except Exception as e:
        from .logger import logger
        logger.error(f"Error loading hospital data: {e}", exc_info=True)
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
    
    # Build lookup maps for efficiency
    # NPI -> set of facility_ids
    npi_to_facilities: Dict[str, set[str]] = {}
    for _, row in affiliations_df.iterrows():
        npi = str(row["npi"]).strip()
        fac_id = str(row["facility_id"]).strip()
        if npi and fac_id:
            if npi not in npi_to_facilities:
                npi_to_facilities[npi] = set()
            npi_to_facilities[npi].add(fac_id)
    
    # Facility ID -> hospital info
    facility_to_hospital: Dict[str, Dict[str, Any]] = {}
    for _, row in hospitals_df.iterrows():
        fac_id = str(row["facility_id"]).strip()
        if fac_id:
            facility_to_hospital[fac_id] = {
                "hospital_name": str(row.get("hospital_name", "")),
                "hospital_city": str(row.get("hospital_city", "")),
                "hospital_state": str(row.get("hospital_state", "")),
            }
    
    # Read and process physician data
    path = get_paths().physician_puf
    header = list(pd.read_csv(path, nrows=0, low_memory=False).columns)
    
    npi_col = detect_npi_col(header)
    hcpcs_col = detect_hcpcs_col(header)
    state_col = detect_state_col(header)
    services_col = detect_services_col(header)
    total_payment_col = detect_total_payment_col(header)
    
    usecols = [c for c in [npi_col, hcpcs_col, state_col, services_col, total_payment_col] if c]
    
    # Direct hospital-level aggregation
    hospital_stats: Dict[str, Dict[str, Any]] = {}
    
    chunksize = 500_000  # Larger chunks for better performance
    processed_rows = 0
    
    for chunk in pd.read_csv(path, usecols=usecols, low_memory=False, chunksize=chunksize):
        # Early filtering in pandas (vectorized)
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
        
        # Convert to string and normalize
        chunk["npi"] = chunk["npi"].astype(str).str.strip()
        chunk["code"] = chunk["code"].astype(str).str.strip().str.upper()
        chunk["state"] = chunk["state"].astype(str).str.strip().str.upper()
        
        # Early filter by codes and states (vectorized operations)
        chunk = chunk[chunk["code"].isin(codes_set)]
        if chunk.empty:
            continue
            
        if states_set:
            chunk = chunk[chunk["state"].isin(states_set)]
        if chunk.empty:
            continue
        
        # Convert numeric columns
        chunk["services"] = pd.to_numeric(chunk["services"], errors="coerce").fillna(0)
        if "total_payment" in chunk.columns:
            chunk["total_payment"] = pd.to_numeric(chunk["total_payment"], errors="coerce").fillna(0)
        else:
            chunk["total_payment"] = 0.0
        
        # Filter out NPIs without hospital affiliations (vectorized)
        chunk["has_facilities"] = chunk["npi"].isin(npi_to_facilities.keys())
        chunk = chunk[chunk["has_facilities"]].copy()
        if chunk.empty:
            continue
        
        # Expand: create one row per NPI-facility combination
        # Use list comprehension which is faster than iterrows
        expanded_rows = []
        npi_list = chunk["npi"].tolist()
        code_list = chunk["code"].tolist()
        services_list = chunk["services"].tolist()
        payment_list = chunk["total_payment"].tolist()
        
        for i, npi in enumerate(npi_list):
            facilities = npi_to_facilities.get(npi, set())
            for fac_id in facilities:
                if fac_id in facility_to_hospital:
                    expanded_rows.append({
                        "facility_id": fac_id,
                        "npi": npi,
                        "code": code_list[i],
                        "services": services_list[i],
                        "payment": payment_list[i],
                    })
        
        if not expanded_rows:
            continue
        
        # Convert to DataFrame and aggregate by facility (vectorized)
        expanded_df = pd.DataFrame(expanded_rows)
        
        # Group by facility and aggregate (much faster than iterrows)
        facility_groups = expanded_df.groupby("facility_id", sort=False)
        
        for fac_id, group in facility_groups:
            if fac_id not in hospital_stats:
                hosp_info = facility_to_hospital[fac_id]
                hospital_stats[fac_id] = {
                    "facility_id": fac_id,
                    "hospital_name": hosp_info["hospital_name"],
                    "hospital_city": hosp_info["hospital_city"],
                    "hospital_state": hosp_info["hospital_state"],
                    "total_procedures": 0.0,
                    "total_payments": 0.0,
                    "physicians": set(),
                    "code_breakdown": {},
                }
            
            # Aggregate using pandas operations (much faster)
            hospital_stats[fac_id]["total_procedures"] += float(group["services"].sum())
            hospital_stats[fac_id]["total_payments"] += float(group["payment"].sum())
            hospital_stats[fac_id]["physicians"].update(group["npi"].unique())
            
            # Aggregate code breakdown (vectorized)
            code_groups = group.groupby("code", sort=False)["services"].sum()
            for code, services in code_groups.items():
                hospital_stats[fac_id]["code_breakdown"][code] = (
                    hospital_stats[fac_id]["code_breakdown"].get(code, 0.0) + float(services)
                )
        
        processed_rows += len(chunk)
        if processed_rows % 2_000_000 == 0:
            logger.info(f"Processed {processed_rows:,} rows, found {len(hospital_stats)} hospitals so far")
        # Early exit if we've processed enough (optional optimization)
        if processed_rows > 5_000_000:  # Reduced from 10M for faster response
            logger.info(f"Early exit after processing {processed_rows:,} rows")
            break
    
    logger.info(f"Completed processing. Found {len(hospital_stats)} hospitals from {processed_rows:,} rows")
    
    if not hospital_stats:
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
    
    # Convert to DataFrame
    rows = []
    for fac_id, stats in hospital_stats.items():
        num_physicians = len(stats["physicians"])
        avg_procedures = (
            stats["total_procedures"] / num_physicians if num_physicians > 0 else 0.0
        )
        
        # Build code breakdown string (top 5)
        code_breakdown_parts = []
        for code, services in sorted(
            stats["code_breakdown"].items(), key=lambda x: x[1], reverse=True
        )[:5]:
            code_breakdown_parts.append(f"{code} ({int(services):,})")
        code_breakdown = ", ".join(code_breakdown_parts)
        if len(stats["code_breakdown"]) > 5:
            code_breakdown += f" (+{len(stats['code_breakdown']) - 5} more)"
        
        rows.append({
            "facility_id": fac_id,
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


def get_hospital_physicians_optimized(
    facility_id: str,
    codes: List[str],
    max_rows: int = 100,
) -> pd.DataFrame:
    """
    Optimized version - only processes data for the specific hospital and codes.
    Much faster than loading all doctors then filtering.
    """
    from .cms_query import get_paths, load_facility_affiliations, normalize_codes
    from .cms_columns import (
        detect_first_name_col,
        detect_hcpcs_col,
        detect_last_name_col,
        detect_npi_col,
        detect_services_col,
        detect_specialty_col,
        detect_state_col,
        detect_total_payment_col,
    )
    
    codes_n = normalize_codes(codes)
    if not codes_n:
        return pd.DataFrame()
    
    codes_set = set(codes_n)
    
    # Get NPIs for this facility
    affiliations = load_facility_affiliations()
    npi_set = set(
        str(npi).strip()
        for npi in affiliations[affiliations["facility_id"] == facility_id]["npi"].tolist()
    )
    
    if not npi_set:
        return pd.DataFrame()
    
    # Read physician data and filter early
    path = get_paths().physician_puf
    header = list(pd.read_csv(path, nrows=0, low_memory=False).columns)
    
    npi_col = detect_npi_col(header)
    hcpcs_col = detect_hcpcs_col(header)
    services_col = detect_services_col(header)
    total_payment_col = detect_total_payment_col(header)
    last_col = detect_last_name_col(header)
    first_col = detect_first_name_col(header)
    specialty_col = detect_specialty_col(header)
    state_col = detect_state_col(header)
    
    usecols = [c for c in [
        npi_col, hcpcs_col, services_col, total_payment_col,
        last_col, first_col, specialty_col, state_col
    ] if c]
    
    # Aggregate by NPI
    npi_totals: Dict[str, Dict[str, Any]] = {}
    npi_info: Dict[str, Dict[str, str]] = {}
    
    chunksize = 500_000
    for chunk in pd.read_csv(path, usecols=usecols, low_memory=False, chunksize=chunksize):
        chunk = chunk.rename(
            columns={
                npi_col: "npi",
                hcpcs_col: "code",
                services_col: "services",
                (total_payment_col or ""): "total_payment",
                (last_col or ""): "last_name",
                (first_col or ""): "first_name",
                (specialty_col or ""): "specialty",
                (state_col or ""): "state",
            }
        )
        if "" in chunk.columns:
            chunk = chunk.drop(columns=[""])
        
        chunk["npi"] = chunk["npi"].astype(str).str.strip()
        chunk["code"] = chunk["code"].astype(str).str.strip().str.upper()
        
        # Early filter: only NPIs in this hospital, only codes we care about
        chunk = chunk[chunk["npi"].isin(npi_set)]
        if chunk.empty:
            continue
        chunk = chunk[chunk["code"].isin(codes_set)]
        if chunk.empty:
            continue
        
        chunk["services"] = pd.to_numeric(chunk["services"], errors="coerce").fillna(0)
        if "total_payment" in chunk.columns:
            chunk["total_payment"] = pd.to_numeric(chunk["total_payment"], errors="coerce").fillna(0)
        else:
            chunk["total_payment"] = 0.0
        
        # Aggregate
        for _, row in chunk.iterrows():
            npi = str(row["npi"])
            services = float(row["services"])
            payment = float(row.get("total_payment", 0))
            
            if npi not in npi_totals:
                npi_totals[npi] = {"services": 0.0, "payments": 0.0}
                npi_info[npi] = {
                    "last_name": str(row.get("last_name", "")),
                    "first_name": str(row.get("first_name", "")),
                    "specialty": str(row.get("specialty", "")),
                    "state": str(row.get("state", "")),
                }
            
            npi_totals[npi]["services"] += services
            npi_totals[npi]["payments"] += payment
    
    if not npi_totals:
        return pd.DataFrame()
    
    # Build DataFrame
    rows = []
    for npi, totals in npi_totals.items():
        info = npi_info[npi]
        last = info["last_name"].strip()
        first = info["first_name"].strip()
        name = f"{last}, {first}" if last and first else (last or first)
        
        rows.append({
            "npi": npi,
            "doctor_name": name,
            "specialty": info["specialty"],
            "state": info["state"],
            "total_services_selected_codes": totals["services"],
            "total_payments_selected_codes": totals["payments"],
        })
    
    df = pd.DataFrame(rows)
    df = df.sort_values("total_services_selected_codes", ascending=False)
    return df.head(max_rows)

