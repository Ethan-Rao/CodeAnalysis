from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from cms_app.data_loading import discover_doctors_files, query_doctors
from cms_app.filters import filter_doctors


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    doctors_dir = root / "Doctors_08_2025"

    files = discover_doctors_files(doctors_dir)
    df = query_doctors(files, states=["OR", "WA"], procedure_substrings=["bone", "spine"])
    filtered = filter_doctors(df)
    print(filtered.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
