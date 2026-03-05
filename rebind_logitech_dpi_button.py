#!/usr/bin/env python3
"""
HID++ thumb button -> Direct actions via osascript
"""
import subprocess
import time

import hid
from Quartz import (
    CGEventSourceCreate,
    CGEventSourceFlagsState,
    kCGEventFlagMaskAlternate,  # ⌥
    kCGEventFlagMaskCommand,  # ⌘
    kCGEventFlagMaskControl,  # ⌃
    kCGEventFlagMaskShift,  # ⇧
    kCGEventSourceStateHIDSystemState,
)

LOGITECH_VID = 0x046D

UNIFYING_RECIEVER_PID = 0xC52B
BOLT_PID = 0xC52B

UNIFYING_PID = UNIFYING_RECIEVER_PID # Change to BOLT_PID to use a BOLT
DEVICE_INDEX = 0x01                   # Change to 0x02 if not working and you have more than 1 device connected to your USB receiver

HIDPP_LONG_REPORT = 0x11

CONTROL_IDS = {
    0x0050: "Left Click",
    0x0051: "Right Click",
    0x0052: "Middle Click",
    0x0053: "Back",
    0x0056: "Forward",
    0x00C3: "Gesture Button",
    0x00C4: "Smart Shift",
    0x00D7: "Thumb Wheel",
    0x00FD: "Resolution Switch",
}


# Update this!
def on_thumb_button_press():
    """Handle thumb button press"""
    cmd = is_command_held()
    shift = is_shift_held()
    option = is_option_held()
    control = is_control_held()

    if cmd and shift:
        # Shift + Thumb = Command+Shift+T (restore tab)
        print("  -> Action: Command+Shift+T (restore tab)")
        send_keystroke("t", ["command down", "shift down"])
    elif shift:
        pass
    elif cmd:
        # Command + Thumb = Command+T (new tab)
        print("  -> Action: Command+T (new tab)")
        send_keystroke("t", ["command down"])
    else:
        # Thumb alone = Command+W (close tab)
        print("  -> Action: Command+W (close tab)")
        send_keystroke("w", ["command down"])


# ---- don't update this :) ----

def is_command_held():
    """Check if Command key is currently held down"""
    flags = CGEventSourceFlagsState(kCGEventSourceStateHIDSystemState)
    return bool(flags & kCGEventFlagMaskCommand)


def is_shift_held():
    """Check if Shift key is currently held down"""
    flags = CGEventSourceFlagsState(kCGEventSourceStateHIDSystemState)
    return bool(flags & kCGEventFlagMaskShift)


def is_option_held():
    """Check if Option key is currently held down"""
    flags = CGEventSourceFlagsState(kCGEventSourceStateHIDSystemState)
    return bool(flags & kCGEventFlagMaskAlternate)


def is_control_held():
    """Check if Control key is currently held down"""
    flags = CGEventSourceFlagsState(kCGEventSourceStateHIDSystemState)
    return bool(flags & kCGEventFlagMaskControl)


def send_keystroke(key, modifiers):
    """Send keystroke via AppleScript. Fails silently if permissions missing."""
    mod_str = ", ".join(modifiers) if modifiers else ""
    script = (
        f'tell application "System Events" to keystroke "{key}" using {{{mod_str}}}'
    )
    #print(script)
    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, timeout=5
        )
        if result.returncode != 0:
            print(f"[WARN] Keystroke failed: {result.stderr.decode().strip()}")
    except Exception as e:
        print(f"[WARN] Keystroke error: {e}")


### HID++ stuff ###

def find_hidpp_interface():
    """ Figure out which HID++ device interface to use

        0xFF00 , 0x0002 = Logitech Unifying Receiver
    """
    for dev in hid.enumerate(LOGITECH_VID, UNIFYING_PID):
        if dev["usage_page"] == 0xFF00 and dev["usage"] == 0x0002:
            return dev["path"]
    return None


def send_hidpp(device, device_idx, feature_idx, func_id, *args):
    """
        Send HID++ command to device
        Used to enable/disable diversion for a specific control
    """
    data = [HIDPP_LONG_REPORT, device_idx, feature_idx, (func_id << 4) | 0x0A] + list(
        args
    )
    data += [0] * (20 - len(data))
    device.write(data)
    for _ in range(10):
        response = device.read(20, timeout_ms=500)
        if response:
            if response[2] == feature_idx:
                return response
            print(f"  (async event: {[hex(b) for b in response]})")
    return None


def get_feature_index(device, feature_id):
    """ Get HID++ feature index for a given feature ID

        Example feature ID: 0x1B04 = Special Keys
    """
    hi = (feature_id >> 8) & 0xFF
    lo = feature_id & 0xFF
    response = send_hidpp(device, DEVICE_INDEX, 0x00, 0x00, hi, lo)
    if response and response[2] == 0x00:
        return response[4]
    return None


