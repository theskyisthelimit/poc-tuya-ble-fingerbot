from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_ID,
    CONF_INCLUDE_MOTION,
    CONF_LOCAL_KEY,
    CONF_MAC,
    CONF_PRODUCT_ID,
    CONF_PRODUCT_NAME,
    CONF_PROFILE,
    CONF_TIMEOUT,
    CONF_UUID,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .fingerbot import FingerBot


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tuya BLE Fingerbot button entities."""
    async_add_entities([TuyaBleFingerbotPressButton(hass, entry)])


class TuyaBleFingerbotPressButton(ButtonEntity):
    """Button that presses a Tuya BLE Fingerbot."""

    _attr_has_entity_name = True
    _attr_translation_key = "press"
    entity_description = ButtonEntityDescription(key="press")

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        data = entry.data
        device_id = data[CONF_DEVICE_ID]
        product_name = data.get(CONF_PRODUCT_NAME) or DEFAULT_NAME
        self._attr_unique_id = f"{device_id}_press"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=data.get(CONF_NAME, DEFAULT_NAME),
            manufacturer="Tuya",
            model=product_name,
        )

    async def async_press(self) -> None:
        """Press the Fingerbot."""
        data = self.entry.data
        address = data[CONF_MAC]
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass,
            address,
            connectable=True,
        )
        async with FingerBot(
            address,
            data[CONF_LOCAL_KEY],
            data[CONF_UUID],
            data[CONF_DEVICE_ID],
            product_id=data.get(CONF_PRODUCT_ID) or None,
            profile=data.get(CONF_PROFILE, "auto"),
            response_timeout=float(data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            ble_device=ble_device,
        ) as fingerbot:
            await fingerbot.press(
                include_motion=bool(data.get(CONF_INCLUDE_MOTION, True)),
            )
