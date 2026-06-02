# Control Tuya BLE Fingerbot locally

This repo controls Tuya/Adaprox BLE Fingerbot devices without a Bluetooth hub.
It was modernized from the old `pygatt` proof of concept to `bleak`, because
the old BlueZ `gatttool` path is brittle on current Home Assistant/Linux stacks.

## What this fixes

- Uses `bleak` instead of `pygatt`/`gatttool`.
- Uses the protocol version returned by the device info handshake instead of
  hard-coding protocol `2`.
- Answers Tuya BLE time requests during the session.
- Adds current Fingerbot datapoint profiles:
  - `classic`: `szjqr` Fingerbot/Fingerbot Plus, click DP `2`
  - `cubetouch`: CubeTouch 1s/II, click DP `1`
  - `kg`: newer Fingerbot Plus IDs like `mknd4lci` and `riecov42`, click DP `108`
  - `legacy`: original PoC behavior, click DP `101`

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Pair the Fingerbot in Tuya Smart or Smart Life first. Then extract `local_key`,
`uuid`, and `device_id` with the same method as before, for example
[tuya-local-key-extractor](https://github.com/redphx/tuya-local-key-extractor).
If you re-pair the device, extract the key again.

## Run once

```bash
python finger_me.py \
  --mac "AA:BB:CC:DD:EE:FF" \
  --local-key "xxxxxxxxxxxxxxxx" \
  --uuid "xxxxxxxxxxxxxxxx" \
  --device-id "xxxxxxxxxxxxxxxxxxxx" \
  --product-id "blliqpsj"
```

`--profile auto` is the default. If you know the device family, set it directly:

```bash
python finger_me.py --profile kg ...
python finger_me.py --profile cubetouch ...
python finger_me.py --profile classic ...
```

You can also use environment variables:

```bash
export FINGERBOT_MAC="AA:BB:CC:DD:EE:FF"
export FINGERBOT_LOCAL_KEY="xxxxxxxxxxxxxxxx"
export FINGERBOT_UUID="xxxxxxxxxxxxxxxx"
export FINGERBOT_DEVICE_ID="xxxxxxxxxxxxxxxxxxxx"
export FINGERBOT_PRODUCT_ID="riecov42"
python finger_me.py
```

## Home Assistant

Use the script as a short-lived `shell_command`. Home Assistant OS runs
`shell_command` inside the `homeassistant` container with `/config` as working
directory and stops commands after 60 seconds, so this script connects, presses,
and exits.

Example `configuration.yaml`:

```yaml
shell_command:
  press_fingerbot: >-
    /usr/local/bin/python3 /config/poc-tuya-ble-fingerbot/finger_me.py
    --mac "AA:BB:CC:DD:EE:FF"
    --local-key "xxxxxxxxxxxxxxxx"
    --uuid "xxxxxxxxxxxxxxxx"
    --device-id "xxxxxxxxxxxxxxxxxxxx"
    --product-id "riecov42"
```

Then call action `shell_command.press_fingerbot` from an automation or dashboard
button.

If the HA container does not have `bleak` or `pycryptodome`, install this repo in
a Python environment reachable from Home Assistant, or run it on a nearby host
and call it over SSH/MQTT. Bluetooth must be reachable from the process that runs
the script.

## References

- Original PoC/demo:
  <https://www.reddit.com/r/homeassistant/comments/uubh7h/poc_controlling_tuyaadaprox_fingerbot_plus/>
- Tuya BLE Home Assistant integration and supported Fingerbot products:
  <https://github.com/PlusPlus-ua/ha_tuya_ble>
- Current HA `shell_command` runtime behavior:
  <https://www.home-assistant.io/integrations/shell_command>
