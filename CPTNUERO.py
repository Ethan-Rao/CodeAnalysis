# -*- coding: utf-8 -*-
"""
Providers-only (NPI + Names): Referring physicians (DMEPOS) and Physicians (CPT)
- Keeps all rows even when beneficiaries are masked (0) and flags them as 'suppressed_<11'.
- Derives $ totals from averages × services when true totals aren't present; notes retained.

Inputs (same folder):
  refHCPCS.csv   -> DMEPOS by Referring Provider & Service (HCPCS codes, referrals)
  physHCPCS.csv  -> Physician & Other Supplier PUF (CPT codes, billing physicians)

Codes & labels (UPDATED for your request):
  HCPCS:  L8679, A4593
  CPT:    61889

Output:
  Excel workbook: HCPCS_CPT_report.xlsx with sheets:
    Referring_AllProviders, L8679_referring, A4593_referring,
    PhysiciansCPT_AllProviders, 61889_physicians
"""

import os
import re
import numpy as np
import pandas as pd
pd.options.display.width = 220

# Prefer shared core logic from cms_app (keeps this script as a thin wrapper)
try:
    from cms_app.puf_utils import (
        build_display_name as _build_display_name,
        detect_dimensions as _detect_dimensions,
        detect_measures as _detect_measures,
        metric_priority_exists as _metric_priority_exists,
        per_row_totals as _per_row_totals,
        pick_column as _pick_column,
        to_num as _to_num,
    )
except Exception:  # pragma: no cover
    _build_display_name = None
    _detect_dimensions = None
    _detect_measures = None
    _metric_priority_exists = None
    _per_row_totals = None
    _pick_column = None
    _to_num = None

# === CONFIG: file paths ===
REFERRING_CSV = "./refHCPCS.csv"
PHYSICIAN_CSV = "./physHCPCS.csv"

# === Target code sets & labels (UPDATED) ===
HCPCS_TARGETS = {
    "L8679": "Target HCPCS L8679",
    "A4593": "Target HCPCS A4593",
}
CPT_TARGETS = {
    "61889": "Target CPT 61889",
}

STANDARD_COLS = [
    "Code", "Code_Label", "NPI", "Name", "city", "state",
    "total_services", "total_beneficiaries", "services_per_beneficiary",
    "total_submitted_charges", "total_allowed_amount", "total_medicare_payment",
    "rank_within_code",
    "note_total_beneficiaries",
    "note_total_submitted_charges", "note_total_allowed_amount", "note_total_medicare_payment",
]

def _safe_out_dir(pref_path: str) -> str:
    out_dir = os.path.dirname(os.path.abspath(pref_path)) if pref_path else ""
    return out_dir or os.getcwd()

OUT_DIR = _safe_out_dir(REFERRING_CSV if REFERRING_CSV else os.getcwd())
os.makedirs(OUT_DIR, exist_ok=True)

def load_csv(path):
    return pd.read_csv(path, dtype=str, low_memory=False)

def to_num(s):
    if _to_num is not None:
        return _to_num(s)
    return pd.to_numeric(s, errors="coerce")

def pick_column(cols, preferred_exact=(), contains_any=(), regexes=()):
    if _pick_column is not None:
        return _pick_column(cols, preferred_exact=preferred_exact, contains_any=contains_any, regexes=regexes)
    cl = list(cols); cl_lower = [c.lower() for c in cl]
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

def find_name_columns(cols, who):
    if who in ("referring", "physician"):
        name_last = pick_column(
            cols,
            preferred_exact=("Rfrg_Prvdr_Last_Name_Org","Rndrng_Prvdr_Last_Org_Name","last_name","nppes_provider_last_org_name"),
            contains_any=("last","org","provider","rfrg","rndrng"),
            regexes=[r"(rfrg|referr|rndrng|provider).*last|org.*name|last.*name"]
        )
        name_first = pick_column(
            cols,
            preferred_exact=("Rfrg_Prvdr_First_Name","Rndrng_Prvdr_First_Name","first_name","nppes_provider_first_name"),
            contains_any=("first","provider","rfrg","rndrng"),
            regexes=[r"(rfrg|referr|rndrng|provider).*first|first.*name"]
        )
    else:
        name_last, name_first = None, None
    return name_last, name_first

