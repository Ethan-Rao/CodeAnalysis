from __future__ import annotations

import io
import re
from urllib.parse import urlencode

import pandas as pd
from flask import Blueprint, Response, current_app, jsonify, redirect, render_template, request, url_for

from . import data_loading
from .code_classification import CodeClassificationManager
from .cms_query import DOCTORS_BY_CODE_UI_COLUMNS, doctors_by_codes
from .filters import filter_doctors, filter_hospitals
from .code_analytics import get_code_market_stats, get_top_codes_by_volume
from .code_validation import validate_codes_before_search
from .data_validation import check_data_files, get_data_health_summary
from .hcpcs_lookup import get_hcpcs_lookup
from .hospital_analytics import get_hospital_physicians, hospitals_by_codes
from .logger import logger

cms_bp = Blueprint("cms", __name__, template_folder="templates", static_folder="static")


@cms_bp.route("/health", methods=["GET"])
def health_check():
    """Data health check endpoint."""
    status = check_data_files()
    health_summary = get_data_health_summary()
    
    all_ok = all(info["exists"] and info["readable"] for info in status.values())
    
    return render_template(
        "health_check.html",
        status=status,
        health_summary=health_summary,
        all_ok=all_ok,
    )


def _parse_csvish_list(value: str | None) -> list[str]:
    if not value:
        return []
    # supports "CA, OR" or "CA OR" etc.
    parts = [p.strip() for p in value.replace(";", ",").replace("\n", ",").split(",")]
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        # If user pasted space-separated states ("CA OR")
        if " " in p:
            out.extend([x.strip() for x in p.split() if x.strip()])
        else:
            out.append(p)
    return [x for x in out if x]


