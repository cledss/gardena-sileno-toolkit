import os
import sys

from dotenv import load_dotenv

from gardena_client import GardenaClient, group_devices_by_id

load_dotenv()

client_id = os.environ.get("GARDENA_CLIENT_ID")
client_secret = os.environ.get("GARDENA_CLIENT_SECRET")

if not client_id or not client_secret:
    sys.exit("Set GARDENA_CLIENT_ID and GARDENA_CLIENT_SECRET in .env (see .env.example)")

client = GardenaClient(client_id, client_secret)
client.authenticate()
print("Authenticated OK")

locations = client.get_locations()
if not locations:
    sys.exit("No locations found on this Gardena account")

for location in locations:
    location_id = location["id"]
    location_name = location["attributes"]["name"]
    print(f"\nLocation: {location_name} ({location_id})")

    location_data = client.get_location(location_id)
    devices = group_devices_by_id(location_data)

    for device_id, services in devices.items():
        if "MOWER" not in services:
            continue
        common_attrs = services.get("COMMON", {}).get("attributes", {})
        mower_attrs = services["MOWER"]["attributes"]
        name = common_attrs.get("name", {}).get("value", device_id)
        battery = common_attrs.get("batteryLevel", {}).get("value")
        activity = mower_attrs.get("activity", {}).get("value")
        state = mower_attrs.get("state", {}).get("value")
        print(f"- {name}: activity={activity} state={state} battery={battery}%")