def detect_dimensions(df, who):
    if _detect_dimensions is not None:
        return _detect_dimensions(df, who)
    cols = df.columns
    code_col = pick_column(cols,
        preferred_exact=("HCPCS_CD","HCPCS_Cd","hcpcs","hcpcs_code","hcpcs_cd"),
        contains_any=("hcpcs",),
        regexes=[r"\bhcpcs\b", r"\bhcpcs_?code\b", r"\bhcpcs_?cd\b"])

    if who == "referring":
        npi_col = pick_column(cols,
            preferred_exact=("Rfrg_NPI","npi"),
            contains_any=("rfrg","referr","npi"))
        city_col  = pick_column(cols, preferred_exact=("Rfrg_Prvdr_City",), contains_any=("city",))
        state_col = pick_column(cols, preferred_exact=("Rfrg_Prvdr_State_Abrvtn",), contains_any=("state","abrvtn"))
        label = "DMEPOS Referring"
    else:  # physician
        npi_col = pick_column(cols, preferred_exact=("Rndrng_NPI","npi","NPI"), contains_any=("rndrng","npi"))
        city_col  = pick_column(cols, preferred_exact=("Rndrng_Prvdr_City",), contains_any=("city",))
        state_col = pick_column(cols, preferred_exact=("Rndrng_Prvdr_State_Abrvtn",), contains_any=("state","abrvtn"))
        label = "Physician CPT"

    name_last, name_first = find_name_columns(cols, who)

    print(f"\n[Detected Columns] {label}")
    print(f"  total columns: {len(cols)}")
    print("  first 60 columns:", list(cols)[:60])
    print(f"  code        : {code_col}")
    print(f"  npi         : {npi_col}")
    print(f"  name_last   : {name_last}")
    print(f"  name_first  : {name_first}")
    print(f"  city        : {city_col}")
    print(f"  state       : {state_col}")

    if not code_col or not npi_col:
        raise ValueError("Missing required code/NPI columns.")

    return {
        "code": code_col, "npi": npi_col,
        "name_last": name_last, "name_first": name_first,
        "city": city_col, "state": state_col
    }

def detect_measures(df):
    if _detect_measures is not None:
        return _detect_measures(df)
    cols = df.columns
    # Counts
    services_col = pick_column(cols,
        preferred_exact=("Tot_Suplr_Srvcs","Tot_Srvcs","Tot_Supplier_Srvcs","Tot_Suplr_Srvc","Tot_Suplr_Srvc_Cnt"),
        contains_any=("srvcs","srvc","service","srvc_cnt","supplier_srv"),
        regexes=[r"(tot|suplr|supplier|srv).*srv"])
    bene_col = pick_column(cols,
        preferred_exact=("Tot_Suplr_Benes","Tot_Benes","Tot_Supplier_Benes"),
        contains_any=("bene","benes"),
        regexes=[r"(tot|suplr|supplier).*bene"])

    # Averages (common in both)
    avg_submitted = pick_column(cols,
        preferred_exact=("Avg_Suplr_Sbmtd_Chrg","Avg_Sbmtd_Chrg"),
        contains_any=("avg","sbmtd","submitted","charge"),
        regexes=[r"avg.*(sbmtd|submit|chrg)"])
    avg_allowed = pick_column(cols,
        preferred_exact=("Avg_Suplr_Mdcr_Alowd_Amt","Avg_Mdcr_Alowd_Amt"),
        contains_any=("avg","alowd","allow"),
        regexes=[r"avg.*(alowd|allow)"])
    avg_payment = pick_column(cols,
        preferred_exact=("Avg_Suplr_Mdcr_Pymt_Amt","Avg_Mdcr_Pymt_Amt"),
        contains_any=("avg","pymt","payment"),
        regexes=[r"avg.*(pymt|payment)"])

    # True totals (rare). NEVER let an Avg_* be mistaken for a total.
    def _total_col(preferred_exact, fallback_contains):
        col = pick_column(cols, preferred_exact=preferred_exact, contains_any=fallback_contains)
        if col and str(col).lower().startswith("avg"):
            col = None
        return col

    tot_submitted = _total_col(("submitted_chrg_amt","Tot_Sbmtd_Chrg_Amt","Total_Submitted_Charges","Tot_Submitted_Charges"),
                               ("submitted_chrg_amt","submitted charges",))
    tot_allowed   = _total_col(("medicare_allowed_amt","Tot_Mdcr_Alowd_Amt","Total_Allowed_Amount","Tot_Allowed_Amt"),
                               ("allowed_amt","allowed amount",))
    tot_payment   = _total_col(("medicare_payment_amt","Tot_Mdcr_Pymt_Amt","Total_Medicare_Payment","Tot_Payment_Amt"),
                               ("payment_amt","medicare payment",))

    print(f"  measure.services : {services_col}")
    print(f"  measure.benes    : {bene_col}")
    print(f"  measure.avg_sub  : {avg_submitted}")
    print(f"  measure.avg_allow: {avg_allowed}")
    print(f"  measure.avg_pay  : {avg_payment}")
    print(f"  measure.tot_sub  : {tot_submitted}")
    print(f"  measure.tot_allow: {tot_allowed}")
    print(f"  measure.tot_pay  : {tot_payment}")

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

