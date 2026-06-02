from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, replace
from enum import Enum
from struct import pack, unpack
from typing import Any

try:
    from Crypto.Cipher import AES
except ImportError as exc:  # pragma: no cover - exercised by runtime users
    raise RuntimeError(
        "pycryptodome is required. Install dependencies with "
        "`python3 -m pip install -r requirements.txt`."
    ) from exc

_LOGGER = logging.getLogger(__name__)

GATT_MTU = 20
DEFAULT_RESPONSE_TIMEOUT = 12.0
NOTIFY_UUID = "00002b10-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "00002b11-0000-1000-8000-00805f9b34fb"


class Coder(Enum):
    FUN_SENDER_DEVICE_INFO = 0x0000
    FUN_SENDER_PAIR = 0x0001
    FUN_SENDER_DPS = 0x0002
    FUN_SENDER_DEVICE_STATUS = 0x0003
    FUN_RECEIVE_DP = 0x8001
    FUN_RECEIVE_TIME_DP = 0x8003
    FUN_RECEIVE_SIGN_DP = 0x8004
    FUN_RECEIVE_SIGN_TIME_DP = 0x8005
    FUN_RECEIVE_TIME1_REQ = 0x8011
    FUN_RECEIVE_TIME2_REQ = 0x8012


class DpType(Enum):
    RAW = 0
    BOOLEAN = 1
    INT = 2
    STRING = 3
    ENUM = 4
    BITMAP = 5


class DpAction(Enum):
    CUBETOUCH_SWITCH = 1
    TOGGLE_SWITCH = 2
    MODE = 8
    ARM_DOWN_PERCENT = 9
    CLICK_SUSTAIN_TIME = 10
    INVERT_SWITCH = 11
    ARM_UP_PERCENT = 15
    TAP_ENABLE = 17
    LEGACY_CLICK = 101
    KG_MODE = 101
    KG_ARM_DOWN_PERCENT = 102
    KG_CLICK_SUSTAIN_TIME = 103
    KG_INVERT_SWITCH = 104
    KG_BATTERY = 105
    KG_ARM_UP_PERCENT = 106
    KG_TAP_ENABLE = 107
    KG_CLICK = 108
    PROG = 121


class FingerBotError(Exception):
    """Base Fingerbot error."""


class FingerBotProtocolError(FingerBotError):
    """Invalid Tuya BLE packet or unsupported protocol response."""


class FingerBotTimeoutError(FingerBotError):
    """Device did not answer a request before timeout."""


class FingerBotPairingError(FingerBotError):
    """Device refused pairing."""


@dataclass(frozen=True)
class DataPoint:
    id: int
    type: DpType
    value: bytes | bool | int | str

    def encode(self) -> bytes:
        raw_value: bytes
        if self.type in (DpType.RAW, DpType.BITMAP):
            raw_value = bytes(self.value)
        elif self.type == DpType.BOOLEAN:
            raw_value = pack(">B", 1 if bool(self.value) else 0)
        elif self.type == DpType.INT:
            raw_value = pack(">i", int(self.value))
        elif self.type == DpType.ENUM:
            value = int(self.value)
            if value < 0:
                raise FingerBotProtocolError("ENUM datapoints cannot be negative")
            if value <= 0xFF:
                raw_value = pack(">B", value)
            elif value <= 0xFFFF:
                raw_value = pack(">H", value)
            else:
                raw_value = pack(">I", value)
        elif self.type == DpType.STRING:
            raw_value = str(self.value).encode("utf-8")
        else:  # pragma: no cover - Enum exhaustiveness guard
            raise FingerBotProtocolError(f"Unsupported datapoint type: {self.type}")

        if len(raw_value) > 0xFF:
            raise FingerBotProtocolError("Datapoint payload too large")
        return pack(">BBB", int(self.id), int(self.type.value), len(raw_value)) + raw_value


