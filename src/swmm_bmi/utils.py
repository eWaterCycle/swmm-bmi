from pathlib import Path
import json


def read_config(config_file: str) -> dict:
    with open(config_file) as cfg:
        return json.load(cfg)


def get_inp_file(config: dict, config_file: str, file_path: str = "inp_file") -> Path:
    inp_file = Path(config[file_path])
    if not inp_file.exists():
        raise FileNotFoundError(f"SWMM input file not found: {inp_file}")
    if not inp_file.is_absolute():
        inp_file = Path(config_file).parent / inp_file
    return inp_file


def parse_subcatchment_gages(inp_file: Path) -> dict:
    """Return {subcatchment_id: gage_id} parsed from [SUBCATCHMENTS] section."""
    result = {}
    in_section = False
    with open(inp_file) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("["):
                in_section = stripped.upper().startswith("[SUBCATCHMENTS]")
                continue
            if not in_section or not stripped or stripped.startswith(";"):
                continue
            parts = stripped.split()
            if len(parts) >= 2:
                result[parts[0]] = parts[1]  # subcatchment_id: gage_id
    return result


def parse_flow_units(inp_file: Path) -> str:
    """Return the unit system ('US' or 'SI') from FLOW_UNITS in [OPTIONS].

    SWMM US flow units (CFS, GPM, MGD) imply rainfall in in/hr; SI units
    (CMS, LPS, MLD) imply mm/hr. Falls back to 'US' if not found.
    """
    us_units = {"CFS", "GPM", "MGD"}
    in_options = False
    with open(inp_file) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("["):
                in_options = stripped.upper().startswith("[OPTIONS]")
                continue
            if not in_options or not stripped or stripped.startswith(";"):
                continue
            parts = stripped.split()
            if parts[0].upper() == "FLOW_UNITS":
                return "US" if parts[1].upper() in us_units else "SI"
    return "US"


def parse_routing_step(inp_file: Path) -> float:
    """Read ROUTING_STEP from the [OPTIONS] section of a SWMM .inp file.

    Accepts both HH:MM:SS and plain-seconds formats.
    Returns seconds as a float; falls back to 300.0 if not found.
    """
    in_options = False
    with open(inp_file) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("["):
                in_options = stripped.upper().startswith("[OPTIONS]")
                continue
            if not in_options or not stripped or stripped.startswith(";"):
                continue
            parts = stripped.split()
            if parts[0].upper() == "ROUTING_STEP":
                val = parts[1]
                if ":" in val:
                    h, m, s = val.split(":")
                    return int(h) * 3600 + int(m) * 60 + float(s)
                return float(val)
    return 300.0