def build_display_name(df, name_last, name_first):
    if _build_display_name is not None:
        return _build_display_name(df, name_last, name_first)
    if name_last and name_first:
        nm = (df[name_last].astype(str).str.strip() + ", " + df[name_first].astype(str).str.strip()).str.strip(", ")
    elif name_last:
        nm = df[name_last].astype(str).str.strip()
    else:
        nm = pd.Series([""] * len(df), index=df.index)
    return nm

def _metric_priority_exists(df):
    if _metric_priority_exists is not None:
        return _metric_priority_exists(df)
    for c in ["total_services","total_beneficiaries","total_medicare_payment","total_allowed_amount","total_submitted_charges"]:
        if c in df.columns:
            return c
    return None

def _per_row_totals(df, meas, services_series):
    """
    Derive per-row totals (submitted/allowed/payment), or use provided totals.
    Returns: (row_tot_sub, row_tot_allow, row_tot_pay, notes)
    """
    if _per_row_totals is not None:
        return _per_row_totals(df, meas, services_series)
    notes = {"sub": pd.Series(pd.NA, index=df.index, dtype="object"),
             "allow": pd.Series(pd.NA, index=df.index, dtype="object"),
             "pay": pd.Series(pd.NA, index=df.index, dtype="object")}

    # Submitted
    if meas["tot_submitted"] and meas["tot_submitted"] in df.columns:
        row_tot_sub = to_num(df[meas["tot_submitted"]])
    elif meas["avg_submitted"] and services_series is not None:
        row_tot_sub = to_num(df[meas["avg_submitted"]]) * to_num(services_series)
        notes["sub"] = "derived_from_average"
    else:
        row_tot_sub = pd.Series(np.nan, index=df.index, dtype="float64")

    # Allowed
    if meas["tot_allowed"] and meas["tot_allowed"] in df.columns:
        row_tot_allow = to_num(df[meas["tot_allowed"]])
    elif meas["avg_allowed"] and services_series is not None:
        row_tot_allow = to_num(df[meas["avg_allowed"]]) * to_num(services_series)
        notes["allow"] = "derived_from_average"
    else:
        row_tot_allow = pd.Series(np.nan, index=df.index, dtype="float64")

    # Payment
    if meas["tot_payment"] and meas["tot_payment"] in df.columns:
        row_tot_pay = to_num(df[meas["tot_payment"]])
    elif meas["avg_payment"] and services_series is not None:
        row_tot_pay = to_num(df[meas["avg_payment"]]) * to_num(services_series)
        notes["pay"] = "derived_from_average"
    else:
        row_tot_pay = pd.Series(np.nan, index=df.index, dtype="float64")

    return row_tot_sub, row_tot_allow, row_tot_pay, notes