@dataclass(frozen=True)
class FingerBotProfile:
    name: str
    product_ids: tuple[str, ...]
    click_dp: int
    mode_dp: int | None = None
    mode_value: int = 0
    down_dp: int | None = None
    up_dp: int | None = None
    hold_dp: int | None = None
    down_position: int = 80
    up_position: int = 0
    hold_time: int = 0
    click_value: bool = True

    def with_motion(
        self,
        down_position: int,
        up_position: int,
        hold_time: int,
    ) -> "FingerBotProfile":
        return replace(
            self,
            down_position=down_position,
            up_position=up_position,
            hold_time=hold_time,
        )

    def build_press_datapoints(self, include_motion: bool = True) -> list[DataPoint]:
        dps: list[DataPoint] = []
        if self.mode_dp is not None:
            dps.append(DataPoint(self.mode_dp, DpType.ENUM, self.mode_value))
        if include_motion:
            if self.down_dp is not None:
                dps.append(DataPoint(self.down_dp, DpType.INT, self.down_position))
            if self.up_dp is not None:
                dps.append(DataPoint(self.up_dp, DpType.INT, self.up_position))
            if self.hold_dp is not None:
                dps.append(DataPoint(self.hold_dp, DpType.INT, self.hold_time))
        dps.append(DataPoint(self.click_dp, DpType.BOOLEAN, self.click_value))
        return dps


PROFILE_CLASSIC = FingerBotProfile(
    name="classic",
    product_ids=(
        "blliqpsj",
        "ndvkgsrm",
        "yiihr7zh",
        "neq16kgd",
        "ltak7e1p",
        "y6kttvd6",
        "yrnk7mnn",
        "nvr2rocq",
        "bnt7wajf",
        "rvdceqjh",
        "5xhbk964",
    ),
    click_dp=2,
    mode_dp=8,
    down_dp=9,
    up_dp=15,
    hold_dp=10,
)

PROFILE_CUBETOUCH = FingerBotProfile(
    name="cubetouch",
    product_ids=("3yqdo5yt", "xhf790if"),
    click_dp=1,
    mode_dp=2,
    down_dp=6,
    up_dp=5,
    hold_dp=3,
)

PROFILE_KG = FingerBotProfile(
    name="kg",
    product_ids=("mknd4lci", "riecov42"),
    click_dp=108,
    mode_dp=101,
    down_dp=102,
    up_dp=106,
    hold_dp=103,
)

PROFILE_LEGACY = FingerBotProfile(
    name="legacy",
    product_ids=(),
    click_dp=101,
    mode_dp=8,
    down_dp=9,
    up_dp=15,
    hold_dp=10,
)

PROFILES = {
    profile.name: profile
    for profile in (
        PROFILE_CLASSIC,
        PROFILE_CUBETOUCH,
        PROFILE_KG,
        PROFILE_LEGACY,
    )
}


def get_profile(profile: str = "auto", product_id: str | None = None) -> FingerBotProfile:
    if profile != "auto":
        try:
            return PROFILES[profile]
        except KeyError as exc:
            known = ", ".join(["auto", *PROFILES])
            raise FingerBotError(f"Unknown profile {profile!r}. Known profiles: {known}") from exc

    if product_id:
        for candidate in PROFILES.values():
            if product_id in candidate.product_ids:
                return candidate
    return PROFILE_CLASSIC


class SecretKeyManager:
    def __init__(self, login_key: bytes):
        self.login_key = login_key
        self.keys = {
            4: hashlib.md5(self.login_key).digest(),
        }

    def get(self, security_flag: int) -> bytes:
        try:
            return self.keys[security_flag]
        except KeyError as exc:
            raise FingerBotProtocolError(
                f"No key available for security flag {security_flag}"
            ) from exc

    def setSrand(self, srand: bytes) -> None:
        self.keys[5] = hashlib.md5(self.login_key + srand).digest()


class DeviceInfoResp:
    def __init__(self) -> None:
        self.success = False
        self.device_version = ""
        self.protocol_version = ""
        self.protocol_major = 2
        self.protocol_minor = 0
        self.flag = 0
        self.is_bind = 0
        self.srand = b""
        self.hardware_version = ""
        self.auth_key = b""

    def parse(self, raw: bytes) -> None:
        if len(raw) < 46:
            raise FingerBotProtocolError("Device info response too short")
        (
            device_version_major,
            device_version_minor,
            protocol_version_major,
            protocol_version_minor,
            flag,
            is_bind,
            srand,
            hardware_version_major,
            hardware_version_minor,
            auth_key,
        ) = unpack(">BBBBBB6sBB32s", raw[:46])

        self.device_version = f"{device_version_major}.{device_version_minor}"
        self.protocol_version = f"{protocol_version_major}.{protocol_version_minor}"
        self.protocol_major = protocol_version_major
        self.protocol_minor = protocol_version_minor
        self.flag = flag
        self.is_bind = is_bind
        self.srand = srand
        self.hardware_version = f"{hardware_version_major}.{hardware_version_minor}"
        self.auth_key = auth_key

        protocol_number = protocol_version_major * 10 + protocol_version_minor
        self.success = protocol_number >= 20


