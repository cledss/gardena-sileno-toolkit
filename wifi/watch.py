import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import requests
import websockets
from dotenv import load_dotenv

from gardena_client import GardenaClient

load_dotenv()

client_id = os.environ.get("GARDENA_CLIENT_ID")
client_secret = os.environ.get("GARDENA_CLIENT_SECRET")

if not client_id or not client_secret:
    sys.exit("Set GARDENA_CLIENT_ID and GARDENA_CLIENT_SECRET in .env (see .env.example)")

SUPPORTED_SERVICES = {"COMMON", "VALVE", "VALVE_SET", "SENSOR", "MOWER", "POWER_SOCKET", "DEVICE"}

devices = {}  # device_id -> {service_type: attributes}


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def print_mower_status(device_id):
    services = devices.get(device_id, {})
    if "MOWER" not in services:
        return
    common = services.get("COMMON", {})
    mower = services["MOWER"]
    name = common.get("name", {}).get("value", device_id)
    battery = common.get("batteryLevel", {}).get("value")
    activity = mower.get("activity", {}).get("value")
    state = mower.get("state", {}).get("value")
    log(f"{name}: activity={activity} state={state} battery={battery}%")


def handle_message(raw):
    data = json.loads(raw)
    msg_type = data.get("type")
    if msg_type not in SUPPORTED_SERVICES:
        return
    device_id = data["id"].split(":")[0]
    devices.setdefault(device_id, {})[msg_type] = data.get("attributes", {})
    print_mower_status(device_id)


def get_ws_url(client, location_id):
    try:
        return client.get_websocket_url(location_id)
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 401:
            log("Token expired, re-authenticating...")
            client.authenticate()
            return client.get_websocket_url(location_id)
        raise


async def watch(client, location_id):
    delay = 5
    while True:
        try:
            ws_url = get_ws_url(client, location_id)
            log("Connecting to websocket...")
            async with websockets.connect(ws_url, ping_interval=150, ping_timeout=60) as ws:
                log("Connected. Waiting for updates...")
                delay = 5
                async for message in ws:
                    handle_message(message)
        except (websockets.exceptions.ConnectionClosed, OSError) as exc:
            log(f"Websocket disconnected ({exc!r}), reconnecting in {delay}s...")
        except Exception as exc:
            log(f"Unexpected error ({exc!r}), reconnecting in {delay}s...")
        await asyncio.sleep(delay)
        delay = min(delay * 2, 60)


def main():
    client = GardenaClient(client_id, client_secret)
    client.authenticate()
    log("Authenticated OK")

    locations = client.get_locations()
    if not locations:
        sys.exit("No locations found on this Gardena account")

    location_id = locations[0]["id"]
    location_name = locations[0]["attributes"]["name"]
    log(f"Location: {location_name} ({location_id})")

    asyncio.run(watch(client, location_id))


if __name__ == "__main__":
    main()
