from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from pyfingerbot import FingerBot, PROFILES


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Press a Tuya/Adaprox BLE Fingerbot locally."
    )
    result.add_argument("--mac", default=env("FINGERBOT_MAC"), help="BLE MAC address")
    result.add_argument("--local-key", default=env("FINGERBOT_LOCAL_KEY"), help="Tuya local key")
    result.add_argument("--uuid", default=env("FINGERBOT_UUID"), help="Tuya UUID")
    result.add_argument("--device-id", default=env("FINGERBOT_DEVICE_ID"), help="Tuya device ID")
    result.add_argument("--product-id", default=env("FINGERBOT_PRODUCT_ID"), help="Tuya product ID")
    result.add_argument(
        "--profile",
        default=env("FINGERBOT_PROFILE", "auto"),
        choices=("auto", *PROFILES.keys()),
        help="DP profile. Use product-id with auto when available.",
    )
    result.add_argument("--down-position", type=int, default=None)
    result.add_argument("--up-position", type=int, default=None)
    result.add_argument("--hold-time", type=int, default=None)
    result.add_argument(
        "--no-motion-config",
        action="store_true",
        help="Send only mode + click datapoints, skip position/hold settings.",
    )
    result.add_argument("--timeout", type=float, default=float(env("FINGERBOT_TIMEOUT", "12")))
    result.add_argument("--debug", action="store_true")
    return result


async def amain() -> None:
    args = parser().parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    missing = [
        name
        for name, value in {
            "--mac/FINGERBOT_MAC": args.mac,
            "--local-key/FINGERBOT_LOCAL_KEY": args.local_key,
            "--uuid/FINGERBOT_UUID": args.uuid,
            "--device-id/FINGERBOT_DEVICE_ID": args.device_id,
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit("Missing required values: " + ", ".join(missing))

    async with FingerBot(
        args.mac,
        args.local_key,
        args.uuid,
        args.device_id,
        product_id=args.product_id or None,
        profile=args.profile,
        response_timeout=args.timeout,
    ) as fingerbot:
        await fingerbot.press(
            down_position=args.down_position,
            up_position=args.up_position,
            hold_time=args.hold_time,
            include_motion=not args.no_motion_config,
        )
        print(
            "pressed "
            f"profile={fingerbot.profile.name} "
            f"protocol={fingerbot.protocol_version_str or fingerbot.protocol_version}"
        )


def main() -> int:
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
