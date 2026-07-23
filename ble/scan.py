"""
Adopted from the automower-ble project's ble_scanner.py example:
https://github.com/alistair23/AutoMower-BLE
"""

import argparse
import asyncio

from bleak import BleakScanner

# "Husqvarna AB" maps to "0x0426" for the manufacturer data
HUSQVARNA_COMPANY_IDENTIFIER = 0x0426


async def main(args: argparse.Namespace):
    print(f"Scanning for {args.timeout} seconds, please wait...")

    devices = await BleakScanner.discover(
        timeout=args.timeout,
        return_adv=True,
    )

    husqvarna_device_found = False
    for d, a in devices.values():
        if args.show_all or next(iter(a.manufacturer_data.keys()), None) == HUSQVARNA_COMPANY_IDENTIFIER:
            if not husqvarna_device_found and not args.show_all:
                print("Husqvarna/Gardena device(s) found!")
                husqvarna_device_found = True

            print(f"\n\tAddress: {d.address}")
            print(f"\tName: {d.name}")
            print(f"\tSignal Strength: {a.rssi} dBm (closer to 0 is stronger)")
            if args.show_all:
                print(f"\tManufacturer Data: {a.manufacturer_data}")

    if not husqvarna_device_found and not args.show_all:
        print("No Husqvarna/Gardena devices found!")
        print("Make sure your Sileno is powered on, nearby, and in BLE pairing mode.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Duration (seconds) to scan for BLE devices. Default = 15 seconds",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Scan and show all BLE devices found, not just Husqvarna/Gardena ones.",
    )
    args = parser.parse_args()
    asyncio.run(main(args))