def summarize_providers(df, who, targets_map, dataset_label):
    dims = detect_dimensions(df, who=who)
    meas = detect_measures(df)

    code_col = dims["code"]; npi_col = dims["npi"]
    wanted = set(k.upper() for k in targets_map.keys())
    mask = df[code_col].astype(str).str.upper().str.strip().isin(wanted)
    df = df.loc[mask].copy()
    if df.empty:
        print(f"[INFO] No rows found for target codes in {dataset_label}: {sorted(wanted)}")
        return pd.DataFrame()

    # Standard helper cols for display
    df["_CODE"] = df[code_col].astype(str).str.upper().str.strip()
    df["_Code_Label"] = df["_CODE"].map(targets_map).fillna("")
    df["_Name"] = build_display_name(df, dims["name_last"], dims["name_first"])
    df["_city"] = df[dims["city"]] if dims["city"] else ""
    df["_state"] = df[dims["state"]] if dims["state"] else ""

    # Per-row numeric bases
    row_services = to_num(df[meas["services"]]) if meas["services"] else pd.Series(np.nan, index=df.index, dtype="float64")
    row_benes    = to_num(df[meas["beneficiaries"]]) if meas["beneficiaries"] else pd.Series(np.nan, index=df.index, dtype="float64")

    # Derive row-level totals (or use provided totals). This prevents duplicates when aggregating by NPI+Code.
    row_tot_sub, row_tot_allow, row_tot_pay, notes = _per_row_totals(df, meas, row_services)

    # Normalize frame
    norm = pd.DataFrame({
        "NPI": df[npi_col],
        "Code": df["_CODE"],
        "Code_Label": df["_Code_Label"],
        "Name": df["_Name"],
        "city": df["_city"],
        "state": df["_state"],
        "row_services": row_services,
        "row_benes": row_benes,
        "row_tot_sub": row_tot_sub,
        "row_tot_allow": row_tot_allow,
        "row_tot_pay": row_tot_pay,
        "note_sub": notes["sub"],
        "note_allow": notes["allow"],
        "note_pay": notes["pay"],
    })

    # Aggregate strictly by (NPI, Code)
    g = norm.groupby(["NPI", "Code", "Code_Label"], dropna=False).agg({
        "row_services": "sum",
        "row_benes": "sum",
        "row_tot_sub": "sum",
        "row_tot_allow": "sum",
        "row_tot_pay": "sum",
        "Name": "first",
        "city": "first",
        "state": "first",
        # If any line for this NPI+Code was derived, mark derived
        "note_sub": lambda s: "derived_from_average" if (s == "derived_from_average").any() else pd.NA,
        "note_allow": lambda s: "derived_from_average" if (s == "derived_from_average").any() else pd.NA,
        "note_pay": lambda s: "derived_from_average" if (s == "derived_from_average").any() else pd.NA,
    }).reset_index()

    # Rename to standard
    g = g.rename(columns={
        "row_services": "total_services",
        "row_benes": "total_beneficiaries",
        "row_tot_sub": "total_submitted_charges",
        "row_tot_allow": "total_allowed_amount",
        "row_tot_pay": "total_medicare_payment",
        "note_sub": "note_total_submitted_charges",
        "note_allow": "note_total_allowed_amount",
        "note_pay": "note_total_medicare_payment",
    })

    # Beneficiary suppression note: if total_services>0 and total_beneficiaries==0
    g["note_total_beneficiaries"] = pd.NA
    mask_suppressed = (g["total_services"].fillna(0) > 0) & (g["total_beneficiaries"].fillna(0) == 0)
    g.loc[mask_suppressed, "note_total_beneficiaries"] = "suppressed_<11"

    # Intensity
    denom = g["total_beneficiaries"].replace({0: np.nan})
    g["services_per_beneficiary"] = (g["total_services"] / denom).astype("float64").round(3)

    # Rank within code by best available metric
    metric = _metric_priority_exists(g)
    if metric is None:
        g["rank_within_code"] = 1
    else:
        g["rank_within_code"] = g.groupby("Code")[metric].rank(method="first", ascending=False).astype("Int64")
        g = g.sort_values(["Code", metric], ascending=[True, False])

    # Ensure standard columns
    for col in STANDARD_COLS:
        if col not in g.columns:
            g[col] = pd.NA
    g = g[STANDARD_COLS]

    # Console summary
    print(f"  [Derived $ totals in {dataset_label}] submitted={ (g['note_total_submitted_charges']=='derived_from_average').sum() }, "
          f"allowed={ (g['note_total_allowed_amount']=='derived_from_average').sum() }, "
          f"payment={ (g['note_total_medicare_payment']=='derived_from_average').sum() }")
    print(f"  [Suppressed benes flagged in {dataset_label}]: {(g['note_total_beneficiaries']=='suppressed_<11').sum()} rows")
    dup_keys = g.duplicated(subset=["NPI","Code"], keep=False).sum()
    if dup_keys:
        print(f"  [WARN] {dup_keys} duplicate key rows after aggregation in {dataset_label} (NPI+Code).")
    else:
        print(f"  [OK] Unique rows by (NPI, Code) in {dataset_label}.")

    return g.reset_index(drop=True)

