from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class DoctorsFiles:
    utilization: Path
    national: Path
    affiliation: Path | None = None


@dataclass(frozen=True)
class HospitalFiles:
    general_info: Path


def _require_file(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Not a file for {label}: {path}")
    return path


def discover_doctors_files(base_dir: Path) -> DoctorsFiles:
    """Discover key Doctors & Clinicians files without renaming any raw CSVs."""
    base_dir = Path(base_dir)
    util = base_dir / "Utilization.csv"
    nat = base_dir / "DAC_NationalDownloadableFile.csv"
    aff = base_dir / "Facility_Affiliation.csv"

    _require_file(util, "doctors utilization")
    _require_file(nat, "doctors national")
    if aff.exists() and aff.is_file():
        aff_path: Path | None = aff
    else:
        aff_path = None

    return DoctorsFiles(utilization=util, national=nat, affiliation=aff_path)


def discover_hospital_files(base_dir: Path) -> HospitalFiles:
    """Discover key Hospital files without renaming any raw CSVs."""
    base_dir = Path(base_dir)

    # In your dataset this exists explicitly.
    gi = base_dir / "Hospital_General_Information.csv"
    if gi.exists():
        return HospitalFiles(general_info=_require_file(gi, "hospital general info"))

    # Fallback heuristic: try to find a best match.
    candidates = list(base_dir.glob("*.csv"))
    best = None
    for p in candidates:
        name = p.name.lower()
        if "general" in name and "hospital" in name and "information" in name:
            best = p
            break
    if not best:
        raise FileNotFoundError(
            f"Could not find Hospital general info CSV in {base_dir}. "
            "Expected Hospital_General_Information.csv (or similar)."
        )
    return HospitalFiles(general_info=_require_file(best, "hospital general info"))


def _first_existing(columns: Iterable[str], *names: str) -> str | None:
    lower_map = {c.lower(): c for c in columns}
    for n in names:
        c = lower_map.get(n.lower())
        if c:
            return c
    return None


def _find_col_contains(columns: Iterable[str], *needles: str) -> str | None:
    cols = list(columns)
    cols_lower = [c.lower() for c in cols]
    for needle in needles:
        n = needle.lower()
        for idx, c in enumerate(cols_lower):
            if n in c:
                return cols[idx]
    return None


def _read_columns(path: Path) -> list[str]:
    return list(pd.read_csv(path, nrows=0).columns)


def load_doctors(util_path: Path, nat_path: Path) -> pd.DataFrame:
    """Load and normalize Doctors master dataframe (utilization + national, joined on NPI)."""
    util_cols = _read_columns(util_path)
    nat_cols = _read_columns(nat_path)

    util_npi = _first_existing(util_cols, "NPI") or _find_col_contains(util_cols, "npi")
    util_proc = _first_existing(util_cols, "Procedure_Category") or _find_col_contains(util_cols, "procedure_category")
    util_count = _first_existing(util_cols, "Count") or _find_col_contains(util_cols, "count")
    util_percentile = _first_existing(util_cols, "Percentile") or _find_col_contains(util_cols, "percentile")

    missing = [k for k, v in {
        "NPI": util_npi,
        "Procedure_Category": util_proc,
        "Count": util_count,
    }.items() if not v]
    if missing:
        raise KeyError(f"Utilization.csv missing required columns: {missing}")

    nat_npi = _first_existing(nat_cols, "NPI") or _find_col_contains(nat_cols, "npi")
    nat_first = _first_existing(nat_cols, "Frst_Nm", "First_Name") or _find_col_contains(nat_cols, "first")
    nat_last = _first_existing(nat_cols, "Lst_Nm", "Last_Name") or _find_col_contains(nat_cols, "last")
    nat_city = _first_existing(nat_cols, "City") or _find_col_contains(nat_cols, "city")
    nat_state = _first_existing(nat_cols, "State") or _find_col_contains(nat_cols, "state")
    nat_zip = _first_existing(nat_cols, "ZIP", "Zip") or _find_col_contains(nat_cols, "zip")
    nat_spec = _first_existing(nat_cols, "Pri_spec", "Primary_Specialty") or _find_col_contains(nat_cols, "pri_spec")

    missing_nat = [k for k, v in {
        "NPI": nat_npi,
        "First": nat_first,
        "Last": nat_last,
        "City": nat_city,
        "State": nat_state,
        "Pri_spec": nat_spec,
    }.items() if not v]
    if missing_nat:
        raise KeyError(f"DAC_NationalDownloadableFile.csv missing required columns: {missing_nat}")

    util_usecols = [c for c in [util_npi, util_proc, util_count, util_percentile] if c]
    nat_usecols = [c for c in [nat_npi, nat_first, nat_last, nat_city, nat_state, nat_zip, nat_spec] if c]

    util = pd.read_csv(util_path, usecols=util_usecols, low_memory=False)
    nat = pd.read_csv(nat_path, usecols=nat_usecols, low_memory=False)

    # Normalize columns
    util = util.rename(columns={
        util_npi: "npi",
        util_proc: "procedure_category",
        util_count: "count",
        (util_percentile or ""): "percentile",
    })
    if "" in util.columns:
        util = util.drop(columns=[""])

    nat = nat.rename(columns={
        nat_npi: "npi",
        nat_first: "first_name",
        nat_last: "last_name",
        nat_city: "city",
        nat_state: "state",
        nat_zip: "zip",
        nat_spec: "primary_specialty",
    })

    # Keep national to one row per NPI for v1 (pick the first)
    nat = nat.dropna(subset=["npi"]).drop_duplicates(subset=["npi"], keep="first")

    df = util.merge(nat, on="npi", how="left")

    # Dtypes / cleanup
    df["npi"] = df["npi"].astype(str)
    df["state"] = df["state"].astype(str).str.upper().astype("category")
    df["procedure_category"] = df["procedure_category"].astype(str).astype("category")
    df["count"] = pd.to_numeric(df["count"], errors="coerce")
    if "percentile" in df.columns:
        df["percentile"] = pd.to_numeric(df["percentile"], errors="coerce")

    # Column order
    ordered = [
        "npi",
        "first_name",
        "last_name",
        "primary_specialty",
        "city",
        "state",
        "zip",
        "procedure_category",
        "count",
    ]
    if "percentile" in df.columns:
        ordered.append("percentile")

    rest = [c for c in df.columns if c not in ordered]
    return df[ordered + rest]


def load_national_min(
    nat_path: Path,
    states: list[str] | None = None,
    chunksize: int = 200_000,
) -> pd.DataFrame:
    """Load a minimal national dataframe; optionally filter by state during read.

    This is intended to keep the app responsive because DAC_NationalDownloadableFile.csv
    can be very large.
    """
    nat_cols = _read_columns(nat_path)
    nat_npi = _first_existing(nat_cols, "NPI") or _find_col_contains(nat_cols, "npi")
    nat_first = _first_existing(nat_cols, "Frst_Nm", "First_Name") or _find_col_contains(nat_cols, "first")
    nat_last = _first_existing(nat_cols, "Lst_Nm", "Last_Name") or _find_col_contains(nat_cols, "last")
    nat_city = _first_existing(nat_cols, "City") or _find_col_contains(nat_cols, "city")
    nat_state = _first_existing(nat_cols, "State") or _find_col_contains(nat_cols, "state")
    nat_zip = _first_existing(nat_cols, "ZIP", "Zip") or _find_col_contains(nat_cols, "zip")
    nat_spec = _first_existing(nat_cols, "Pri_spec", "Primary_Specialty") or _find_col_contains(nat_cols, "pri_spec")

    missing_nat = [k for k, v in {
        "NPI": nat_npi,
        "First": nat_first,
        "Last": nat_last,
        "City": nat_city,
        "State": nat_state,
        "Pri_spec": nat_spec,
    }.items() if not v]
    if missing_nat:
        raise KeyError(f"DAC_NationalDownloadableFile.csv missing required columns: {missing_nat}")

    usecols = [c for c in [nat_npi, nat_first, nat_last, nat_city, nat_state, nat_zip, nat_spec] if c]

    st: set[str] | None = None
    if states:
        st = {str(s).strip().upper() for s in states if str(s).strip()}

    parts: list[pd.DataFrame] = []
    for chunk in pd.read_csv(nat_path, usecols=usecols, low_memory=False, chunksize=chunksize):
        chunk = chunk.rename(columns={
            nat_npi: "npi",
            nat_first: "first_name",
            nat_last: "last_name",
            nat_city: "city",
            nat_state: "state",
            nat_zip: "zip",
            nat_spec: "primary_specialty",
        })
        chunk = chunk.dropna(subset=["npi"])
        chunk["state"] = chunk["state"].astype(str).str.upper()
        if st is not None:
            chunk = chunk[chunk["state"].isin(st)]
        if not chunk.empty:
            parts.append(chunk)

    if not parts:
        return pd.DataFrame(
            columns=["npi", "first_name", "last_name", "primary_specialty", "city", "state", "zip"]
        )

    nat = pd.concat(parts, ignore_index=True)
    nat["npi"] = nat["npi"].astype(str)
    nat["state"] = nat["state"].astype("category")
    nat = nat.drop_duplicates(subset=["npi"], keep="first")
    return nat


@lru_cache(maxsize=16)
def _cached_national_min(nat_path: str, states_key: tuple[str, ...]) -> pd.DataFrame:
    states = list(states_key) if states_key else None
    return load_national_min(Path(nat_path), states=states)


def get_national_min(nat_path: Path, states: list[str] | None = None) -> pd.DataFrame:
    key = tuple(sorted({str(s).strip().upper() for s in (states or []) if str(s).strip()}))
    return _cached_national_min(str(nat_path), key).copy()


def load_hospitals(general_info_path: Path) -> pd.DataFrame:
    cols = _read_columns(general_info_path)

    # CMS file commonly has these labels
    name_col = _first_existing(cols, "Hospital Name", "Facility Name") or _find_col_contains(cols, "hospital name")
    addr_col = _first_existing(cols, "Address", "Address 1") or _find_col_contains(cols, "address")
    city_col = _first_existing(cols, "City") or _find_col_contains(cols, "city")
    state_col = _first_existing(cols, "State") or _find_col_contains(cols, "state")
    zip_col = _first_existing(cols, "ZIP Code", "Zip Code", "ZIP") or _find_col_contains(cols, "zip")
    ccn_col = (
        _first_existing(cols, "Facility ID", "CCN")
        or _find_col_contains(cols, "facility id")
        or _find_col_contains(cols, "ccn")
    )

    required_missing = [k for k, v in {"hospital_name": name_col, "state": state_col}.items() if not v]
    if required_missing:
        raise KeyError(f"Hospital general info missing required columns: {required_missing}")

    usecols = [c for c in [ccn_col, name_col, addr_col, city_col, state_col, zip_col] if c]
    df = pd.read_csv(general_info_path, usecols=usecols, low_memory=False)

    rename_map = {}
    if ccn_col:
        rename_map[ccn_col] = "ccn"
    rename_map[name_col] = "hospital_name"
    if addr_col:
        rename_map[addr_col] = "address"
    if city_col:
        rename_map[city_col] = "city"
    rename_map[state_col] = "state"
    if zip_col:
        rename_map[zip_col] = "zip"

    df = df.rename(columns=rename_map)

    df["state"] = df["state"].astype(str).str.upper().astype("category")
    if "ccn" in df.columns:
        df["ccn"] = df["ccn"].astype(str)

    ordered = [c for c in ["ccn", "hospital_name", "address", "city", "state", "zip"] if c in df.columns]
    rest = [c for c in df.columns if c not in ordered]
    return df[ordered + rest]


def query_doctors(
    files: DoctorsFiles,
    states: list[str] | None = None,
    procedure_substrings: list[str] | None = None,
    chunksize: int = 200_000,
) -> pd.DataFrame:
    """Filter-first loader for doctors.

    Reads the large national file in a memory-friendly way and only pulls
    utilization rows that match selected states/procedure substrings.
    """
    util_path = files.utilization
    nat_path = files.national

    util_cols = _read_columns(util_path)
    util_npi = _first_existing(util_cols, "NPI") or _find_col_contains(util_cols, "npi")
    util_proc = _first_existing(util_cols, "Procedure_Category") or _find_col_contains(util_cols, "procedure_category")
    util_count = _first_existing(util_cols, "Count") or _find_col_contains(util_cols, "count")
    util_percentile = _first_existing(util_cols, "Percentile") or _find_col_contains(util_cols, "percentile")

    missing = [k for k, v in {"NPI": util_npi, "Procedure_Category": util_proc, "Count": util_count}.items() if not v]
    if missing:
        raise KeyError(f"Utilization.csv missing required columns: {missing}")

    national = get_national_min(nat_path, states=states)
    npi_set: set[str] | None = None
    if states:
        npi_set = set(national["npi"].astype(str))

    subs = [s.strip() for s in (procedure_substrings or []) if str(s).strip()]
    subs_lower = [s.lower() for s in subs]

    usecols = [c for c in [util_npi, util_proc, util_count, util_percentile] if c]

    parts: list[pd.DataFrame] = []
    for chunk in pd.read_csv(util_path, usecols=usecols, low_memory=False, chunksize=chunksize):
        chunk = chunk.rename(columns={
            util_npi: "npi",
            util_proc: "procedure_category",
            util_count: "count",
            (util_percentile or ""): "percentile",
        })
        if "" in chunk.columns:
            chunk = chunk.drop(columns=[""])

        chunk["npi"] = chunk["npi"].astype(str)
        if npi_set is not None:
            chunk = chunk[chunk["npi"].isin(npi_set)]

        if subs_lower:
            cats = chunk["procedure_category"].astype(str)
            mask = pd.Series(False, index=chunk.index)
            for sub in subs_lower:
                mask = mask | cats.str.contains(sub, case=False, na=False)
            chunk = chunk[mask]

        if not chunk.empty:
            parts.append(chunk)

    if not parts:
        # Return empty with canonical columns
        cols = [
            "npi",
            "first_name",
            "last_name",
            "primary_specialty",
            "city",
            "state",
            "zip",
            "procedure_category",
            "count",
            "percentile",
        ]
        return pd.DataFrame(columns=cols)

    util = pd.concat(parts, ignore_index=True)
    util["count"] = pd.to_numeric(util["count"], errors="coerce")
    if "percentile" in util.columns:
        util["percentile"] = pd.to_numeric(util["percentile"], errors="coerce")

    df = util.merge(national, on="npi", how="left")

    if "state" in df.columns:
        df["state"] = df["state"].astype(str).str.upper().astype("category")
    df["procedure_category"] = df["procedure_category"].astype(str).astype("category")

    ordered = [
        "npi",
        "first_name",
        "last_name",
        "primary_specialty",
        "city",
        "state",
        "zip",
        "procedure_category",
        "count",
    ]
    if "percentile" in df.columns:
        ordered.append("percentile")
    rest = [c for c in df.columns if c not in ordered]
    return df[ordered + rest]


@lru_cache(maxsize=32)
def _cached_query_doctors(
    util_path: str,
    nat_path: str,
    states_key: tuple[str, ...],
    procedure_key: tuple[str, ...],
) -> pd.DataFrame:
    states = list(states_key) if states_key else None
    procedures = list(procedure_key) if procedure_key else None
    files = DoctorsFiles(utilization=Path(util_path), national=Path(nat_path), affiliation=None)
    return query_doctors(files, states=states, procedure_substrings=procedures)


def get_doctors_filtered(
    files: DoctorsFiles,
    states: list[str] | None = None,
    procedure_substrings: list[str] | None = None,
) -> pd.DataFrame:
    st_key = tuple(sorted({str(s).strip().upper() for s in (states or []) if str(s).strip()}))
    pr_key = tuple([str(s).strip() for s in (procedure_substrings or []) if str(s).strip()])
    return _cached_query_doctors(str(files.utilization), str(files.national), st_key, pr_key).copy()


@lru_cache(maxsize=4)
def _cached_doctors(util_path: str, nat_path: str) -> pd.DataFrame:
    return load_doctors(Path(util_path), Path(nat_path))


@lru_cache(maxsize=4)
def _cached_hospitals(general_info_path: str) -> pd.DataFrame:
    return load_hospitals(Path(general_info_path))


def get_doctors_df(files: DoctorsFiles) -> pd.DataFrame:
    return _cached_doctors(str(files.utilization), str(files.national)).copy()


def get_hospitals_df(files: HospitalFiles) -> pd.DataFrame:
    return _cached_hospitals(str(files.general_info)).copy()
