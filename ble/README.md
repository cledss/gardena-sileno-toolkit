# ble/ - Bluetooth-only Sileno

Gardena sells some Sileno models with **Bluetooth only** - no WiFi, no app
cloud connectivity, no GARDENA Smart System API access at all. The only
official way to talk to them is the Gardena app over BLE, direct.

This directory does the same thing from a Raspberry Pi (or any Linux box
with BlueZ), using [automower-ble](https://github.com/alistair23/AutoMower-BLE)
- the same reverse-engineered protocol library used for real Husqvarna
Automowers, since Gardena and Husqvarna share the underlying platform.

## The actual problem, if you're stuck here

If you've gotten this far you've probably already hit this: you can find
the mower in a BLE scan, but every connection attempt fails during
`start_notify()` or with `Bonded: no` and a GATT error, no matter what you
try. An HCI trace (`btmon`) shows the real cause plainly:

```
ATT: Write Request - Client Characteristic Configuration
> ATT: Error Response - Insufficient Authentication
< SMP: Pairing Request (whatever IO capability you configured)
> SMP: Pairing Failed - Reason: Pairing not supported
```

The mower's notification characteristic requires an encrypted/bonded link,
and it **flatly refuses any new BLE pairing request** from an unrecognized
central - regardless of IO capability (`NoInputNoOutput`, `DisplayYesNo`,
`KeyboardOnly` with a static PIN file) or Legacy vs. Secure Connections
pairing. We confirmed this with `btmon` across all of those combinations;
none of them are the fix. If you're searching for your specific error and
landed here: this is very likely it, and tweaking pairing parameters on
your end will not solve it.

**What actually fixes it**: these mowers don't have a generic repeatable
"pairing mode" - they're normally bonded once, to whichever phone paired
them during physical setup, and refuse everyone else forever. Removing the
mower from your GARDENA *account* in the app does **not** help - that's a
cloud-side unlink, unrelated to the Bluetooth bond, which lives only in the
mower's own Bluetooth chip.

What worked for us: there was a separate option (distinct from removing the
mower from the account) that put the mower into a genuine fresh
BLE-pairing-accepting state. Once that was active, a plain

```
bluetoothctl pair <mower-mac-address>
```

succeeded immediately. Exactly where that option lives may vary by model/
app version - look for anything Bluetooth-specific (not just "remove
device"/"remove from account") in the mower's own settings or the app's
device management screen, and try pairing again right after using it.

## Once it's bonded: a second gotcha

After a successful bond, the mower **stops BLE-advertising entirely**. That
means:

- `bleak`'s `BleakScanner` can no longer find it (it's not advertising), so
  the usual scan-then-connect flow breaks.
- `bleak_retry_connector`'s `establish_connection()` (which `automower_ble`
  uses internally) hangs or raises `BleakDeviceNotFoundError` against it.
- Plain `bluetoothctl connect <addr>` still works, though - it appears to
  do something extra internally (likely a background passive scan) that
  bleak's own D-Bus `Connect()` call doesn't replicate.

`ble_patch.py` works around this by monkeypatching
`automower_ble.protocol.BLEClient.connect()` to:

1. Shell out to `bluetoothctl connect <addr>` first.
2. Attach a `bleak.BleakClient` built from a hand-constructed `BLEDevice`
   (with the D-Bus object path derived directly from the address, since the
   device isn't in bleak's own discovery cache) - this connects near-
   instantly once step 1 has already connected it at the BlueZ level.
3. Skip `client.pair()` entirely, since we're already bonded.

The mower's BLE radio also appears to go idle/dormant after a period, and a
cold connection attempt to a dormant mower will time out even via
`bluetoothctl connect` directly. Waking it (e.g. briefly opening the
Gardena app, or whatever else brings the mower's screen/radio to life)
before running these scripts fixes that.

## Setup

```bash
cd ble
python3 -m venv .venv
.venv/bin/pip install automower-ble bleak

# make sure the Bluetooth adapter is actually up - some Pis ship with it
# soft-rfkilled/down by default:
sudo hciconfig hci0 up   # if this fails with "RF-kill", first:
#   echo 0 | sudo tee /sys/class/rfkill/rfkill0/soft
```

Find your mower's address:

```bash
.venv/bin/python scan.py
```

Pair it (mower must be in its fresh-pairing state - see above):

```bash
bluetoothctl pair <mower-mac-address>
```

Read status:

```bash
.venv/bin/python status.py --address <mower-mac-address> --pin <your-pin>
```

`--pin` is the mower's operator PIN (used for the app-layer
`EnterOperatorPin` protocol command, separate from BLE pairing).

## Known limitations

- Not yet packaged as a persistent service - each run does a fresh
  `bluetoothctl connect`. Should work fine wrapped in a loop/systemd
  service the same way as `wifi/watch.py`, just not done here yet.
- The mower needs to be BLE-reachable (not dormant) when you run this.
- Only tested against a Sileno; other Bluetooth-only Gardena/Husqvarna
  models may behave differently.
