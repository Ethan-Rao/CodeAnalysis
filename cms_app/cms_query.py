from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .cms_columns import (
    detect_affiliation_facility_id_col,
    detect_avg_payment_col,
    detect_city_col,
    detect_first_name_col,
    detect_hcpcs_col,
    detect_hcpcs_desc_col,
    detect_hospital_city_col,
    detect_hospital_id_col,
    detect_hospital_name_col,
    detect_hospital_state_col,
    detect_last_name_col,
    detect_npi_col,
    detect_services_col,
    detect_specialty_col,
    detect_state_col,
    detect_total_payment_col,
    normalize_codes,
    normalize_states,
)


@dataclass(frozen=True)
class DataPaths:
    root: Path

    @property
    def physician_puf(self) -> Path:
        return self.root / "physHCPCS.csv"
    
    @property
    def referring_puf(self) -> Path:
        return self.root / "refHCPCS.csv"

    @property
    def facility_affiliation(self) -> Path:
        return self.root / "Doctors_08_2025" / "Facility_Affiliation.csv"

    @property
    def hospital_general_info(self) -> Path:
        hospitals_dir = self.root / "hospitals_08_2025"
        if not hospitals_dir.exists():
            hospitals_dir = self.root / "Hospitals_08_2025"
        return hospitals_dir / "Hospital_General_Information.csv"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_paths() -> DataPaths:
    return DataPaths(root=_project_root())


@lru_cache(maxsize=4)
def _phys_puf_header(path: str) -> list[str]:
    return list(pd.read_csv(path, nrows=0, low_memory=False).columns)


@lru_cache(maxsize=2)
def load_hospital_metadata() -> pd.DataFrame:
    """Hospital metadata keyed by Facility ID."""
    path = get_paths().hospital_general_info
    cols = list(pd.read_csv(path, nrows=0, low_memory=False).columns)

    id_col = detect_hospital_id_col(cols)
    name_col = detect_hospital_name_col(cols)
    city_col = detect_hospital_city_col(cols)
    state_col = detect_hospital_state_col(cols)

    usecols = [c for c in [id_col, name_col, city_col, state_col] if c]
    df = pd.read_csv(path, usecols=usecols, low_memory=False)
    df = df.rename(
        columns={
            id_col: "facility_id",
            name_col: "hospital_name",
            (city_col or ""): "hospital_city",
            (state_col or ""): "hospital_state",
        }
    )
    if "" in df.columns:
        df = df.drop(columns=[""])

    df["facility_id"] = df["facility_id"].astype(str).str.strip()
    df["hospital_name"] = df["hospital_name"].astype(str).str.strip()
    if "hospital_city" in df.columns:
        df["hospital_city"] = df["hospital_city"].astype(str).str.strip()
    if "hospital_state" in df.columns:
        df["hospital_state"] = df["hospital_state"].astype(str).str.strip().str.upper()

    df = df.dropna(subset=["facility_id"]).drop_duplicates(subset=["facility_id"], keep="first")
    return df


@lru_cache(maxsize=2)
def load_facility_affiliations() -> pd.DataFrame:
    """Mapping NPI -> Facility ID (hospital certification number)."""
    path = get_paths().facility_affiliation
    cols = list(pd.read_csv(path, nrows=0, low_memory=False).columns)

    npi_col = detect_npi_col(cols)
    fac_col = detect_affiliation_facility_id_col(cols)

    usecols = [npi_col, fac_col]
    df = pd.read_csv(path, usecols=usecols, low_memory=False)
    df = df.rename(columns={npi_col: "npi", fac_col: "facility_id"})
    df["npi"] = df["npi"].astype(str).str.strip()
    df["facility_id"] = df["facility_id"].astype(str).str.strip()
    df = df[(df["npi"] != "") & (df["facility_id"] != "")]
    df = df.drop_duplicates()
    return df