def main():
    path = find_hidpp_interface()
    if not path:
        print("Could not find HID++ interface!")
        return

    print(f"Opening: {path}")
    dev = hid.device()
    dev.open_path(path)
    dev.set_nonblocking(False)

    # === Find Special Keys feature (0x1B04) ===
    print("\n=== Finding Special Keys feature (0x1B04) ===")
    special_keys_idx = get_feature_index(dev, 0x1B04)

    if special_keys_idx is None or special_keys_idx == 0:
        print("Special Keys feature not found!")
        dev.close()
        return

    print(f"Special Keys feature at index: {special_keys_idx}")

    # === Get count of controls associated with Special Keys ===
    print("\n=== Querying reprogrammable controls ===")
    response = send_hidpp(dev, DEVICE_INDEX, special_keys_idx, 0x00)
    if not response:
        print("Failed to get control count")
        dev.close()
        return

    control_count = response[4]
    print(f"Number of controls: {control_count}")

    # === List all controls, see if we can find the thumb button ===
    res_switch_idx = None
    res_switch_cid = None

    for i in range(control_count):
        response = send_hidpp(dev, DEVICE_INDEX, special_keys_idx, 0x01, i)
        if response:
            cid = (response[4] << 8) | response[5]
            flags = response[8]

            name = CONTROL_IDS.get(cid, f"Unknown (0x{cid:04X})")
            divertable = "divertable" if (flags & 0x01) else ""

            print(f"  [{i}] CID: 0x{cid:04X} ({name}) flags: {flags:02X} {divertable}")

            # Match thumb button by CID, see printout when command runs for more. One could also match by name
            """
            Number of controls: 7
            [0] CID: 0x0050 (Left Click) flags: 11 divertable
            [1] CID: 0x0051 (Right Click) flags: 11 divertable
            [2] CID: 0x0052 (Middle Click) flags: 71 divertable
            [3] CID: 0x0053 (Back) flags: 71 divertable
            [4] CID: 0x0056 (Forward) flags: 71 divertable
            [5] CID: 0x00FD (Resolution Switch) flags: 71 divertable
            [6] CID: 0x00D7 (Thumb Wheel) flags: A0
            """
            if cid == 0x00FD:
                res_switch_idx = i
                res_switch_cid = cid

    if res_switch_cid is None:
        print("\nResolution Switch (0x00FD) not found!")
        dev.close()
        return

    # === Enable diversion for Resolution Switch ===
    # (This is the cool part)
    # AKA: Tell the logitech mouse to send events when the button is pressed
    # Normally it supresses them until Options+ connects to it and sends it this command
    print(
        f"\n=== Enabling diversion for control index {res_switch_idx} (CID 0x{res_switch_cid:04X}) ==="
    )

    cid_hi = (res_switch_cid >> 8) & 0xFF
    cid_lo = res_switch_cid & 0xFF
    response = send_hidpp(
        dev,
        DEVICE_INDEX,
        special_keys_idx,
        0x03,
        cid_hi,
        cid_lo,
        0x03,
        0x00,
        0x00,
        0x00,
    )

    if response:
        print("Diversion enabled!")
    else:
        print("Failed to enable diversion")

    # === Listen for diverted button events ===
    print("\n=== Listening for thumb button events ===")
    print("Actions:")
    print("  - Thumb button alone    -> Command+W (close tab)")
    print("  - Command + Thumb button -> Command+T (new tab)")
    print("  - Command + Shift + Thumb button -> Command+Shift+T (restore tab)")
    print("(Ctrl+C to stop)")

    dev.set_nonblocking(True)
    last_state = False

    try:
        while True:
            try:
                data = dev.read(64, timeout_ms=5000)
                if not data:
                    continue

                print(f"EVENT: {[hex(b) for b in data]}")

                if data[2] == special_keys_idx:
                    cid = (data[4] << 8) | data[5]
                    if cid == 0x00FD:
                        name = CONTROL_IDS.get(cid, "Unknown")
                        print(f"  -> {name} (0x{cid:04X}) PRESSED")
                        on_thumb_button_press()
                    elif cid == 0x0000:
                        print(f"  -> Button RELEASED")
                    else:
                        name = CONTROL_IDS.get(cid, "Unknown")
                        print(f"  -> {name} (0x{cid:04X})")

            except Exception as e:
                print(f"[ERROR] Device read failed: {e}")
                print("Reconnecting in 5 seconds...")
                time.sleep(5)
                # Re-open device
                dev.close()
                path = find_hidpp_interface()
                if path:
                    dev.open_path(path)
                    enable_diversion(
                        dev, special_keys_index, RESOLUTION_SWITCH_CID, enable=True
                    )
                    print("Reconnected!")
                else:
                    print("Device not found, retrying...")
    except KeyboardInterrupt:
        print("Exiting...")

    # === Disable diversion (cleanup) ===
    print("\n=== Disabling diversion ===")
    dev.set_nonblocking(False)
    send_hidpp(
        dev,
        DEVICE_INDEX,
        special_keys_idx,
        0x03,
        cid_hi,
        cid_lo,
        0x02,
        0x00,
        0x00,
        0x00,
    )

    dev.close()
    print("Done.")


if __name__ == "__main__":
    main()
