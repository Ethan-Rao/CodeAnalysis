"""Data validation and health checks for CMS data files."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .config import Config
from .logger import logger


def check_data_files() -> Dict[str, Dict[str, any]]:
    """
    Check if required data files exist and are accessible.
    
    Returns:
        Dictionary with status for each data source
    """
    status = {}
    
    # Check physician PUF file
    phys_path = Config.PROJECT_ROOT / "physHCPCS.csv"
    status["physician_puf"] = {
        "exists": phys_path.exists(),
        "path": str(phys_path),
        "readable": phys_path.exists() and phys_path.is_file(),
    }
    
    # Check hospital directory
    hosp_dir = Config.HOSPITALS_DIR
    status["hospitals"] = {
        "exists": hosp_dir.exists(),
        "path": str(hosp_dir),
        "readable": hosp_dir.exists() and hosp_dir.is_dir(),
    }
    
    # Check HCPCS data
    hcpcs_file = Config.HCPCS_DATA_DIR / "HCPC2026_JAN_ANWEB_12082025.txt"
    status["hcpcs"] = {
        "exists": hcpcs_file.exists(),
        "path": str(hcpcs_file),
        "readable": hcpcs_file.exists() and hcpcs_file.is_file(),
    }
    
    # Check referring provider PUF (for HCPCS A-codes)
    ref_path = Config.REFERRING_PUF
    status["referring_puf"] = {
        "exists": ref_path.exists(),
        "path": str(ref_path),
        "readable": ref_path.exists() and ref_path.is_file(),
    }
    
    # Check facility affiliations
    fac_aff_path = Config.DOCTORS_DIR / "Facility_Affiliation.csv"
    status["facility_affiliations"] = {
        "exists": fac_aff_path.exists(),
        "path": str(fac_aff_path),
        "readable": fac_aff_path.exists() and fac_aff_path.is_file(),
    }
    
    return status


def get_data_health_summary() -> str:
    """Get a human-readable summary of data file health."""
    status = check_data_files()
    
    issues = []
    for name, info in status.items():
        if not info["exists"]:
            issues.append(f"{name}: File/directory not found at {info['path']}")
        elif not info["readable"]:
            issues.append(f"{name}: File/directory exists but is not readable")
    
    if not issues:
        return "All required data files are present and accessible."
    
    return "Data file issues:\n" + "\n".join(f"  - {issue}" for issue in issues)