@cms_bp.route("/explorer", methods=["GET", "POST"])
def explorer():
    # Default to Hospitals - primary use case
    dataset = request.values.get("dataset", "Hospitals")
    states_raw = request.values.get("states", "")
    codes_raw = request.values.get("codes", "")
    min_services_raw = request.values.get("min_services", "")
    procedure_raw = request.values.get("procedure", "")
    device_category = request.values.get("device_category", "")

    submitted = request.method == "POST"

    rows = []
    columns: list[str] = []
    column_labels: dict[str, str] = {}
    summary: str | None = None
    export_url: str | None = None
    error: str | None = None
    notice: str | None = None
    search_mode = "doctors"  # "doctors" or "hospitals"
    code_descriptions: dict[str, dict[str, str]] = {}
    searched_codes: list[str] = []

    # Load device categories for dropdown
    classification_manager = CodeClassificationManager()
    device_categories = classification_manager.get_all_categories()

    # If device category is selected (via GET), load its codes
    if device_category and not codes_raw and request.method == "GET":
        category = classification_manager.get_category(device_category)
        if category:
            codes_raw = ", ".join(category.codes)
            notice = f"Loaded {len(category.codes)} codes from category '{device_category}'. Click 'Run' to search."

    if submitted:
        try:
            logger.info(f"Search request: dataset={dataset}, codes={codes_raw[:100]}, states={states_raw}, min_services={min_services_raw}, device_category={device_category}")
            
            states = _parse_csvish_list(states_raw)
            procedure_substrings = _parse_csvish_list(procedure_raw)

            codes = _parse_csvish_list(codes_raw)
            min_services = None
            if str(min_services_raw).strip():
                try:
                    min_services = int(str(min_services_raw).strip())
                except Exception:
                    min_services = None

            if dataset == "Hospitals":
                search_mode = "hospitals"
                if not codes:
                    columns = []
                    rows = []
                    summary = None
                    export_url = None
                    notice = "Please enter at least one CPT or HCPCS code to search hospitals by procedure volume."
                    return render_template(
                        "cms_explorer.html",
                        dataset=dataset,
                        states=states_raw,
                        codes=codes_raw,
                        min_services=min_services_raw,
                        procedure=procedure_raw,
                        device_category=device_category,
                        device_categories=device_categories,
                        submitted=submitted,
                        columns=columns,
                        column_labels=column_labels,
                        rows=rows,
                        summary=summary,
                        export_url=export_url,
                        error=error,
                        notice=notice,
                        is_doctors_by_code=False,
                        search_mode=search_mode,
                    )
                
                # Validate code format
                invalid_codes = [c for c in codes if not re.match(r'^[A-Z0-9]+$', c.upper())]
                if invalid_codes:
                    error = f"Invalid code format(s): {', '.join(invalid_codes)}. Codes should contain only letters and numbers."
                    return render_template(
                        "cms_explorer.html",
                        dataset=dataset,
                        states=states_raw,
                        codes=codes_raw,
                        min_services=min_services_raw,
                        procedure=procedure_raw,
                        device_category=device_category,
                        device_categories=device_categories,
                        submitted=submitted,
                        columns=[],
                        column_labels={},
                        rows=[],
                        summary=None,
                        export_url=None,
                        error=error,
                        notice=None,
                        is_doctors_by_code=False,
                        search_mode=search_mode,
                    )
                
                # Quick validation: check if codes exist in dataset
                valid_codes, missing_codes = validate_codes_before_search(codes)
                if missing_codes:
                    notice = f"Warning: The following codes were not found in the dataset: {', '.join(missing_codes)}. They may not exist in this year's data or may be very rare."
                    logger.warning(f"Codes not found in dataset: {missing_codes}")
                
                if not valid_codes:
                    error = f"None of the provided codes ({', '.join(codes)}) were found in the dataset. Please verify the codes are correct and exist in the current year's Medicare data."
                    return render_template(
                        "cms_explorer.html",
                        dataset=dataset,
                        states=states_raw,
                        codes=codes_raw,
                        min_services=min_services_raw,
                        procedure=procedure_raw,
                        device_category=device_category,
                        device_categories=device_categories,
                        submitted=submitted,
                        columns=[],
                        column_labels={},
                        rows=[],
                        summary=None,
                        export_url=None,
                        error=error,
                        notice=None,
                        is_doctors_by_code=False,
                        search_mode=search_mode,
                    )
                
                # Use hospital analytics with only valid codes
                filtered = hospitals_by_codes(codes=valid_codes, states=states, min_procedures=min_services, max_rows=250)
                
                # Summary
                n_hospitals = len(filtered)
                n_states = int(filtered["hospital_state"].dropna().astype(str).str.upper().nunique()) if n_hospitals else 0
                total_procedures = int(pd.to_numeric(filtered["total_procedures"], errors="coerce").fillna(0).sum()) if n_hospitals else 0
                total_payments = int(pd.to_numeric(filtered["total_payments"], errors="coerce").fillna(0).sum()) if n_hospitals else 0
                
                summary = (
                    f"Top {min(250, n_hospitals):,} hospitals by volume. Showing {n_hospitals:,} hospitals across {n_states} states for codes: {', '.join([c.upper() for c in codes])}. "
                    f"Total procedures: {total_procedures:,}. Total payments: ${total_payments:,.0f}."
                )
                if min_services is not None:
                    summary += f" Minimum procedures per hospital: {min_services:,}."
                if device_category:
                    summary += f" Category: {device_category}."
                
                preview = filtered.head(current_app.config["MAX_TABLE_ROWS"])
                column_labels = {
                    "facility_id": "Facility ID",
                    "hospital_name": "Hospital Name",
                    "hospital_city": "City",
                    "hospital_state": "State",
                    "total_procedures": "Total Procedures",
                    "total_payments": "Total Payments",
                    "num_physicians": "Number of Physicians",
                    "avg_procedures_per_physician": "Avg Procedures/Physician",
                    "code_breakdown": "Code Breakdown",
                }
                
                q = {
                    "dataset": dataset,
                    "codes": codes_raw,
                    "states": states_raw,
                    "min_services": str(min_services or ""),
                    "device_category": device_category or "",
                }
                export_url = "/cms/export?" + urlencode(q)
                
                columns = list(preview.columns)
                rows = preview.to_dict(orient="records")
                
                # Enrich with HCPCS code descriptions
                hcpcs_lookup = get_hcpcs_lookup()
                for code in codes:
                    code_info = hcpcs_lookup.get_code(code)
                    if code_info:
                        code_descriptions[code.upper()] = {
                            "short": code_info.short_description or (code_info.long_description[:50] if code_info.long_description else ""),
                            "long": code_info.long_description or "",
                        }
                searched_codes = codes
            else:  # DoctorsByCode
                search_mode = "doctors"
                if not codes:
                    columns = []
                    rows = []
                    summary = None
                    export_url = None
                    notice = "Please enter at least one CPT or HCPCS code, or select a device category."
                    return render_template(
                        "cms_explorer.html",
                        dataset=dataset,
                        states=states_raw,
                        codes=codes_raw,
                        min_services=min_services_raw,
                        procedure=procedure_raw,
                        device_category=device_category,
                        device_categories=device_categories,
                        submitted=submitted,
                        columns=columns,
                        column_labels=column_labels,
                        rows=rows,
                        summary=summary,
                        export_url=export_url,
                        error=error,
                        notice=notice,
                        is_doctors_by_code=True,
                        search_mode=search_mode,
                    )

                # Validate code format
                invalid_codes = [c for c in codes if not re.match(r'^[A-Z0-9]+$', c.upper())]
                if invalid_codes:
                    error = f"Invalid code format(s): {', '.join(invalid_codes)}. Codes should contain only letters and numbers."
                    return render_template(
                        "cms_explorer.html",
                        dataset=dataset,
                        states=states_raw,
                        codes=codes_raw,
                        min_services=min_services_raw,
                        procedure=procedure_raw,
                        device_category=device_category,
                        device_categories=device_categories,
                        submitted=submitted,
                        columns=[],
                        column_labels={},
                        rows=[],
                        summary=None,
                        export_url=None,
                        error=error,
                        notice=None,
                        is_doctors_by_code=True,
                        search_mode=search_mode,
                    )

                # Quick validation: check if codes exist in dataset
                valid_codes, missing_codes = validate_codes_before_search(codes)
                if missing_codes:
                    notice = f"Warning: The following codes were not found in the dataset: {', '.join(missing_codes)}. They may not exist in this year's data or may be very rare."
                    logger.warning(f"Codes not found in dataset: {missing_codes}")
                
                if not valid_codes:
                    error = f"None of the provided codes ({', '.join(codes)}) were found in the dataset. Please verify the codes are correct and exist in the current year's Medicare data."
                    return render_template(
                        "cms_explorer.html",
                        dataset=dataset,
                        states=states_raw,
                        codes=codes_raw,
                        min_services=min_services_raw,
                        procedure=procedure_raw,
                        device_category=device_category,
                        device_categories=device_categories,
                        submitted=submitted,
                        columns=[],
                        column_labels={},
                        rows=[],
                        summary=None,
                        export_url=None,
                        error=error,
                        notice=None,
                        is_doctors_by_code=True,
                        search_mode=search_mode,
                    )

                df = doctors_by_codes(codes=valid_codes, states=states, min_services=min_services, max_rows=250)
                filtered = df

                # Summary
                n_docs = len(filtered)
                n_states = int(filtered["state"].dropna().astype(str).str.upper().nunique()) if n_docs else 0
                total_services = int(pd.to_numeric(filtered["total_services_selected_codes"], errors="coerce").fillna(0).sum()) if n_docs else 0
                summary = (
                    f"Top {min(250, n_docs):,} doctors by volume. Showing {n_docs:,} doctors across {n_states} states for codes: {', '.join([c.upper() for c in codes])}. "
                    f"Total services for these codes: {total_services:,}."
                )
                if min_services is not None:
                    summary += f" Minimum procedures per doctor: {min_services:,}."
                if device_category:
                    summary += f" Category: {device_category}."

                preview = filtered.head(current_app.config["MAX_TABLE_ROWS"])
                column_labels = {k: v for k, v in DOCTORS_BY_CODE_UI_COLUMNS}

                q = {
                    "dataset": dataset,
                    "codes": codes_raw,
                    "states": states_raw,
                    "min_services": str(min_services or ""),
                    "device_category": device_category or "",
                }
                export_url = "/cms/export?" + urlencode(q)

            columns = list(preview.columns)
            rows = preview.to_dict(orient="records")
            
            # Enrich with HCPCS code descriptions
            hcpcs_lookup = get_hcpcs_lookup()
            for code in codes:
                code_info = hcpcs_lookup.get_code(code)
                if code_info:
                    code_descriptions[code.upper()] = {
                        "short": code_info.short_description or code_info.long_description[:50],
                        "long": code_info.long_description,
                    }
            searched_codes = codes
        except Exception as e:
            logger.error(f"Error in explorer: {str(e)}", exc_info=True)
            error = str(e)

    return render_template(
        "cms_explorer.html",
        dataset=dataset,
        states=states_raw,
        codes=codes_raw,
        min_services=min_services_raw,
        procedure=procedure_raw,
        device_category=device_category,
        device_categories=device_categories,
        submitted=submitted,
        columns=columns,
        column_labels=column_labels,
        rows=rows,
        summary=summary,
        export_url=export_url,
        error=error,
        notice=notice,
        is_doctors_by_code=(dataset != "Hospitals"),
        search_mode=search_mode,
        code_descriptions=code_descriptions,
        searched_codes=searched_codes,
    )