class Ret:
    def __init__(self, raw: bytes, version: int):
        self.raw = raw
        self.version = version
        self.security_flag = 0
        self.iv = b""
        self.seq_num = 0
        self.response_to = 0
        self.code: Coder | int = 0
        self.data = b""
        self.resp: DeviceInfoResp | int | None = None

    def parse(self, secret_key: bytes) -> None:
        if len(self.raw) < 17:
            raise FingerBotProtocolError("Encrypted response too short")
        self.security_flag = self.raw[0]
        self.iv = self.raw[1:17]
        encrypted_data = self.raw[17:]
        decrypted_data = AesUtils.decrypt(encrypted_data, self.iv, secret_key)

        if len(decrypted_data) < 12:
            raise FingerBotProtocolError("Decrypted response too short")
        self.seq_num, self.response_to, code, length = unpack(">IIHH", decrypted_data[:12])
        data_end = 12 + length
        if len(decrypted_data) < data_end:
            raise FingerBotProtocolError("Decrypted response payload truncated")
        self.data = decrypted_data[12:data_end]

        if len(decrypted_data) >= data_end + 2:
            expected_crc = CrcUtils.crc16(decrypted_data[:data_end])
            (actual_crc,) = unpack(">H", decrypted_data[data_end:data_end + 2])
            if expected_crc != actual_crc:
                raise FingerBotProtocolError(
                    f"CRC mismatch: got {actual_crc:#06x}, expected {expected_crc:#06x}"
                )

        try:
            self.code = Coder(code)
        except ValueError:
            self.code = code

        if self.code == Coder.FUN_SENDER_DEVICE_INFO:
            resp = DeviceInfoResp()
            resp.parse(self.data)
            self.resp = resp
        elif self.code in (
            Coder.FUN_SENDER_PAIR,
            Coder.FUN_SENDER_DEVICE_STATUS,
        ):
            if len(self.data) != 1:
                raise FingerBotProtocolError(f"{self.code.name} response has invalid length")
            self.resp = self.data[0]


class BleReceiver:
    def __init__(self, secret_key_manager: SecretKeyManager):
        self.expected_packet = 0
        self.data_length = 0
        self.raw = bytearray()
        self.version = 0
        self.secret_key_manager = secret_key_manager

    @staticmethod
    def unpack_int(data: bytes | bytearray, start_pos: int = 0) -> tuple[int, int]:
        result = 0
        offset = 0
        while offset < 5:
            pos = start_pos + offset
            if pos >= len(data):
                raise FingerBotProtocolError("Varint truncated")
            curr_byte = data[pos]
            result |= (curr_byte & 0x7F) << (offset * 7)
            offset += 1
            if (curr_byte & 0x80) == 0:
                return result, start_pos + offset
        raise FingerBotProtocolError("Varint too long")

    def unpack(self, data: bytes | bytearray) -> int:
        packet_number, pos = self.unpack_int(data, 0)

        if packet_number == 0:
            self.raw.clear()
            self.expected_packet = 0
            self.data_length, pos = self.unpack_int(data, pos)
            if pos >= len(data):
                return 2
            self.version = (data[pos] >> 4) & 0x0F
            pos += 1

        if packet_number != self.expected_packet:
            self.raw.clear()
            self.expected_packet = 0
            raise FingerBotProtocolError(
                f"Unexpected packet {packet_number}, expected {self.expected_packet}"
            )

        self.raw += data[pos:]
        self.expected_packet += 1

        if len(self.raw) < self.data_length:
            return 1
        if len(self.raw) == self.data_length:
            return 0
        self.raw.clear()
        self.expected_packet = 0
        raise FingerBotProtocolError("Received packet payload is longer than advertised")

    def parse_data_received(self, data: bytes | bytearray) -> Ret | None:
        status = self.unpack(data)
        if status != 0:
            return None

        security_flag = self.raw[0]
        secret_key = self.secret_key_manager.get(security_flag)
        ret = Ret(bytes(self.raw), self.version)
        self.raw.clear()
        self.expected_packet = 0
        ret.parse(secret_key)
        return ret


