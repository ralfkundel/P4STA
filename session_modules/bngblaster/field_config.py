import json
import os
import tempfile
from pathlib import Path

from session_modules.bngblaster import session_mod


def get_config(module_cfg):
    config = module_cfg.get("config", {})
    for section in ("runtime_specific", "setup_specific"):
        for entry in config.get(section, []):
            if entry.get("target_key") == "dyn_cfg":
                return entry
    raise ValueError("Session modification fields are not configured.")


def get_options(module_cfg):
    config = get_config(module_cfg)
    selected = config.get("selected_values", [])
    return [
        {"name": field[0] + "." + field[1], "selected": field in selected}
        for field in config.get("values_to_select", [])
    ]


def select_fields(module_cfg, names):
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise ValueError("Session fields must be a list of field names.")
    available = get_config(module_cfg).get("values_to_select", [])
    allowed = {field[0] + "." + field[1] for field in available}
    if not names or set(names) - allowed:
        raise ValueError("Select at least one valid session modification field.")
    fields = {name: 1 for name in names}
    session_mod.get_used_groups(fields)
    # All enabled session mapping actions require Ethernet and IPv4.
    required = session_mod.GROUP_FIELDS["ethernet"] + session_mod.GROUP_FIELDS["ipv4"]
    if not set(required).issubset(names):
        raise ValueError("Session mapping requires both Ethernet and both IPv4 fields.")
    if "pppoe.sessionID" in names and "vlan_qinq.vid" in names and "vlan.vid" not in names:
        raise ValueError("Upstream QinQ requires vlan.vid as well as vlan_qinq.vid.")
    return [field for field in available if field[0] + "." + field[1] in names]


def save_selected_fields(module_cfg, selected, module_path):
    path = Path(module_path) / "module_cfg.json"
    # Read again to preserve other settings saved while the profile was applied.
    with path.open() as source:
        saved = json.load(source)
    get_config(saved)["selected_values"] = selected
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as target:
            temporary_path = target.name
            json.dump(saved, target, indent="\t")
            target.write("\n")
        os.chmod(temporary_path, path.stat().st_mode & 0o777)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)
    get_config(module_cfg)["selected_values"] = selected
