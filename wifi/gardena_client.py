import json

import requests

AUTH_HOST = "https://api.authentication.husqvarnagroup.dev"
SMART_HOST = "https://api.smart.gardena.dev"


class GardenaClient:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None

    def authenticate(self):
        resp = requests.post(
            f"{AUTH_HOST}/v1/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=10,
        )
        resp.raise_for_status()
        self.access_token = resp.json()["access_token"]

    def _headers(self, json_content=False):
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Authorization-Provider": "husqvarna",
            "X-Api-Key": self.client_id,
        }
        if json_content:
            headers["Content-Type"] = "application/vnd.api+json"
        return headers

    def get_locations(self):
        resp = requests.get(f"{SMART_HOST}/v2/locations", headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()["data"]

    def get_location(self, location_id):
        resp = requests.get(f"{SMART_HOST}/v2/locations/{location_id}", headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_websocket_url(self, location_id):
        body = {
            "data": {
                "type": "WEBSOCKET",
                "attributes": {"locationId": location_id},
                "id": "does-not-matter",
            }
        }
        resp = requests.post(
            f"{SMART_HOST}/v2/websocket",
            headers=self._headers(json_content=True),
            data=json.dumps(body),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["data"]["attributes"]["url"]


def group_devices_by_id(location_response):
    """Group the JSON:API 'included' service objects by device id.

    Each physical device shows up as several service objects (COMMON, MOWER, ...)
    whose ids share a "<device_id>:<service>" prefix.
    """
    devices = {}
    for item in location_response.get("included", []):
        device_id = item["id"].split(":")[0]
        devices.setdefault(device_id, {})[item["type"]] = item
    return devices