def attach_hospital_affiliations(df_doctors: pd.DataFrame) -> pd.DataFrame:
    """
    Input: df with an 'npi' column.
    Output: same df with extra columns:
      - primary_hospital_name
      - primary_hospital_city
      - primary_hospital_state
      - hospital_summary
    """
    if df_doctors.empty:
        for c in [
            "primary_hospital_name",
            "primary_hospital_city",
            "primary_hospital_state",
            "hospital_summary",
        ]:
            df_doctors[c] = pd.NA
        return df_doctors

    if "npi" not in df_doctors.columns:
        raise KeyError("attach_hospital_affiliations expects column 'npi'")

    aff = load_facility_affiliations()
    hosp = load_hospital_metadata()

    m = aff.merge(hosp, on="facility_id", how="left")

    def _agg(group: pd.DataFrame) -> pd.Series:
        rows = group.dropna(subset=["hospital_name"])
        if rows.empty:
            return pd.Series(
                {
                    "primary_hospital_name": pd.NA,
                    "primary_hospital_city": pd.NA,
                    "primary_hospital_state": pd.NA,
                    "hospital_summary": pd.NA,
                }
            )

        rows = rows.drop_duplicates(subset=["hospital_name", "hospital_state", "hospital_city"]).copy()
        rows = rows.sort_values(["hospital_name", "hospital_state"], kind="mergesort")

        primary = rows.iloc[0]
        parts = []
        for _, r in rows.iterrows():
            nm = str(r.get("hospital_name", "")).strip()
            st = str(r.get("hospital_state", "")).strip()
            if nm:
                parts.append(f"{nm} ({st})" if st else nm)

        summary = ", ".join(parts)
        if len(summary) > 140:
            summary = summary[:137] + "..."

        return pd.Series(
            {
                "primary_hospital_name": primary.get("hospital_name", pd.NA),
                "primary_hospital_city": primary.get("hospital_city", pd.NA),
                "primary_hospital_state": primary.get("hospital_state", pd.NA),
                "hospital_summary": summary,
            }
        )

    agg = m.groupby("npi", sort=False).apply(_agg).reset_index()

    out = df_doctors.merge(agg, on="npi", how="left")
    return out


def _parse_codes_breakdown(breakdown: pd.Series) -> str:
    # breakdown is a Series with (hcpcs, services) pairs after sorting
    parts = [f"{code} ({int(svc):,})" for code, svc in breakdown.items() if svc and svc > 0]
    s = ", ".join(parts)
    if len(s) > 180:
        s = s[:177] + "..."
    return s


def doctors_by_codes(
    codes: list[str],
    states: list[str] | None = None,
    min_services: int | None = None,
    max_rows: int = 250,
) -> pd.DataFrame:
    """
    Search for doctors by codes. Routes to appropriate dataset:
    - HCPCS codes (letter-prefixed) -> refHCPCS.csv
    - CPT codes (numeric) -> physHCPCS.csv
    """
    from .code_type_detection import split_codes_by_type
    
    # Split codes by type
    hcpcs_codes, cpt_codes = split_codes_by_type(codes)
    
    results = []
    
    # Search HCPCS codes in referring provider dataset
    if hcpcs_codes:
        hcpcs_df = _doctors_by_hcpcs_codes(hcpcs_codes, states, min_services, max_rows)
        if not hcpcs_df.empty:
            results.append(hcpcs_df)
    
    # Search CPT codes in physician dataset
    if cpt_codes:
        cpt_df = _doctors_by_cpt_codes(cpt_codes, states, min_services, max_rows)
        if not cpt_df.empty:
            results.append(cpt_df)
    
    # Combine results
    if not results:
        return pd.DataFrame(
            columns=[
                "doctor_name",
                "npi",
                "specialty",
                "city",
                "state",
                "primary_hospital_name",
                "primary_hospital_city",
                "primary_hospital_state",
                "hospital_summary",
                "total_services_selected_codes",
                "total_payments_selected_codes",
                "code_breakdown",
            ]
        )
    
    # Combine and deduplicate by NPI
    combined = pd.concat(results, ignore_index=True)
    # Group by NPI and aggregate
    grouped = combined.groupby("npi", sort=False).agg({
        "doctor_name": "first",
        "specialty": "first",
        "city": "first",
        "state": "first",
        "primary_hospital_name": "first",
        "primary_hospital_city": "first",
        "primary_hospital_state": "first",
        "hospital_summary": "first",
        "total_services_selected_codes": "sum",
        "total_payments_selected_codes": "sum",
        "code_breakdown": lambda x: ", ".join([str(s) for s in x if pd.notna(s)])[:200],
    }).reset_index()
    
    # Sort and limit
    grouped = grouped.sort_values("total_services_selected_codes", ascending=False)
    return grouped.head(max_rows)


