from __future__ import annotations

import re

import pandas as pd

from .puf_utils import pick_column


def _detect_from_df_or_cols(df_or_cols) -> list[str]:
    if isinstance(df_or_cols, pd.DataFrame):
        return list(df_or_cols.columns)
    return list(df_or_cols)


def detect_npi_col(df_or_cols) -> str:
    cols = _detect_from_df_or_cols(df_or_cols)
    col = pick_column(
        cols,
        preferred_exact=("Rndrng_NPI", "Rfrg_NPI", "NPI", "npi"),
        contains_any=("npi",),
        regexes=[r"\bnpi\b"],
    )
    if not col:
        raise KeyError("Could not detect NPI column")
    return col


def detect_hcpcs_col(df_or_cols) -> str:
    cols = _detect_from_df_or_cols(df_or_cols)
    col = pick_column(
        cols,
        preferred_exact=("HCPCS_Cd", "HCPCS_CD", "hcpcs_cd", "hcpcs"),
        contains_any=("hcpcs",),
        regexes=[r"\bhcpcs\b"],
    )
    if not col:
        raise KeyError("Could not detect HCPCS/CPT code column")
    return col


def detect_state_col(df_or_cols) -> str:
    cols = _detect_from_df_or_cols(df_or_cols)
    col = pick_column(
        cols,
        preferred_exact=("Rndrng_Prvdr_State_Abrvtn", "Rfrg_Prvdr_State_Abrvtn", "State"),
        contains_any=("state", "abrvtn"),
        regexes=[r"state.*abr", r"\bstate\b"],
    )
    if not col:
        raise KeyError("Could not detect state column")
    return col


def detect_services_col(df_or_cols) -> str:
    cols = _detect_from_df_or_cols(df_or_cols)
    col = pick_column(
        cols,
        preferred_exact=("Tot_Srvcs", "Tot_Suplr_Srvcs", "Tot_Supplier_Srvcs"),
        contains_any=("tot_srv", "tot_srvcs", "srvcs"),
        regexes=[r"\btot_.*srv"],
    )
    if not col:
        raise KeyError("Could not detect total services column")
    return col


def detect_total_payment_col(df_or_cols) -> str | None:
    cols = _detect_from_df_or_cols(df_or_cols)
    col = pick_column(
        cols,
        preferred_exact=("Tot_Mdcr_Pymt_Amt", "medicare_payment_amt", "Tot_Payment_Amt"),
        contains_any=("tot", "pymt", "payment"),
        regexes=[r"tot.*(pymt|payment).*amt"],
    )
    if col and str(col).lower().startswith("avg"):
        return None
    return col


def detect_avg_payment_col(df_or_cols) -> str | None:
    cols = _detect_from_df_or_cols(df_or_cols)
    return pick_column(
        cols,
        preferred_exact=("Avg_Mdcr_Pymt_Amt", "Avg_Suplr_Mdcr_Pymt_Amt"),
        contains_any=("avg", "pymt", "payment"),
        regexes=[r"avg.*(pymt|payment).*amt"],
    )


def detect_specialty_col(df_or_cols) -> str | None:
    cols = _detect_from_df_or_cols(df_or_cols)
    return pick_column(
        cols,
        preferred_exact=("Rndrng_Prvdr_Type", "Pri_spec"),
        contains_any=("spclty", "specialty", "type"),
        regexes=[r"prvdr.*type", r"pri_?spec"],
    )


def detect_city_col(df_or_cols) -> str | None:
    cols = _detect_from_df_or_cols(df_or_cols)
    return pick_column(
        cols,
        preferred_exact=("Rndrng_Prvdr_City", "City", "City/Town"),
        contains_any=("city", "town"),
        regexes=[r"city"],
    )


def detect_zip_col(df_or_cols) -> str | None:
    cols = _detect_from_df_or_cols(df_or_cols)
    return pick_column(
        cols,
        preferred_exact=("Rndrng_Prvdr_Zip5", "ZIP Code", "ZIP", "Zip"),
        contains_any=("zip",),
        regexes=[r"zip"],
    )


def detect_last_name_col(df_or_cols) -> str | None:
    cols = _detect_from_df_or_cols(df_or_cols)
    return pick_column(
        cols,
        preferred_exact=("Rndrng_Prvdr_Last_Org_Name", "Provider Last Name"),
        contains_any=("last", "org", "name"),
        regexes=[r"last.*name", r"last_.*org"],
    )


def detect_first_name_col(df_or_cols) -> str | None:
    cols = _detect_from_df_or_cols(df_or_cols)
    return pick_column(
        cols,
        preferred_exact=("Rndrng_Prvdr_First_Name", "Provider First Name"),
        contains_any=("first", "name"),
        regexes=[r"first.*name"],
    )


def detect_hcpcs_desc_col(df_or_cols) -> str | None:
    cols = _detect_from_df_or_cols(df_or_cols)
    return pick_column(
        cols,
        preferred_exact=("HCPCS_Desc", "HCPCS Description"),
        contains_any=("desc",),
        regexes=[r"hcpcs.*desc"],
    )


# Facility affiliation (Doctors_08_2025/Facility_Affiliation.csv)

def detect_affiliation_facility_id_col(df_or_cols) -> str:
    cols = _detect_from_df_or_cols(df_or_cols)
    col = pick_column(
        cols,
        preferred_exact=(
            "Facility Affiliations Certification Number",
            "Facility Type Certification Number",
        ),
        contains_any=("certification", "number"),
        regexes=[r"certification.*number"],
    )
    if not col:
        raise KeyError("Could not detect facility certification number column")
    return col


# Hospital general info (hospitals_08_2025/Hospital_General_Information.csv)

def detect_hospital_id_col(df_or_cols) -> str:
    cols = _detect_from_df_or_cols(df_or_cols)
    col = pick_column(cols, preferred_exact=("Facility ID", "CCN"), contains_any=("facility id", "ccn"))
    if not col:
        raise KeyError("Could not detect hospital Facility ID/CCN column")
    return col


def detect_hospital_name_col(df_or_cols) -> str:
    cols = _detect_from_df_or_cols(df_or_cols)
    col = pick_column(cols, preferred_exact=("Facility Name", "Hospital Name"), contains_any=("facility name", "hospital name"))
    if not col:
        raise KeyError("Could not detect hospital name column")
    return col


def detect_hospital_city_col(df_or_cols) -> str | None:
    cols = _detect_from_df_or_cols(df_or_cols)
    return pick_column(cols, preferred_exact=("City/Town", "City"), contains_any=("city", "town"))


def detect_hospital_state_col(df_or_cols) -> str | None:
    cols = _detect_from_df_or_cols(df_or_cols)
    return pick_column(cols, preferred_exact=("State",), contains_any=("state",))


def normalize_states(states: list[str] | None) -> list[str]:
    if not states:
        return []
    out: list[str] = []
    for s in states:
        s2 = str(s or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", s2):
            continue
        if s2 not in out:
            out.append(s2)
    return out


def normalize_codes(codes: list[str] | None) -> list[str]:
    if not codes:
        return []
    out: list[str] = []
    for c in codes:
        c2 = str(c or "").strip().upper()
        if not c2:
            continue
        if c2 not in out:
            out.append(c2)
    return out
