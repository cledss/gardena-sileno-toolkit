import argparse
import asyncio
import sys

import ble_patch

ble_patch.apply()

from automower_ble.mower import Mower
from automower_ble.protocol import ResponseResult
from bleak.backends.device import BLEDevice

# Arbitrary but fixed channel id for this integration (matches upstream example).
CHANNEL_ID = 1197489078

MAX_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 3.0


def bluez_object_path(adapter: str, address: str) -> str:
    return f"/org/bluez/{adapter}/dev_{address.upper().replace(':', '_')}"


async def reset_link(address: str):
    """
    Clear any stuck BlueZ connection state before retrying. This mower's BLE
    link is unreliable enough (a known trait of this hardware/firmware, not
    something fixable client-side - see ble/README.md) that a stale
    half-open connection from a failed attempt can block the next one.
    """
    proc = await asyncio.create_subprocess_exec(
        "bluetoothctl", "disconnect", address,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


async def read_status(mower: Mower):
    name = await mower.command("GetUserMowerNameAsAsciiString")
    manufacturer = await mower.get_manufacturer()
    model = await mower.get_model()
    battery = await mower.battery_level()
    charging = await mower.is_charging()
    state = await mower.mower_state()
    activity = await mower.mower_activity()
    next_start = await mower.mower_next_start_time()

    print(f"\nName: {name}")
    print(f"Manufacturer: {manufacturer}")
    print(f"Model: {model}")
    print(f"Battery: {battery}%")
    print(f"Charging: {charging}")
    print(f"State: {state.name if state else 'unknown'}")
    print(f"Activity: {activity.name if activity else 'unknown'}")
    if next_start:
        print(f"Next start: {next_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    else:
        print("Next start: none scheduled")


async def try_once(address: str, pin: int | None):
    mower = Mower(CHANNEL_ID, address, pin)
    # The name here is just a label for bleak/BlueZ logging - it doesn't need
    # to match the mower's real name, which command() below fetches anyway.
    device = BLEDevice(address, "Sileno", {"path": bluez_object_path("hci0", address)})

    result = await mower.connect(device)
    if result != ResponseResult.OK:
        raise RuntimeError(f"connect() returned {result}")

    try:
        await read_status(mower)
    finally:
        try:
            await mower.disconnect()
        except Exception:
            pass


async def main(address: str, pin: int | None):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"Connecting (attempt {attempt}/{MAX_ATTEMPTS})...")
        try:
            await try_once(address, pin)
            return
        except Exception as exc:
            print(f"Attempt {attempt} failed: {exc!r}")
            if attempt == MAX_ATTEMPTS:
                sys.exit(f"Giving up after {MAX_ATTEMPTS} attempts.")
            await reset_link(address)
            await asyncio.sleep(RETRY_DELAY_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--address", required=True, help="Bluetooth address of the mower")
    parser.add_argument("--pin", type=int, default=None, help="Operator PIN, if required")
    args = parser.parse_args()

    asyncio.run(main(args.address, args.pin))
