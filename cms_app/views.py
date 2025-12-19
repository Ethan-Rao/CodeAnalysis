from __future__ import annotations

import io
from urllib.parse import urlencode

from flask import Blueprint, Response, current_app, render_template, request

from . import data_loading
from .filters import filter_doctors, filter_hospitals

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
    dataset = request.values.get("dataset", "Doctors")
    states_raw = request.values.get("states", "")
    procedure_raw = request.values.get("procedure", "")

    submitted = request.method == "POST"

    rows = []
    columns: list[str] = []
    summary: str | None = None
    export_url: str | None = None
    error: str | None = None

    if submitted:
        try:
            states = _parse_csvish_list(states_raw)
            procedure_substrings = _parse_csvish_list(procedure_raw)

            if dataset == "Hospitals":
                files = data_loading.discover_hospital_files(current_app.config["HOSPITALS_DIR"])
                df = data_loading.get_hospitals_df(files)
                filtered = filter_hospitals(df, states=states)
                summary = f"Found {len(filtered):,} hospitals" + (f" in {', '.join([s.upper() for s in states])}." if states else ".")
                preview = filtered.head(current_app.config["MAX_TABLE_ROWS"])
            else:
                files = data_loading.discover_doctors_files(current_app.config["DOCTORS_DIR"])
                df = data_loading.get_doctors_filtered(files, states=states, procedure_substrings=procedure_substrings)
                filtered = filter_doctors(df, states=None, procedure_substrings=None)
                bits = [f"Found {len(filtered):,} doctors"]
                if states:
                    bits.append(f"in {', '.join([s.upper() for s in states])}")
                if procedure_substrings:
                    bits.append(f"categories matching {procedure_substrings}")
                summary = " ".join(bits) + "."
                preview = filtered.head(current_app.config["MAX_TABLE_ROWS"])

            columns = list(preview.columns)
            rows = preview.to_dict(orient="records")

            q = {
                "dataset": dataset,
                "states": states_raw,
                "procedure": procedure_raw,
            }
            export_url = "/cms/export?" + urlencode(q)
        except Exception as e:  # keep v1 friendly
            error = str(e)

    return render_template(
        "cms_explorer.html",
        dataset=dataset,
        states=states_raw,
        procedure=procedure_raw,
        submitted=submitted,
        columns=columns,
        rows=rows,
        summary=summary,
        export_url=export_url,
        error=error,
    )


@cms_bp.route("/export", methods=["GET"])
def export():
    dataset = request.args.get("dataset", "Doctors")
    states_raw = request.args.get("states", "")
    procedure_raw = request.args.get("procedure", "")

    states = _parse_csvish_list(states_raw)
    procedure_substrings = _parse_csvish_list(procedure_raw)

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
        files = data_loading.discover_hospital_files(current_app.config["HOSPITALS_DIR"])
        df = data_loading.get_hospitals_df(files)
        filtered = filter_hospitals(df, states=states)
        filename = "hospitals_filtered.csv"
    else:
        files = data_loading.discover_doctors_files(current_app.config["DOCTORS_DIR"])
        df = data_loading.get_doctors_filtered(files, states=states, procedure_substrings=procedure_substrings)
        filtered = filter_doctors(df, states=None, procedure_substrings=None)
        filename = "doctors_filtered.csv"

    return Response(
        _stream_csv(filtered),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
