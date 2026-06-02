import unittest

from pyfingerbot import (
    BleReceiver,
    DataPoint,
    DpType,
    PROFILE_CLASSIC,
    PROFILE_CUBETOUCH,
    PROFILE_KG,
    XRequest,
    get_profile,
)


class ProfileTests(unittest.TestCase):
    def test_auto_profile_by_product_id(self):
        self.assertEqual(get_profile("auto", "riecov42").name, "kg")
        self.assertEqual(get_profile("auto", "xhf790if").name, "cubetouch")
        self.assertEqual(get_profile("auto", "blliqpsj").name, "classic")
        self.assertEqual(get_profile("auto", None).name, "classic")

    def test_classic_press_datapoints(self):
        payload = b"".join(dp.encode() for dp in PROFILE_CLASSIC.build_press_datapoints())
        self.assertIn(DataPoint(8, DpType.ENUM, 0).encode(), payload)
        self.assertIn(DataPoint(2, DpType.BOOLEAN, True).encode(), payload)
        self.assertIn(DataPoint(9, DpType.INT, 80).encode(), payload)
        self.assertIn(DataPoint(15, DpType.INT, 0).encode(), payload)

    def test_kg_press_datapoints(self):
        payload = b"".join(dp.encode() for dp in PROFILE_KG.build_press_datapoints())
        self.assertIn(DataPoint(101, DpType.ENUM, 0).encode(), payload)
        self.assertIn(DataPoint(108, DpType.BOOLEAN, True).encode(), payload)
        self.assertIn(DataPoint(102, DpType.INT, 80).encode(), payload)
        self.assertIn(DataPoint(106, DpType.INT, 0).encode(), payload)

    def test_cubetouch_press_datapoints(self):
        payload = b"".join(dp.encode() for dp in PROFILE_CUBETOUCH.build_press_datapoints())
        self.assertIn(DataPoint(2, DpType.ENUM, 0).encode(), payload)
        self.assertIn(DataPoint(1, DpType.BOOLEAN, True).encode(), payload)
        self.assertIn(DataPoint(6, DpType.INT, 80).encode(), payload)
        self.assertIn(DataPoint(5, DpType.INT, 0).encode(), payload)


class PacketTests(unittest.TestCase):
    def test_varint_roundtrip(self):
        for value in (0, 1, 20, 127, 128, 255, 16384):
            encoded = XRequest.pack_int(value)
            decoded, pos = BleReceiver.unpack_int(encoded)
            self.assertEqual(decoded, value)
            self.assertEqual(pos, len(encoded))

    def test_split_packet_uses_protocol_version(self):
        packets = XRequest(
            sn_ack=1,
            ack_sn=0,
            code=__import__("pyfingerbot").Coder.FUN_SENDER_DPS,
            security_flag=5,
            secret_key=b"0" * 16,
            iv=b"1" * 16,
            inp=b"",
            protocol_version=3,
        ).split_packet(3, b"A" * 34)
        self.assertEqual(packets[0][2], 0x30)


if __name__ == "__main__":
    unittest.main()
