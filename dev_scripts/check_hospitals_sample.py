from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from cms_app.data_loading import discover_hospital_files, get_hospitals_df
from cms_app.filters import filter_hospitals


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    hospitals_dir = root / "hospitals_08_2025"
    if not hospitals_dir.exists():
        hospitals_dir = root / "Hospitals_08_2025"

    files = discover_hospital_files(hospitals_dir)
    df = get_hospitals_df(files)

    filtered = filter_hospitals(df, states=["OR", "WA"])
    print(filtered.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
