from __future__ import annotations

import re
from typing import Literal

import numpy as np
import pandas as pd


def to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def pick_column(
    cols,
    preferred_exact=(),
    contains_any=(),
    regexes=(),
) -> str | None:
    cl = list(cols)
    cl_lower = [c.lower() for c in cl]
    for p in preferred_exact:
        p = p.lower()
        for i, c in enumerate(cl_lower):
            if c == p:
                return cl[i]
    for frag in contains_any:
        frag = frag.lower()
        for i, c in enumerate(cl_lower):
            if frag in c:
                return cl[i]
    for pat in regexes:
        rx = re.compile(pat, re.I)
        for c in cl:
            if rx.search(c):
                return c
    return None


def find_name_columns(cols, who: Literal["referring", "physician"]):
    if who in ("referring", "physician"):
        name_last = pick_column(
            cols,
            preferred_exact=(
                "Rfrg_Prvdr_Last_Name_Org",
                "Rndrng_Prvdr_Last_Org_Name",
                "last_name",
                "nppes_provider_last_org_name",
            ),
            contains_any=("last", "org", "provider", "rfrg", "rndrng"),
            regexes=[r"(rfrg|referr|rndrng|provider).*last|org.*name|last.*name"],
        )
        name_first = pick_column(
            cols,
            preferred_exact=(
                "Rfrg_Prvdr_First_Name",
                "Rndrng_Prvdr_First_Name",
                "first_name",
                "nppes_provider_first_name",
            ),
            contains_any=("first", "provider", "rfrg", "rndrng"),
            regexes=[r"(rfrg|referr|rndrng|provider).*first|first.*name"],
        )
    else:
        name_last, name_first = None, None
    return name_last, name_first


def detect_dimensions(df: pd.DataFrame, who: Literal["referring", "physician"]):
    cols = df.columns
    code_col = pick_column(
        cols,
        preferred_exact=("HCPCS_CD", "HCPCS_Cd", "hcpcs", "hcpcs_code", "hcpcs_cd"),
        contains_any=("hcpcs",),
        regexes=[r"\bhcpcs\b", r"\bhcpcs_?code\b", r"\bhcpcs_?cd\b"],
    )

    if who == "referring":
        npi_col = pick_column(cols, preferred_exact=("Rfrg_NPI", "npi"), contains_any=("rfrg", "referr", "npi"))
        city_col = pick_column(cols, preferred_exact=("Rfrg_Prvdr_City",), contains_any=("city",))
        state_col = pick_column(cols, preferred_exact=("Rfrg_Prvdr_State_Abrvtn",), contains_any=("state", "abrvtn"))
    else:
        npi_col = pick_column(cols, preferred_exact=("Rndrng_NPI", "npi", "NPI"), contains_any=("rndrng", "npi"))
        city_col = pick_column(cols, preferred_exact=("Rndrng_Prvdr_City",), contains_any=("city",))
        state_col = pick_column(cols, preferred_exact=("Rndrng_Prvdr_State_Abrvtn",), contains_any=("state", "abrvtn"))

    name_last, name_first = find_name_columns(cols, who)

    if not code_col or not npi_col:
        raise ValueError("Missing required code/NPI columns.")

    return {
        "code": code_col,
        "npi": npi_col,
        "name_last": name_last,
        "name_first": name_first,
        "city": city_col,
        "state": state_col,
    }


