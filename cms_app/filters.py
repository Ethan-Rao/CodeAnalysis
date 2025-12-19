from __future__ import annotations

from typing import Iterable

import pandas as pd


def _normalize_states(states: list[str] | None) -> list[str]:
    if not states:
        return []
    cleaned: list[str] = []
    for s in states:
        if s is None:
            continue
        s2 = str(s).strip().upper()
        if not s2:
            continue
        cleaned.append(s2)
    # de-dupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for s in cleaned:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _normalize_substrings(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned: list[str] = []
    for v in values:
        if v is None:
            continue
        v2 = str(v).strip()
        if not v2:
            continue
        cleaned.append(v2)
    seen: set[str] = set()
    out: list[str] = []
    for v in cleaned:
        key = v.lower()
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out


def filter_doctors(
    df: pd.DataFrame,
    states: list[str] | None = None,
    procedure_substrings: list[str] | None = None,
) -> pd.DataFrame:
    """
    - states: list of 2-letter codes; if None/empty, do not filter by state.
    - procedure_substrings: list of case-insensitive substrings matched against procedure_category.
      If None/empty, do not filter by category.
    - Returns a dataframe sorted by count (desc), then last_name, first_name.
    """
    out = df

    st = _normalize_states(states)
    if st:
        if "state" not in out.columns:
            raise KeyError("Expected column 'state' in doctors dataframe")
        out = out[out["state"].astype(str).str.upper().isin(st)]

    subs = _normalize_substrings(procedure_substrings)
    if subs:
        if "procedure_category" not in out.columns:
            raise KeyError("Expected column 'procedure_category' in doctors dataframe")
        cat = out["procedure_category"].astype(str)
        mask = pd.Series(False, index=out.index)
        for sub in subs:
            mask = mask | cat.str.contains(sub, case=False, na=False)
        out = out[mask]

    sort_cols: list[str] = []
    if "count" in out.columns:
        sort_cols.append("count")
    for c in ["last_name", "first_name"]:
        if c in out.columns:
            sort_cols.append(c)

    if sort_cols:
        ascending = [False] + [True] * (len(sort_cols) - 1) if sort_cols[0] == "count" else [True] * len(sort_cols)
        out = out.sort_values(sort_cols, ascending=ascending, kind="mergesort")

    return out


def filter_hospitals(
    df: pd.DataFrame,
    states: list[str] | None = None,
) -> pd.DataFrame:
    """Filter hospitals by state (2-letter). If None/empty, return all."""
    out = df
    st = _normalize_states(states)
    if st:
        if "state" not in out.columns:
            raise KeyError("Expected column 'state' in hospitals dataframe")
        out = out[out["state"].astype(str).str.upper().isin(st)]

    # Stable and predictable ordering
    for col in ["hospital_name", "city", "state"]:
        if col in out.columns:
            out = out.sort_values([c for c in ["state", "hospital_name"] if c in out.columns], kind="mergesort")
            break

    return out
