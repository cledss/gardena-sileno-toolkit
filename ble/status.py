import argparse
import asyncio

import ble_patch

ble_patch.apply()

from automower_ble.mower import Mower
from bleak.backends.device import BLEDevice

# Arbitrary but fixed channel id for this integration (matches upstream example).
CHANNEL_ID = 1197489078


def bluez_object_path(adapter: str, address: str) -> str:
    return f"/org/bluez/{adapter}/dev_{address.upper().replace(':', '_')}"


async def main(address: str, pin: int | None):
    mower = Mower(CHANNEL_ID, address, pin)
    # The name here is just a label for bleak/BlueZ logging - it doesn't need
    # to match the mower's real name, which command() below fetches anyway.
    device = BLEDevice(address, "Sileno", {"path": bluez_object_path("hci0", address)})

    print("Connecting...")
    result = await mower.connect(device)
    print(f"connect() result: {result}")

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

    await mower.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--address", required=True, help="Bluetooth address of the mower")
    parser.add_argument("--pin", type=int, default=None, help="Operator PIN, if required")
    args = parser.parse_args()

    asyncio.run(main(args.address, args.pin))