class AesUtils:
    @staticmethod
    def decrypt(data: bytes, iv: bytes, key: bytes) -> bytes:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return cipher.decrypt(data)

    @staticmethod
    def encrypt(data: bytes, iv: bytes, key: bytes) -> bytes:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return cipher.encrypt(data)


class CrcUtils:
    @staticmethod
    def crc16(data: bytes | bytearray) -> int:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte & 255
            for _ in range(8):
                tmp = crc & 1
                crc >>= 1
                if tmp != 0:
                    crc ^= 0xA001
        return crc


class TuyaDataPacket:
    @staticmethod
    def prepare_crc(sn_ack: int, ack_sn: int, code: int, inp: bytes, inp_length: int) -> bytes:
        raw = pack(">IIHH", sn_ack, ack_sn, code, inp_length)
        raw += inp
        crc = CrcUtils.crc16(raw)
        return raw + pack(">H", crc)

    @staticmethod
    def get_random_iv() -> bytes:
        return secrets.token_bytes(16)

    @staticmethod
    def encrypt_packet(secret_key: bytes, security_flag: int, iv: bytes, data: bytes) -> bytes:
        raw = bytearray(data)
        while len(raw) % 16 != 0:
            raw += b"\x00"

        encrypted_data = AesUtils.encrypt(bytes(raw), iv, secret_key)
        return security_flag.to_bytes(1, byteorder="big") + iv + encrypted_data


class XRequest:
    def __init__(
        self,
        sn_ack: int,
        ack_sn: int,
        code: Coder,
        security_flag: int,
        secret_key: bytes,
        iv: bytes,
        inp: bytes,
        protocol_version: int = 2,
        gatt_mtu: int = GATT_MTU,
    ):
        self.gatt_mtu = gatt_mtu
        self.sn_ack = sn_ack
        self.ack_sn = ack_sn
        self.code = code
        self.security_flag = security_flag
        self.secret_key = secret_key
        self.iv = iv
        self.inp = bytes(inp)
        self.protocol_version = protocol_version

    @staticmethod
    def pack_int(value: int) -> bytearray:
        result = bytearray()
        while True:
            curr_byte = value & 0x7F
            value >>= 7
            if value:
                curr_byte |= 0x80
            result += pack(">B", curr_byte)
            if value == 0:
                return result

    def split_packet(self, protocol_version: int, data: bytes) -> list[bytes]:
        output = []
        packet_number = 0
        pos = 0
        length = len(data)
        while pos < length:
            packet = bytearray()
            packet += self.pack_int(packet_number)

            if packet_number == 0:
                packet += self.pack_int(length)
                packet += pack(">B", protocol_version << 4)

            sub_data = data[pos:pos + self.gatt_mtu - len(packet)]
            packet += sub_data
            output.append(bytes(packet))

            pos += len(sub_data)
            packet_number += 1

        return output

    def pack(self) -> list[bytes]:
        data = TuyaDataPacket.prepare_crc(
            self.sn_ack,
            self.ack_sn,
            self.code.value,
            self.inp,
            len(self.inp),
        )
        encrypted_data = TuyaDataPacket.encrypt_packet(
            self.secret_key,
            self.security_flag,
            self.iv,
            data,
        )
        return self.split_packet(self.protocol_version, encrypted_data)


