"""
Patches automower_ble.protocol.BLEClient.connect() for this specific mower:

1. The mower is already bonded at the OS/BlueZ level (paired manually via
   `bluetoothctl pair` while the mower was in its BLE pairing mode - see
   project notes). Once bonded it stops advertising entirely, so it can no
   longer be found via BleakScanner, and bleak_retry_connector's
   establish_connection() (which has its own scan/verify logic) hangs
   against it. bluetoothctl's own `connect <addr>` works instantly against
   a bonded-but-not-advertising device, so we do the same thing here:
   connect directly via BleakClient, skipping establish_connection.

2. Since we're already bonded, there's no need to call client.pair() again.

This is otherwise a copy of automower_ble.protocol.BLEClient.connect()
(https://github.com/alistair23/AutoMower-BLE).
"""

import asyncio
import binascii
import logging

from automower_ble.protocol import BLEClient, Command, ResponseResult
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

logger = logging.getLogger(__name__)


async def connect_direct(self, device) -> ResponseResult:
    logger.info("connecting directly (already bonded, skipping discovery/pairing)...")

    # bleak's own D-Bus Connect() call times out against this bonded-but-
    # not-advertising mower, but `bluetoothctl connect <addr>` reliably
    # works (it does something extra internally, likely a background
    # passive scan alongside the connect). So shell out to it first, then
    # attach bleak to the now-already-connected device - bleak's Connect()
    # no-ops quickly once BlueZ already reports Connected=true.
    proc = await asyncio.create_subprocess_exec(
        "bluetoothctl", "connect", self.address,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await asyncio.wait_for(proc.communicate(), timeout=30.0)
    logger.info("bluetoothctl connect output: %s", out.decode(errors="replace").strip())
    if proc.returncode != 0:
        return ResponseResult.UNKNOWN_ERROR

    self.client = BleakClient(device)
    await self.client.connect(timeout=15.0)
    logger.info("connected")

    self.client._backend._mtu_size = self.MTU_SIZE  # type: ignore[attr-defined]

    for service in self.client.services:
        logger.info("[Service] %s", service)
        for char in service.characteristics:
            if char.uuid == "98bd0002-0b0e-421a-84e5-ddbf75dc6de4":
                self.write_char = char
            if char.uuid == "98bd0003-0b0e-421a-84e5-ddbf75dc6de4":
                self.read_char = char

    async def notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
        logger.info("Received: %s", str(binascii.hexlify(data)))
        await self.queue.put(data)

    logger.info("starting notify...")
    try:
        await self.client.start_notify(self.read_char, notification_handler)
    except Exception:
        await self.client.disconnect()
        raise
    logger.info("notify started")

    await asyncio.sleep(5.0)

    logger.info("sending setup_channel_id request...")
    request = self.generate_request_setup_channel_id()
    response = await self._request_response(request)
    logger.info("setup_channel_id response: %s", response)
    if response is None:
        return ResponseResult.UNKNOWN_ERROR

    logger.info("sending handshake request...")
    request = self.generate_request_handshake()
    response = await self._request_response(request)
    logger.info("handshake response: %s", response)
    if response is None:
        return ResponseResult.UNKNOWN_ERROR

    if self.pin is not None:
        logger.info("sending pin...")
        command = Command(self.channel_id, (await self.get_protocol())["EnterOperatorPin"])
        request = command.generate_request(code=self.pin)
        response = await self._request_response(request)
        logger.info("pin response: %s", response)
        if response is None:
            return ResponseResult.UNKNOWN_ERROR
        result = self.get_response_result(response)
        return ResponseResult.INVALID_PIN if result == ResponseResult.UNKNOWN_ERROR else result

    return ResponseResult.OK


def apply():
    BLEClient.connect = connect_direct
