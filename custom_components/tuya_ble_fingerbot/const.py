from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "tuya_ble_fingerbot"

CONF_MAC: Final = "mac"
CONF_LOCAL_KEY: Final = "local_key"
CONF_UUID: Final = "uuid"
CONF_DEVICE_ID: Final = "device_id"
CONF_PRODUCT_ID: Final = "product_id"
CONF_PRODUCT_NAME: Final = "product_name"
CONF_PROFILE: Final = "profile"
CONF_INCLUDE_MOTION: Final = "include_motion"
CONF_TIMEOUT: Final = "timeout"

DEFAULT_NAME: Final = "Fingerbot Plus"
DEFAULT_TIMEOUT: Final = 12.0

PLATFORMS: Final = [Platform.BUTTON]
