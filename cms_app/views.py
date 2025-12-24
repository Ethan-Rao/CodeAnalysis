from __future__ import annotations

import io
import re
from urllib.parse import urlencode

import pandas as pd
from flask import Blueprint, Response, current_app, redirect, render_template, request, url_for

from . import data_loading
from .code_classification import CodeClassificationManager
from .cms_query import DOCTORS_BY_CODE_UI_COLUMNS, doctors_by_codes
from .filters import filter_doctors, filter_hospitals
from .hcpcs_lookup import get_hcpcs_lookup
from .hospital_analytics import hospitals_by_codes
from .logger import logger

cms_bp = Blueprint("cms", __name__, template_folder="templates", static_folder="static")


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
    dataset = request.values.get("dataset", "DoctorsByCode")
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
                
                # Use hospital analytics
                filtered = hospitals_by_codes(codes=codes, states=states, min_procedures=min_services, max_rows=250)
                
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

                df = doctors_by_codes(codes=codes, states=states, min_services=min_services, max_rows=250)
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