def write_excel(ref_df, phy_df):
    xlsx_path = os.path.join(OUT_DIR, "HCPCS_CPT_report.xlsx")
    with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
        if not ref_df.empty:
            ref_df.to_excel(writer, sheet_name="Referring_AllProviders", index=False)
            for code in HCPCS_TARGETS:
                sub = ref_df[ref_df["Code"] == code]
                if not sub.empty:
                    sub.to_excel(writer, sheet_name=f"{code}_referring", index=False)
        if not phy_df.empty:
            phy_df.to_excel(writer, sheet_name="PhysiciansCPT_AllProviders", index=False)
            for code in CPT_TARGETS:
                sub = phy_df[phy_df["Code"] == code]
                if not sub.empty:
                    sub.to_excel(writer, sheet_name=f"{code}_physicians", index=False)
    print(f"[OK] Wrote Excel workbook: {xlsx_path}")

def preview(df, title, targets_map):
    if df.empty:
        print(f"\n[INFO] No rows for {title}.")
        return
    metric = _metric_priority_exists(df)
    for code, label in targets_map.items():
        sub = df[df["Code"] == code]
        if sub.empty:
            print(f"\n[INFO] No rows for {code} ({label}) in {title}.")
            continue
        show_cols = [c for c in [
            "rank_within_code","NPI","Name","city","state",
            "total_services","total_beneficiaries","services_per_beneficiary",
            "total_medicare_payment","total_allowed_amount","total_submitted_charges",
            "note_total_beneficiaries",
            "note_total_medicare_payment","note_total_allowed_amount","note_total_submitted_charges"
        ] if c in sub.columns]
        if metric:
            sub = sub.sort_values(["rank_within_code", metric], ascending=[True, False])
        print(f"\nTop 15 for {code} ({label}) — {title}:")
        print(sub.head(15)[show_cols].to_string(index=False))

def main():
    print(f"Output directory: {OUT_DIR}")

    # 1) Referring (DMEPOS HCPCS codes; providers who referred/ordered)
    if os.path.exists(REFERRING_CSV):
        print(f"\nLoading DMEPOS Referring CSV: {REFERRING_CSV}")
        ref_src = load_csv(REFERRING_CSV)
        ref_df = summarize_providers(ref_src, who="referring", targets_map=HCPCS_TARGETS, dataset_label="DMEPOS Referring")
    else:
        print("[INFO] Missing refHCPCS.csv; skipping referring.")
        ref_df = pd.DataFrame()

    # 2) Physicians (CPT billing providers)
    if os.path.exists(PHYSICIAN_CSV):
        print(f"\nLoading Physician CPT CSV: {PHYSICIAN_CSV}")
        phy_src = load_csv(PHYSICIAN_CSV)
        phy_df = summarize_providers(phy_src, who="physician", targets_map=CPT_TARGETS, dataset_label="Physicians CPT")
    else:
        print("[INFO] Missing physHCPCS.csv; skipping CPT.")
        phy_df = pd.DataFrame()

    write_excel(ref_df, phy_df)

    # Console previews (top 15 per code)
    preview(ref_df, "Referring Physicians (DMEPOS)", HCPCS_TARGETS)
    preview(phy_df, "Physicians (CPT)", CPT_TARGETS)

if __name__ == "__main__":
    main()