@cms_bp.route("/export", methods=["GET"])
def export():
    dataset = request.args.get("dataset", "DoctorsByCode")
    states_raw = request.args.get("states", "")
    codes_raw = request.args.get("codes", "")
    min_services_raw = request.args.get("min_services", "")
    procedure_raw = request.args.get("procedure", "")
    device_category = request.args.get("device_category", "")

    # If device category is selected, load its codes
    if device_category and not codes_raw:
        classification_manager = CodeClassificationManager()
        category = classification_manager.get_category(device_category)
        if category:
            codes_raw = ", ".join(category.codes)

    states = _parse_csvish_list(states_raw)
    procedure_substrings = _parse_csvish_list(procedure_raw)
    codes = _parse_csvish_list(codes_raw)
    min_services = None
    if str(min_services_raw).strip():
        try:
            min_services = int(str(min_services_raw).strip())
        except Exception:
            min_services = None

    def _stream_csv(df):
        # Stream CSV in chunks to avoid large in-memory buffers
        header = True
        for start in range(0, len(df), 5_000):
            chunk = df.iloc[start : start + 5_000]
            buf = io.StringIO()
            chunk.to_csv(buf, index=False, header=header)
            header = False
            yield buf.getvalue()

    if dataset == "Hospitals":
        if codes:
            filtered = hospitals_by_codes(codes=codes, states=states, min_procedures=min_services, max_rows=250)
            filename = "hospitals_by_code.csv"
        else:
            files = data_loading.discover_hospital_files(current_app.config["HOSPITALS_DIR"])
            df = data_loading.get_hospitals_df(files)
            filtered = filter_hospitals(df, states=states)
            filename = "hospitals_filtered.csv"
    else:  # DoctorsByCode
        filtered = doctors_by_codes(codes=codes, states=states, min_services=min_services, max_rows=250)
        filename = "doctors_by_code.csv"

    return Response(
        _stream_csv(filtered),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@cms_bp.route("/code-lookup", methods=["GET"])
def code_lookup():
    """HCPCS code lookup and search interface."""
    query = request.args.get("query", "").strip()
    codes = []
    popular_codes = []
    
    hcpcs_lookup = get_hcpcs_lookup()
    
    if query:
        # Search for codes
        code_objects = hcpcs_lookup.search_codes(query, limit=50)
        codes = [code.to_dict() for code in code_objects]
    else:
        # Show popular codes for medical device companies
        # These are common device-related codes
        popular_code_list = [
            "L8679", "A4593", "62270", "62272", "61889", "77080",
            "27215", "27216", "27217", "27218", "27236", "27244",
            "27447", "27486", "27487", "27130", "27132",
            "22840", "22842", "22843", "22844", "22845",
            "C1776", "C1778", "C1821", "C1822",
        ]
        
        for code_str in popular_code_list:
            code_obj = hcpcs_lookup.get_code(code_str)
            if code_obj:
                popular_codes.append({
                    "code": code_obj.code,
                    "description": code_obj.short_description or code_obj.long_description[:80],
                })
    
    return render_template(
        "code_lookup.html",
        query=query,
        codes=codes,
        popular_codes=popular_codes,
    )


# Code analytics route removed - too slow. Use inline insights in explorer instead.


@cms_bp.route("/hospital/<facility_id>", methods=["GET"])
def hospital_detail(facility_id: str):
    """Hospital detail page showing physicians and statistics."""
    codes_raw = request.args.get("codes", "")
    codes = _parse_csvish_list(codes_raw) if codes_raw else None
    
    # Get hospital info
    from .cms_query import load_hospital_metadata
    hospitals = load_hospital_metadata()
    hospital_row = hospitals[hospitals["facility_id"] == facility_id]
    
    if hospital_row.empty:
        return render_template(
            "error.html",
            error="Hospital not found",
            message=f"Hospital with Facility ID {facility_id} not found in database.",
        ), 404
    
    hospital = hospital_row.iloc[0].to_dict()
    
    # Get physicians at this hospital for the codes
    physicians = []
    if codes:
        physicians_df = get_hospital_physicians(facility_id, codes=codes, max_rows=500)
        physicians = physicians_df.to_dict(orient="records")
        
        # Add hospital stats if available
        hospitals_df = hospitals_by_codes(codes=codes, max_rows=10000)
        hosp_stats = hospitals_df[hospitals_df["facility_id"] == facility_id]
        if not hosp_stats.empty:
            stats = hosp_stats.iloc[0]
            hospital["total_procedures"] = stats.get("total_procedures", 0)
            hospital["total_payments"] = stats.get("total_payments", 0)
            hospital["num_physicians"] = stats.get("num_physicians", 0)
            hospital["code_breakdown"] = stats.get("code_breakdown", "")
    
    return render_template(
        "hospital_detail.html",
        hospital=hospital,
        physicians=physicians,
        codes=codes,
    )


@cms_bp.route("/api/code-autocomplete", methods=["GET"])
def code_autocomplete():
    """API endpoint for code autocomplete."""
    prefix = request.args.get("q", "").strip()
    if not prefix or len(prefix) < 2:
        return {"results": []}
    
    hcpcs_lookup = get_hcpcs_lookup()
    results = hcpcs_lookup.autocomplete(prefix, limit=20)
    
    return {"results": results}


@cms_bp.route("/code-classification", methods=["GET", "POST"])
def code_classification():
    """Manage device categories and code classifications."""
    manager = CodeClassificationManager()
    error: str | None = None
    success: str | None = None

    if request.method == "POST":
        action = request.form.get("action")
        
        try:
            if action == "create":
                name = request.form.get("name", "").strip()
                description = request.form.get("description", "").strip()
                if not name:
                    error = "Category name is required."
                else:
                    manager.add_category(name, description)
                    success = f"Category '{name}' created successfully."
                    logger.info(f"Created device category: {name}")
            
            elif action == "update":
                name = request.form.get("name", "").strip()
                description = request.form.get("description", "").strip()
                if not name:
                    error = "Category name is required."
                else:
                    manager.update_category(name, description)
                    success = f"Category '{name}' updated successfully."
                    logger.info(f"Updated device category: {name}")
            
            elif action == "delete":
                name = request.form.get("name", "").strip()
                if manager.delete_category(name):
                    success = f"Category '{name}' deleted successfully."
                    logger.info(f"Deleted device category: {name}")
                else:
                    error = f"Category '{name}' not found."
            
            elif action == "add_code":
                category_name = request.form.get("category_name", "").strip()
                code = request.form.get("code", "").strip().upper()
                if not category_name or not code:
                    error = "Category name and code are required."
                elif manager.add_code_to_category(category_name, code):
                    success = f"Code '{code}' added to category '{category_name}'."
                    logger.info(f"Added code {code} to category {category_name}")
                else:
                    error = f"Code '{code}' already in category '{category_name}' or category not found."
            
            elif action == "remove_code":
                category_name = request.form.get("category_name", "").strip()
                code = request.form.get("code", "").strip().upper()
                if not category_name or not code:
                    error = "Category name and code are required."
                elif manager.remove_code_from_category(category_name, code):
                    success = f"Code '{code}' removed from category '{category_name}'."
                    logger.info(f"Removed code {code} from category {category_name}")
                else:
                    error = f"Code '{code}' not found in category '{category_name}' or category not found."
        
        except ValueError as e:
            error = str(e)
            logger.error(f"Error in code classification: {error}")
        except Exception as e:
            error = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error in code classification: {str(e)}", exc_info=True)

    categories = manager.get_all_categories()
    
    return render_template(
        "code_classification.html",
        categories=categories,
        error=error,
        success=success,
    )
