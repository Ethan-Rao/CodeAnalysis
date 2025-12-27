"""Analytics for referring provider data (refHCPCS.csv) - HCPCS A-codes."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from .cms_query import get_paths, load_facility_affiliations, load_hospital_metadata, normalize_codes, normalize_states
from .cms_columns import (
    detect_avg_payment_col,
    detect_hcpcs_col,
    detect_npi_col,
    detect_services_col,
    detect_state_col,
    detect_total_payment_col,
)
from .logger import logger


def _detect_referring_columns(header: list[str]) -> dict[str, str | None]:
    """Detect columns in referring provider dataset (refHCPCS.csv)."""
    from .puf_utils import pick_column
    
    # Referring provider uses different column names
    npi_col = pick_column(
        header,
        preferred_exact=("Rfrg_NPI", "npi"),
        contains_any=("rfrg", "referr", "npi"),
    )
    hcpcs_col = detect_hcpcs_col(header)
    state_col = pick_column(
        header,
        preferred_exact=("Rfrg_Prvdr_State_Abrvtn",),
        contains_any=("state", "abrvtn"),
    )
    services_col = pick_column(
        header,
        preferred_exact=("Tot_Suplr_Srvcs", "Tot_Srvcs"),
        contains_any=("srvcs", "srvc", "service"),
    )
    total_payment_col = detect_total_payment_col(header)
    avg_payment_col = detect_avg_payment_col(header)
    
    return {
        "npi": npi_col,
        "hcpcs": hcpcs_col,
        "state": state_col,
        "services": services_col,
        "total_payment": total_payment_col,
        "avg_payment": avg_payment_col,
    }


def hospitals_by_hcpcs_codes(
    codes: List[str],
    states: Optional[List[str]] = None,
    min_procedures: Optional[int] = None,
    max_rows: int = 250,
) -> pd.DataFrame:
    """
    Hospital aggregation for HCPCS codes from referring provider dataset.
    Note: Referring providers may not have direct hospital affiliations like rendering providers.
    This aggregates by the referring provider's hospital affiliations.
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
    
    codes_set = set(codes_n)
    states_set = set(states_n) if states_n else None
    
    # Load hospital data
    try:
        affiliations_df = load_facility_affiliations()
        hospitals_df = load_hospital_metadata()
    except Exception as e:
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
    
    # Build lookup maps
    npi_to_facilities: Dict[str, set[str]] = {}
    for _, row in affiliations_df.iterrows():
        npi = str(row["npi"]).strip()
        fac_id = str(row["facility_id"]).strip()
        if npi and fac_id:
            if npi not in npi_to_facilities:
                npi_to_facilities[npi] = set()
            npi_to_facilities[npi].add(fac_id)
    
    facility_to_hospital: Dict[str, Dict[str, Any]] = {}
    for _, row in hospitals_df.iterrows():
        fac_id = str(row["facility_id"]).strip()
        if fac_id:
            facility_to_hospital[fac_id] = {
                "hospital_name": str(row.get("hospital_name", "")),
                "hospital_city": str(row.get("hospital_city", "")),
                "hospital_state": str(row.get("hospital_state", "")),
            }
    
    # Read referring provider data
    path = get_paths().referring_puf
    if not path.exists():
        logger.warning(f"Referring provider file not found: {path}")
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
    
    header = list(pd.read_csv(path, nrows=0, low_memory=False).columns)
    cols = _detect_referring_columns(header)
    
    usecols = [c for c in [cols["npi"], cols["hcpcs"], cols["state"], cols["services"], cols["total_payment"], cols["avg_payment"]] if c]
    
    hospital_stats: Dict[str, Dict[str, Any]] = {}
    chunksize = 500_000
    processed_rows = 0
    
    logger.info(f"Starting HCPCS hospital aggregation for codes: {codes_n}, states: {states_n}")
    
    for chunk in pd.read_csv(path, usecols=usecols, low_memory=False, chunksize=chunksize):
        # Rename columns
        rename_dict = {
            cols["npi"]: "npi",
            cols["hcpcs"]: "code",
            cols["state"]: "state",
            cols["services"]: "services",
        }
        if cols["total_payment"]:
            rename_dict[cols["total_payment"]] = "total_payment"
        if cols["avg_payment"]:
            rename_dict[cols["avg_payment"]] = "avg_payment"
        
        chunk = chunk.rename(columns=rename_dict)
        
        # Normalize
        chunk["npi"] = chunk["npi"].astype(str).str.strip()
        chunk["code"] = chunk["code"].astype(str).str.strip().str.upper()
        chunk["state"] = chunk["state"].astype(str).str.strip().str.upper()
        
        # Filter
        chunk = chunk[chunk["code"].isin(codes_set)]
        if chunk.empty:
            continue
        
        if states_set:
            chunk = chunk[chunk["state"].isin(states_set)]
        if chunk.empty:
            continue
        
        # Convert numeric
        chunk["services"] = pd.to_numeric(chunk["services"], errors="coerce").fillna(0)
        
        if "total_payment" in chunk.columns:
            chunk["total_payment"] = pd.to_numeric(chunk["total_payment"], errors="coerce").fillna(0)
        elif "avg_payment" in chunk.columns:
            chunk["avg_payment"] = pd.to_numeric(chunk["avg_payment"], errors="coerce").fillna(0)
            chunk["total_payment"] = chunk["avg_payment"] * chunk["services"]
        else:
            chunk["total_payment"] = 0.0
        
        # Filter NPIs with facilities
        chunk["has_facilities"] = chunk["npi"].isin(npi_to_facilities.keys())
        chunk = chunk[chunk["has_facilities"]].copy()
        if chunk.empty:
            continue
        
        # Expand and aggregate (same logic as optimized version)
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
        
        expanded_df = pd.DataFrame(expanded_rows)
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
            
            hospital_stats[fac_id]["total_procedures"] += float(group["services"].sum())
            hospital_stats[fac_id]["total_payments"] += float(group["payment"].sum())
            hospital_stats[fac_id]["physicians"].update(group["npi"].unique())
            
            code_groups = group.groupby("code", sort=False)["services"].sum()
            for code, services in code_groups.items():
                hospital_stats[fac_id]["code_breakdown"][code] = (
                    hospital_stats[fac_id]["code_breakdown"].get(code, 0.0) + float(services)
                )
        
        processed_rows += len(chunk)
        if processed_rows > 5_000_000:
            break
    
    logger.info(f"Completed HCPCS processing. Found {len(hospital_stats)} hospitals from {processed_rows:,} rows")
    
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
        avg_procedures = stats["total_procedures"] / num_physicians if num_physicians > 0 else 0.0
        
        code_breakdown_parts = []
        for code, services in sorted(stats["code_breakdown"].items(), key=lambda x: x[1], reverse=True)[:5]:
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
    
    if min_procedures is not None:
        df = df[df["total_procedures"] >= min_procedures]
    
    df = df.sort_values("total_procedures", ascending=False)
    return df.head(max_rows)

