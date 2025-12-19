# -*- coding: utf-8 -*-
"""
Physicians (CPT) — 77080, OR/WA only + Facility Affiliations
- Filters strictly to CPT code 77080.
- Filters physicians to states OR or WA using the 'state' column (column F in the Excel output).
- Adds affiliations from Doctors_08_2025/Facility_Affiliation.csv and facility names from
  Hospitals_08_2025/Hospital_General_Information.csv.
- Keeps all rows even when beneficiaries are masked (0) and flags them as 'suppressed_<11'.
- Derives $ totals from averages × services when true totals aren't present; notes retained.

Inputs (same folder):
  physHCPCS.csv
  Doctors_08_2025/Facility_Affiliation.csv
  Hospitals_08_2025/Hospital_General_Information.csv

Output:
  CPT_77080_report.xlsx with sheets:
    PhysiciansCPT_AllProviders  (now OR/WA only, plus 'Facility IDs' & 'Hospital Names')
    77080_physicians            (same filter/columns as above)
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

# === CONFIG: file paths (relative to this script) ===
PHYSICIAN_CSV = "./physHCPCS.csv"
AFFIL_CSV     = "./Doctors_08_2025/Facility_Affiliation.csv"
GEN_INFO_CSV  = "./Hospitals_08_2025/Hospital_General_Information.csv"

# === Target CPT code ===
CPT_TARGETS = {"77080": "CPT 77080"}   # replace label with official text if desired

# Columns in our standard output (base set)
STANDARD_COLS = [
    "Code", "Code_Label", "NPI", "Name", "city", "state",
    "total_services", "total_beneficiaries", "services_per_beneficiary",
    "total_submitted_charges", "total_allowed_amount", "total_medicare_payment",
    "rank_within_code",
    "note_total_beneficiaries",
    "note_total_submitted_charges", "note_total_allowed_amount", "note_total_medicare_payment",
]

# New columns we’ll append (to keep structure “mostly unchanged”)
AFFIL_APPEND_COLS = ["Facility IDs", "Hospital Names"]

def _safe_out_dir(pref_path: str) -> str:
    out_dir = os.path.dirname(os.path.abspath(pref_path)) if pref_path else ""
    return out_dir or os.getcwd()

OUT_DIR = _safe_out_dir(PHYSICIAN_CSV if PHYSICIAN_CSV else os.getcwd())
os.makedirs(OUT_DIR, exist_ok=True)

def load_csv(path, dtype_str=True, usecols=None):
    if dtype_str:
        dtype = None if usecols is None else {c: str for c in usecols}
        return pd.read_csv(path, dtype=dtype or str, low_memory=False, usecols=usecols)
    return pd.read_csv(path, low_memory=False, usecols=usecols)

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

def find_name_columns(cols):
    name_last = pick_column(
        cols,
        preferred_exact=("Rndrng_Prvdr_Last_Org_Name","last_name","nppes_provider_last_org_name"),
        contains_any=("last","org","provider","rndrng"),
        regexes=[r"(rndrng|provider).*last|org.*name|last.*name"]
    )
    name_first = pick_column(
        cols,
        preferred_exact=("Rndrng_Prvdr_First_Name","first_name","nppes_provider_first_name"),
        contains_any=("first","provider","rndrng"),
        regexes=[r"(rndrng|provider).*first|first.*name"]
    )
    return name_last, name_first

def detect_dimensions(df):
    if _detect_dimensions is not None:
        return _detect_dimensions(df, "physician")
    cols = df.columns
    code_col = pick_column(cols,
        preferred_exact=("HCPCS_CD","HCPCS_Cd","hcpcs","hcpcs_code","hcpcs_cd"),
        contains_any=("hcpcs",),
        regexes=[r"\bhcpcs\b", r"\bhcpcs_?code\b", r"\bhcpcs_?cd\b"])
    npi_col = pick_column(cols, preferred_exact=("Rndrng_NPI","npi","NPI"), contains_any=("rndrng","npi"))
    city_col  = pick_column(cols, preferred_exact=("Rndrng_Prvdr_City",), contains_any=("city",))
    state_col = pick_column(cols, preferred_exact=("Rndrng_Prvdr_State_Abrvtn",), contains_any=("state","abrvtn"))

    name_last, name_first = find_name_columns(cols)

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
        preferred_exact=("Tot_Srvcs","Tot_Suplr_Srvcs","Tot_Supplier_Srvcs","Tot_Suplr_Srvc","Tot_Suplr_Srvc_Cnt"),
        contains_any=("srvcs","srvc","service","srvc_cnt","supplier_srv"),
        regexes=[r"(tot|suplr|supplier|srv).*srv"])
    bene_col = pick_column(cols,
        preferred_exact=("Tot_Benes","Tot_Suplr_Benes","Tot_Supplier_Benes"),
        contains_any=("bene","benes"),
        regexes=[r"(tot|suplr|supplier).*bene"])

    # Averages
    avg_submitted = pick_column(cols,
        preferred_exact=("Avg_Mdcr_Sbmtd_Chrg","Avg_Sbmtd_Chrg","Avg_Suplr_Sbmtd_Chrg"),
        contains_any=("avg","sbmtd","submitted","charge"),
        regexes=[r"avg.*(sbmtd|submit|chrg)"])
    avg_allowed = pick_column(cols,
        preferred_exact=("Avg_Mdcr_Alowd_Amt","Avg_Suplr_Mdcr_Alowd_Amt"),
        contains_any=("avg","alowd","allow"),
        regexes=[r"avg.*(alowd|allow)"])
    avg_payment = pick_column(cols,
        preferred_exact=("Avg_Mdcr_Pymt_Amt","Avg_Suplr_Mdcr_Pymt_Amt"),
        contains_any=("avg","pymt","payment"),
        regexes=[r"avg.*(pymt|payment)"])

    # True totals (ensure not confusing with Avg)
    def _total_col(preferred_exact, fallback_contains):
        col = pick_column(cols, preferred_exact=preferred_exact, contains_any=fallback_contains)
        if col and str(col).lower().startswith("avg"):
            col = None
        return col

    tot_submitted = _total_col(("Tot_Sbmtd_Chrg_Amt","submitted_chrg_amt","Total_Submitted_Charges","Tot_Submitted_Charges"),
                               ("submitted_chrg_amt","submitted charges",))
    tot_allowed   = _total_col(("Tot_Mdcr_Alowd_Amt","medicare_allowed_amt","Total_Allowed_Amount","Tot_Allowed_Amt"),
                               ("allowed_amt","allowed amount",))
    tot_payment   = _total_col(("Tot_Mdcr_Pymt_Amt","medicare_payment_amt","Total_Medicare_Payment","Tot_Payment_Amt"),
                               ("payment_amt","medicare payment",))

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

def summarize_physicians_cpt(df, targets_map):
    dims = detect_dimensions(df)
    meas = detect_measures(df)

    code_col = dims["code"]; npi_col = dims["npi"]
    wanted = set(k.upper() for k in targets_map.keys())
    mask = df[code_col].astype(str).str.upper().str.strip().isin(wanted)
    df = df.loc[mask].copy()
    if df.empty:
        print(f"[INFO] No rows found for target code(s): {sorted(wanted)}")
        return pd.DataFrame()

    # Standard helper cols
    df["_CODE"] = df[code_col].astype(str).str.upper().str.strip()
    df["_Code_Label"] = df["_CODE"].map(targets_map).fillna("")
    df["_Name"] = build_display_name(df, dims["name_last"], dims["name_first"])
    df["_city"] = df[dims["city"]] if dims["city"] else ""
    df["_state"] = df[dims["state"]] if dims["state"] else ""

    # Per-row numerics
    row_services = to_num(df[meas["services"]]) if meas["services"] else pd.Series(np.nan, index=df.index, dtype="float64")
    row_benes    = to_num(df[meas["beneficiaries"]]) if meas["beneficiaries"] else pd.Series(np.nan, index=df.index, dtype="float64")
    row_tot_sub, row_tot_allow, row_tot_pay, notes = _per_row_totals(df, meas, row_services)

    # Normalize frame
    norm = pd.DataFrame({
        "NPI": df[dims["npi"]],
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

    # Beneficiary suppression note
    g["note_total_beneficiaries"] = pd.NA
    mask_suppressed = (g["total_services"].fillna(0) > 0) & (g["total_beneficiaries"].fillna(0) == 0)
    g.loc[mask_suppressed, "note_total_beneficiaries"] = "suppressed_<11"

    # Intensity + ranking
    denom = g["total_beneficiaries"].replace({0: np.nan})
    g["services_per_beneficiary"] = (g["total_services"] / denom).astype("float64").round(3)
    metric = _metric_priority_exists(g)
    if metric is None:
        g["rank_within_code"] = 1
    else:
        g["rank_within_code"] = g.groupby("Code")[metric].rank(method="first", ascending=False).astype("Int64")
        g = g.sort_values(["Code", metric], ascending=[True, False])

    # Ensure standard order, fill missing
    for col in STANDARD_COLS:
        if col not in g.columns:
            g[col] = pd.NA
    g = g[STANDARD_COLS]
    return g.reset_index(drop=True)

# ------------------ Affiliations merge ------------------

def load_affiliation_maps():
    # NPI -> Facility ID(s)
    affil = load_csv(AFFIL_CSV, usecols=["NPI", "Facility Affiliations Certification Number"])
    affil = affil.dropna(subset=["NPI"])
    affil["NPI"] = affil["NPI"].astype(str).str.strip()
    affil["Facility Affiliations Certification Number"] = affil["Facility Affiliations Certification Number"].astype(str).str.strip()

    # Facility ID -> Facility Name (use general info for a stable name)
    gen = load_csv(GEN_INFO_CSV, usecols=["Facility ID", "Facility Name"])
    gen["Facility ID"] = gen["Facility ID"].astype(str).str.strip()
    gen["Facility Name"] = gen["Facility Name"].astype(str).str.strip()

    # Build maps
    npi_to_facids = (affil.groupby("NPI")["Facility Affiliations Certification Number"]
                          .apply(lambda s: sorted(set(x for x in s if pd.notna(x) and x != "")))
                          .to_dict())
    facid_to_name = dict(zip(gen["Facility ID"], gen["Facility Name"]))

    return npi_to_facids, facid_to_name

def append_affiliations(df):
    """
    Append 'Facility IDs' and 'Hospital Names' to the aggregated physician rows.
    df must contain 'NPI'.
    """
    npi_to_facids, facid_to_name = load_affiliation_maps()

    def facids_for_npi(npi):
        return npi_to_facids.get(str(npi).strip(), [])

    def facnames_from_ids(ids):
        names = [facid_to_name.get(fid, "") for fid in ids if fid]
        names = [n for n in names if n]
        return sorted(set(names))

    facid_series = df["NPI"].map(lambda n: "; ".join(facids_for_npi(n)) if pd.notna(n) else "")
    facname_series = df["NPI"].map(lambda n: "; ".join(facnames_from_ids(facids_for_npi(n))) if pd.notna(n) else "")

    df_out = df.copy()
    for col in AFFIL_APPEND_COLS:
        if col not in df_out.columns:
            df_out[col] = pd.NA
    df_out["Facility IDs"] = facid_series.replace("", pd.NA)
    df_out["Hospital Names"] = facname_series.replace("", pd.NA)
    return df_out

# ------------------ Write & Preview ------------------

def write_excel(phy_df_or_wa):
    xlsx_path = os.path.join(OUT_DIR, "CPT_77080_report.xlsx")
    with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
        if not phy_df_or_wa.empty:
            # PhysiciansCPT_AllProviders (OR/WA + affiliations)
            phy_df_or_wa.to_excel(writer, sheet_name="PhysiciansCPT_AllProviders", index=False)

            # 77080_physicians (same filter)
            sub = phy_df_or_wa[phy_df_or_wa["Code"] == "77080"]
            if not sub.empty:
                sub.to_excel(writer, sheet_name="77080_physicians", index=False)
    print(f"[OK] Wrote Excel workbook: {xlsx_path}")

def preview(df, title):
    if df.empty:
        print(f"\n[INFO] No rows for {title}.")
        return
    metric = _metric_priority_exists(df)
    sub = df[df["Code"] == "77080"]
    if sub.empty:
        print(f"\n[INFO] No rows for 77080 in {title}.")
        return
    show_cols = [c for c in [
        "rank_within_code","NPI","Name","city","state",
        "total_services","total_beneficiaries","services_per_beneficiary",
        "total_medicare_payment","total_allowed_amount","total_submitted_charges",
        "Facility IDs","Hospital Names"
    ] if c in sub.columns]
    if metric:
        sub = sub.sort_values(["rank_within_code", metric], ascending=[True, False])
    print(f"\nTop 20 for 77080 — {title}:")
    print(sub.head(20)[show_cols].to_string(index=False))

# ------------------ Main ------------------

def main():
    print(f"Output directory: {OUT_DIR}")

    # 1) Load CPT PUF and build base table
    if not os.path.exists(PHYSICIAN_CSV):
        print("[INFO] Missing physHCPCS.csv; nothing to do.")
        return
    print(f"\nLoading Physician CPT CSV: {PHYSICIAN_CSV}")
    phy_src = load_csv(PHYSICIAN_CSV)
    phy_df = summarize_physicians_cpt(phy_src, targets_map=CPT_TARGETS)

    # 2) Filter by state using the 'state' column (Excel column F)
    states_ok = {"OR", "WA"}
    phy_df_or_wa = phy_df[phy_df["state"].astype(str).str.strip().str.upper().isin(states_ok)].copy()

    # 3) Append facility affiliations (IDs + Names) using the other program's data sources
    phy_df_or_wa = append_affiliations(phy_df_or_wa)

    # Keep column order: standard cols first, then appended affiliation cols
    ordered_cols = [c for c in STANDARD_COLS if c in phy_df_or_wa.columns] + [c for c in AFFIL_APPEND_COLS if c in phy_df_or_wa.columns]
    phy_df_or_wa = phy_df_or_wa[ordered_cols]

    # 4) Write Excel (same sheet names), OR/WA only
    write_excel(phy_df_or_wa)

    # 5) Console preview
    preview(phy_df_or_wa, "Physicians (CPT) — OR/WA only")

if __name__ == "__main__":
    main()
