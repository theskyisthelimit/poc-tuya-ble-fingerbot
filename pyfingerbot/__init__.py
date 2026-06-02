from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_FINGERBOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "tuya_ble_fingerbot"
    / "fingerbot.py"
)
_SPEC = importlib.util.spec_from_file_location("_tuya_ble_fingerbot_core", _FINGERBOT_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load Fingerbot core from {_FINGERBOT_PATH}")

_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

for _name, _value in vars(_MODULE).items():
    if not _name.startswith("_"):
        globals()[_name] = _value

__all__ = [_name for _name in globals() if not _name.startswith("_")]
