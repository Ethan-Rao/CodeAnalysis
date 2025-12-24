from __future__ import annotations

from pathlib import Path


class Config:
    # Project root = folder containing this file's parent (cms_app/..)
    PROJECT_ROOT = Path(__file__).resolve().parents[1]

    # Data folders (raw downloads; treated read-only)
    DOCTORS_DIR = PROJECT_ROOT / "Doctors_08_2025"

    # Your workspace uses lowercase "hospitals_08_2025".
    # Keep a fallback for "Hospitals_08_2025" just in case.
    HOSPITALS_DIR = (
        PROJECT_ROOT / "hospitals_08_2025"
        if (PROJECT_ROOT / "hospitals_08_2025").exists()
        else PROJECT_ROOT / "Hospitals_08_2025"
    )

    MAX_TABLE_ROWS = 200
    
    # Code classification file
    CODE_CLASSIFICATIONS_FILE = PROJECT_ROOT / "code_classifications.json"