class FingerBot:
    NOTIF_UUID = NOTIFY_UUID
    CHAR_UUID = WRITE_UUID

    def __init__(
        self,
        mac: str,
        local_key: str,
        uuid: str,
        dev_id: str,
        *,
        product_id: str | None = None,
        profile: str = "auto",
        response_timeout: float = DEFAULT_RESPONSE_TIMEOUT,
        bleak_client: Any | None = None,
        ble_device: Any | None = None,
    ):
        self.mac = mac
        self.ble_device = ble_device or mac
        self.uuid = uuid.encode("utf-8")
        self.dev_id = dev_id.encode("utf-8")
        self.local_key = local_key
        self.login_key = local_key[:6].encode("utf-8")
        self.profile = get_profile(profile, product_id)
        self.response_timeout = response_timeout

        self.secret_key_manager = SecretKeyManager(self.login_key)
        self.ble_receiver = BleReceiver(self.secret_key_manager)
        self.reset_sn_ack()
        self.protocol_version = 2
        self.device_version = ""
        self.protocol_version_str = ""
        self.hardware_version = ""
        self.device = bleak_client
        self._owns_client = bleak_client is None
        self._pending: dict[int, asyncio.Future[Ret]] = {}
        self._paired = False
        self._started_notify = False

    async def __aenter__(self) -> "FingerBot":
        await self.connect()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.disconnect()

    def next_sn_ack(self) -> int:
        self.sn_ack += 1
        return self.sn_ack

    def reset_sn_ack(self) -> None:
        self.sn_ack = 0

    async def connect(self) -> None:
        if self.device is None:
            try:
                from bleak import BleakClient
            except ImportError as exc:  # pragma: no cover - exercised by runtime users
                raise RuntimeError(
                    "bleak is required. Install dependencies with "
                    "`python3 -m pip install -r requirements.txt`."
                ) from exc
            self.device = BleakClient(self.ble_device, timeout=self.response_timeout)

        if not getattr(self.device, "is_connected", False):
            await self.device.connect()

        if not self._started_notify:
            await self.device.start_notify(self.NOTIF_UUID, self.handle_notification)
            self._started_notify = True

        device_info = await self.send_request(self.device_info_request())
        if not isinstance(device_info.resp, DeviceInfoResp) or not device_info.resp.success:
            raise FingerBotProtocolError("Device info handshake failed")

        pair_ret = await self.send_request(self.pair_request())
        result = int(pair_ret.resp or 0)
        # Tuya BLE returns 2 when same client credentials are already paired.
        if result not in (0, 2):
            raise FingerBotPairingError(f"Pairing failed with Tuya result {result}")
        self._paired = True

    async def disconnect(self) -> None:
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

        if self.device is not None and getattr(self.device, "is_connected", False):
            if self._started_notify:
                try:
                    await self.device.stop_notify(self.NOTIF_UUID)
                except Exception:
                    _LOGGER.debug("stop_notify failed", exc_info=True)
            if self._owns_client:
                await self.device.disconnect()
        self._started_notify = False
        self._paired = False

    def handle_notification(self, handle: int, value: bytearray) -> None:
        try:
            ret = self.ble_receiver.parse_data_received(value)
        except Exception:
            _LOGGER.exception("Failed to parse notification")
            return
        if ret is None:
            return

        future = self._pending.pop(ret.response_to, None) if ret.response_to else None
        try:
            self._handle_ret(ret)
        except Exception as exc:
            if future and not future.done():
                future.set_exception(exc)
            else:
                _LOGGER.exception("Failed to handle notification")
            return

        if future and not future.done():
            future.set_result(ret)

    def _handle_ret(self, ret: Ret) -> None:
        if ret.code == Coder.FUN_SENDER_DEVICE_INFO:
            if not isinstance(ret.resp, DeviceInfoResp):
                raise FingerBotProtocolError("Missing device info response")
            self.secret_key_manager.setSrand(ret.resp.srand)
            self.protocol_version = ret.resp.protocol_major
            self.device_version = ret.resp.device_version
            self.protocol_version_str = ret.resp.protocol_version
            self.hardware_version = ret.resp.hardware_version
            _LOGGER.debug(
                "Device info: device=%s protocol=%s hardware=%s",
                self.device_version,
                self.protocol_version_str,
                self.hardware_version,
            )
        elif ret.code == Coder.FUN_RECEIVE_TIME1_REQ:
            asyncio.create_task(self._send_time1_response(ret.seq_num))
        elif ret.code == Coder.FUN_RECEIVE_TIME2_REQ:
            asyncio.create_task(self._send_time2_response(ret.seq_num))
        elif ret.code == Coder.FUN_RECEIVE_DP:
            asyncio.create_task(self._send_response(ret.code, b"", ret.seq_num))

    async def send_request(self, xrequest: XRequest, wait_for_response: bool = True) -> Ret:
        if self.device is None:
            raise FingerBotError("Device is not connected")

        future: asyncio.Future[Ret] | None = None
        if wait_for_response:
            future = asyncio.get_running_loop().create_future()
            self._pending[xrequest.sn_ack] = future

        for cmd in xrequest.pack():
            await self.device.write_gatt_char(self.CHAR_UUID, cmd, response=False)

        if future is None:
            return Ret(b"", self.protocol_version)

        try:
            return await asyncio.wait_for(future, self.response_timeout)
        except asyncio.TimeoutError as exc:
            self._pending.pop(xrequest.sn_ack, None)
            raise FingerBotTimeoutError(
                f"Timed out waiting for response to {xrequest.code.name}"
            ) from exc

    def _request(
        self,
        code: Coder,
        inp: bytes = b"",
        *,
        security_flag: int | None = None,
        response_to: int = 0,
    ) -> XRequest:
        if security_flag is None:
            security_flag = 4 if code == Coder.FUN_SENDER_DEVICE_INFO else 5
        secret_key = self.secret_key_manager.get(security_flag)
        sn_ack = self.next_sn_ack()
        return XRequest(
            sn_ack=sn_ack,
            ack_sn=response_to,
            code=code,
            security_flag=security_flag,
            secret_key=secret_key,
            iv=TuyaDataPacket.get_random_iv(),
            inp=inp,
            protocol_version=self.protocol_version,
        )

    def device_info_request(self) -> XRequest:
        return self._request(Coder.FUN_SENDER_DEVICE_INFO, b"", security_flag=4)

    def pair_request(self) -> XRequest:
        inp = bytearray()
        inp += self.uuid
        inp += self.login_key
        inp += self.dev_id
        while len(inp) < 44:
            inp += b"\x00"
        if len(inp) > 44:
            raise FingerBotProtocolError("Pairing payload is longer than 44 bytes")
        return self._request(Coder.FUN_SENDER_PAIR, bytes(inp), security_flag=5)

    def send_dps(
        self,
        dps: list[DataPoint | tuple[int | Enum, DpType, object]] | None = None,
    ) -> XRequest:
        if not dps:
            dps = self.profile.build_press_datapoints()

        raw = bytearray()
        for dp in dps:
            if isinstance(dp, DataPoint):
                raw += dp.encode()
                continue

            dp_id, dp_type, dp_value = dp
            if isinstance(dp_id, Enum):
                dp_id = int(dp_id.value)
            raw += DataPoint(int(dp_id), dp_type, dp_value).encode()

        return self._request(Coder.FUN_SENDER_DPS, bytes(raw), security_flag=5)

    async def press(
        self,
        *,
        down_position: int | None = None,
        up_position: int | None = None,
        hold_time: int | None = None,
        include_motion: bool = True,
    ) -> None:
        if not self._paired:
            await self.connect()

        profile = self.profile
        if (
            down_position is not None
            or up_position is not None
            or hold_time is not None
        ):
            profile = profile.with_motion(
                down_position=(
                    self.profile.down_position
                    if down_position is None
                    else down_position
                ),
                up_position=self.profile.up_position if up_position is None else up_position,
                hold_time=self.profile.hold_time if hold_time is None else hold_time,
            )

        request = self.send_dps(
            profile.build_press_datapoints(include_motion=include_motion)
        )
        await self.send_request(request)

    async def click(self, **kwargs: Any) -> None:
        await self.press(**kwargs)

    async def _send_response(self, code: Coder, data: bytes, response_to: int) -> None:
        request = self._request(code, data, security_flag=5, response_to=response_to)
        await self.send_request(request, wait_for_response=False)

    @staticmethod
    def _timezone_units() -> int:
        local_time = time.localtime()
        offset = (
            local_time.tm_gmtoff
            if hasattr(local_time, "tm_gmtoff")
            else -time.timezone
        )
        return int(offset / 36)

    async def _send_time1_response(self, response_to: int) -> None:
        timestamp_ms = int(time.time_ns() / 1_000_000)
        data = str(timestamp_ms).encode("ascii") + pack(">h", self._timezone_units())
        await self._send_response(Coder.FUN_RECEIVE_TIME1_REQ, data, response_to)

    async def _send_time2_response(self, response_to: int) -> None:
        now = time.localtime()
        data = pack(
            ">BBBBBBBh",
            now.tm_year % 100,
            now.tm_mon,
            now.tm_mday,
            now.tm_hour,
            now.tm_min,
            now.tm_sec,
            now.tm_wday,
            self._timezone_units(),
        )
        await self._send_response(Coder.FUN_RECEIVE_TIME2_REQ, data, response_to)