def detect_measures(df: pd.DataFrame):
    cols = df.columns

    services_col = pick_column(
        cols,
        preferred_exact=("Tot_Suplr_Srvcs", "Tot_Srvcs", "Tot_Supplier_Srvcs", "Tot_Suplr_Srvc", "Tot_Suplr_Srvc_Cnt"),
        contains_any=("srvcs", "srvc", "service", "srvc_cnt", "supplier_srv"),
        regexes=[r"(tot|suplr|supplier|srv).*srv"],
    )
    bene_col = pick_column(
        cols,
        preferred_exact=("Tot_Suplr_Benes", "Tot_Benes", "Tot_Supplier_Benes"),
        contains_any=("bene", "benes"),
        regexes=[r"(tot|suplr|supplier).*bene"],
    )

    avg_submitted = pick_column(
        cols,
        preferred_exact=("Avg_Suplr_Sbmtd_Chrg", "Avg_Sbmtd_Chrg", "Avg_Mdcr_Sbmtd_Chrg", "Avg_Suplr_Sbmtd_Chrg"),
        contains_any=("avg", "sbmtd", "submitted", "charge"),
        regexes=[r"avg.*(sbmtd|submit|chrg)"],
    )
    avg_allowed = pick_column(
        cols,
        preferred_exact=("Avg_Suplr_Mdcr_Alowd_Amt", "Avg_Mdcr_Alowd_Amt"),
        contains_any=("avg", "alowd", "allow"),
        regexes=[r"avg.*(alowd|allow)"],
    )
    avg_payment = pick_column(
        cols,
        preferred_exact=("Avg_Suplr_Mdcr_Pymt_Amt", "Avg_Mdcr_Pymt_Amt"),
        contains_any=("avg", "pymt", "payment"),
        regexes=[r"avg.*(pymt|payment)"],
    )

    def _total_col(preferred_exact, fallback_contains):
        col = pick_column(cols, preferred_exact=preferred_exact, contains_any=fallback_contains)
        if col and str(col).lower().startswith("avg"):
            col = None
        return col

    tot_submitted = _total_col(
        ("submitted_chrg_amt", "Tot_Sbmtd_Chrg_Amt", "Total_Submitted_Charges", "Tot_Submitted_Charges"),
        ("submitted_chrg_amt", "submitted charges"),
    )
    tot_allowed = _total_col(
        ("medicare_allowed_amt", "Tot_Mdcr_Alowd_Amt", "Total_Allowed_Amount", "Tot_Allowed_Amt"),
        ("allowed_amt", "allowed amount"),
    )
    tot_payment = _total_col(
        ("medicare_payment_amt", "Tot_Mdcr_Pymt_Amt", "Total_Medicare_Payment", "Tot_Payment_Amt"),
        ("payment_amt", "medicare payment"),
    )

    return {
        "services": services_col,
        "beneficiaries": bene_col,
        "avg_submitted": avg_submitted,
        "avg_allowed": avg_allowed,
        "avg_payment": avg_payment,
        "tot_submitted": tot_submitted,
        "tot_allowed": tot_allowed,
        "tot_payment": tot_payment,
    }


def build_display_name(df: pd.DataFrame, name_last: str | None, name_first: str | None) -> pd.Series:
    if name_last and name_first:
        nm = (df[name_last].astype(str).str.strip() + ", " + df[name_first].astype(str).str.strip()).str.strip(", ")
    elif name_last:
        nm = df[name_last].astype(str).str.strip()
    else:
        nm = pd.Series([""] * len(df), index=df.index)
    return nm


def metric_priority_exists(df: pd.DataFrame) -> str | None:
    for c in [
        "total_services",
        "total_beneficiaries",
        "total_medicare_payment",
        "total_allowed_amount",
        "total_submitted_charges",
    ]:
        if c in df.columns:
            return c
    return None


def per_row_totals(df: pd.DataFrame, meas: dict, services_series: pd.Series | None):
    notes = {
        "sub": pd.Series(pd.NA, index=df.index, dtype="object"),
        "allow": pd.Series(pd.NA, index=df.index, dtype="object"),
        "pay": pd.Series(pd.NA, index=df.index, dtype="object"),
    }

    if meas.get("tot_submitted") and meas["tot_submitted"] in df.columns:
        row_tot_sub = to_num(df[meas["tot_submitted"]])
    elif meas.get("avg_submitted") and services_series is not None:
        row_tot_sub = to_num(df[meas["avg_submitted"]]) * to_num(services_series)
        notes["sub"] = "derived_from_average"
    else:
        row_tot_sub = pd.Series(np.nan, index=df.index, dtype="float64")

    if meas.get("tot_allowed") and meas["tot_allowed"] in df.columns:
        row_tot_allow = to_num(df[meas["tot_allowed"]])
    elif meas.get("avg_allowed") and services_series is not None:
        row_tot_allow = to_num(df[meas["avg_allowed"]]) * to_num(services_series)
        notes["allow"] = "derived_from_average"
    else:
        row_tot_allow = pd.Series(np.nan, index=df.index, dtype="float64")

    if meas.get("tot_payment") and meas["tot_payment"] in df.columns:
        row_tot_pay = to_num(df[meas["tot_payment"]])
    elif meas.get("avg_payment") and services_series is not None:
        row_tot_pay = to_num(df[meas["avg_payment"]]) * to_num(services_series)
        notes["pay"] = "derived_from_average"
    else:
        row_tot_pay = pd.Series(np.nan, index=df.index, dtype="float64")

    return row_tot_sub, row_tot_allow, row_tot_pay, notes