def _doctors_by_cpt_codes(
    codes: list[str],
    states: list[str] | None = None,
    min_services: int | None = None,
    max_rows: int = 250,
) -> pd.DataFrame:
    """
    Original doctors_by_codes implementation for CPT codes (physHCPCS.csv).
    Return a DataFrame of doctors ranked by total services for selected HCPCS/CPT codes,
    with hospital affiliation information attached.
    
    Args:
        codes: List of HCPCS/CPT codes to search (e.g., ['62270', 'L8679']).
               Codes are normalized to uppercase and whitespace is stripped.
        states: Optional list of 2-letter state codes to filter by (e.g., ['CA', 'OR']).
                Invalid codes are ignored. If None or empty, searches all states.
        min_services: Optional minimum number of procedures to filter out low-volume providers.
                      If None, no minimum threshold is applied.
        max_rows: Maximum number of results to return (default: 250).
                  Results are sorted by total services (descending).
    
    Returns:
        DataFrame with columns:
        - doctor_name: Full name (Last, First)
        - npi: National Provider Identifier
        - specialty: Provider specialty
        - city: Provider city
        - state: Provider state (2-letter code)
        - primary_hospital_name: Primary affiliated hospital name
        - primary_hospital_city: Primary hospital city
        - primary_hospital_state: Primary hospital state
        - hospital_summary: Summary of all hospital affiliations
        - total_services_selected_codes: Total procedures for selected codes
        - total_payments_selected_codes: Total Medicare payments
        - code_breakdown: String showing code distribution (e.g., "62270 (480), 62272 (210)")
    
    Example:
        >>> df = doctors_by_codes(['62270'], states=['CA'], min_services=10)
        >>> print(df.head())
    
    Note:
        - Reads from physHCPCS.csv in chunks for memory efficiency
        - Hospital affiliations are joined from Facility_Affiliation.csv and Hospital_General_Information.csv
        - Empty DataFrame is returned if no codes provided or no matching results
    """
    codes_n = normalize_codes(codes)
    states_n = normalize_states(states)

    if not codes_n:
        return pd.DataFrame(
            columns=[
                "doctor_name",
                "npi",
                "specialty",
                "city",
                "state",
                "primary_hospital_name",
                "primary_hospital_city",
                "primary_hospital_state",
                "hospital_summary",
                "total_services_selected_codes",
                "total_payments_selected_codes",
                "code_breakdown",
            ]
        )

    path = get_paths().physician_puf
    header = _phys_puf_header(str(path))

    npi_col = detect_npi_col(header)
    hcpcs_col = detect_hcpcs_col(header)
    state_col = detect_state_col(header)
    services_col = detect_services_col(header)

    total_payment_col = detect_total_payment_col(header)
    avg_payment_col = detect_avg_payment_col(header)

    last_col = detect_last_name_col(header)
    first_col = detect_first_name_col(header)
    city_col = detect_city_col(header)
    specialty_col = detect_specialty_col(header)
    hcpcs_desc_col = detect_hcpcs_desc_col(header)

    usecols = [c for c in [
        npi_col,
        hcpcs_col,
        state_col,
        services_col,
        total_payment_col,
        avg_payment_col,
        last_col,
        first_col,
        city_col,
        specialty_col,
        hcpcs_desc_col,
    ] if c]

    # Streaming aggregation
    totals_services: dict[str, float] = {}
    totals_pay: dict[str, float] = {}
    info_rows: list[pd.DataFrame] = []

    breakdown_parts: list[pd.DataFrame] = []

    chunksize = 250_000
    for chunk in pd.read_csv(path, usecols=usecols, low_memory=False, chunksize=chunksize):
        chunk = chunk.rename(
            columns={
                npi_col: "npi",
                hcpcs_col: "code",
                state_col: "state",
                services_col: "services",
                (total_payment_col or ""): "total_payment",
                (avg_payment_col or ""): "avg_payment",
                (last_col or ""): "last_name",
                (first_col or ""): "first_name",
                (city_col or ""): "city",
                (specialty_col or ""): "specialty",
                (hcpcs_desc_col or ""): "code_desc",
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

        if "total_payment" in chunk.columns and chunk["total_payment"].notna().any():
            chunk["total_payment"] = pd.to_numeric(chunk["total_payment"], errors="coerce").fillna(0)
        else:
            if "avg_payment" in chunk.columns:
                chunk["avg_payment"] = pd.to_numeric(chunk["avg_payment"], errors="coerce").fillna(0)
                chunk["total_payment"] = chunk["avg_payment"] * chunk["services"]
            else:
                chunk["total_payment"] = 0.0

        by_npi = chunk.groupby("npi", sort=False).agg({"services": "sum", "total_payment": "sum"})
        for npi, row in by_npi.iterrows():
            totals_services[npi] = totals_services.get(npi, 0.0) + float(row["services"])
            totals_pay[npi] = totals_pay.get(npi, 0.0) + float(row["total_payment"])

        # Info rows (one per npi)
        info_cols = [c for c in ["npi", "last_name", "first_name", "city", "state", "specialty"] if c in chunk.columns]
        info_rows.append(chunk[info_cols].drop_duplicates(subset=["npi"], keep="first"))

        # Breakdown
        breakdown_parts.append(chunk[["npi", "code", "services"]])

    if not totals_services:
        return pd.DataFrame(
            columns=[
                "doctor_name",
                "npi",
                "specialty",
                "city",
                "state",
                "primary_hospital_name",
                "primary_hospital_city",
                "primary_hospital_state",
                "hospital_summary",
                "total_services_selected_codes",
                "total_payments_selected_codes",
                "code_breakdown",
            ]
        )

    totals_df = pd.DataFrame(
        {
            "npi": list(totals_services.keys()),
            "total_services_selected_codes": [totals_services[n] for n in totals_services.keys()],
            "total_payments_selected_codes": [totals_pay.get(n, 0.0) for n in totals_services.keys()],
        }
    )

    if min_services is not None:
        try:
            ms = int(min_services)
            totals_df = totals_df[totals_df["total_services_selected_codes"] >= ms]
        except Exception:
            pass

    # Join representative info
    info_df = pd.concat(info_rows, ignore_index=True) if info_rows else pd.DataFrame(columns=["npi"])
    if not info_df.empty:
        info_df = info_df.drop_duplicates(subset=["npi"], keep="first")

    def _mk_name(r):
        last = str(r.get("last_name", "")).strip()
        first = str(r.get("first_name", "")).strip()
        if last and first:
            return f"{last}, {first}"
        return last or first

    if not info_df.empty:
        info_df["doctor_name"] = info_df.apply(_mk_name, axis=1)

    out = totals_df.merge(info_df, on="npi", how="left")

    # Code breakdown string
    if breakdown_parts:
        bd = pd.concat(breakdown_parts, ignore_index=True)
        bd = bd.groupby(["npi", "code"], sort=False)["services"].sum().reset_index()
        bd = bd.sort_values(["npi", "services"], ascending=[True, False], kind="mergesort")

        def _per_npi(group: pd.DataFrame) -> str:
            s = pd.Series(group["services"].values, index=group["code"].values)
            return _parse_codes_breakdown(s)

        bd2 = bd.groupby("npi", sort=False).apply(_per_npi).reset_index(name="code_breakdown")
        out = out.merge(bd2, on="npi", how="left")
    else:
        out["code_breakdown"] = pd.NA

    # Attach hospitals
    out = attach_hospital_affiliations(out)

    # Clean columns
    if "specialty" not in out.columns:
        out["specialty"] = pd.NA
    if "city" not in out.columns:
        out["city"] = pd.NA
    if "state" not in out.columns:
        out["state"] = pd.NA

    out = out.sort_values(
        ["total_services_selected_codes", "total_payments_selected_codes"],
        ascending=[False, False],
        kind="mergesort",
    )

    out = out.head(max_rows)

    keep = [
        "doctor_name",
        "npi",
        "specialty",
        "city",
        "state",
        "primary_hospital_name",
        "primary_hospital_city",
        "primary_hospital_state",
        "hospital_summary",
        "total_services_selected_codes",
        "total_payments_selected_codes",
        "code_breakdown",
    ]
    for c in keep:
        if c not in out.columns:
            out[c] = pd.NA

    return out[keep]


DOCTORS_BY_CODE_UI_COLUMNS: list[tuple[str, str]] = [
    ("doctor_name", "Doctor name"),
    ("npi", "NPI"),
    ("specialty", "Specialty"),
    ("city", "City"),
    ("state", "State"),
    ("primary_hospital_name", "Primary hospital"),
    ("primary_hospital_city", "Hospital city"),
    ("primary_hospital_state", "Hospital state"),
    ("total_services_selected_codes", "Number of procedures"),
    ("total_payments_selected_codes", "Total Medicare payments"),
    ("code_breakdown", "Code breakdown"),
]
