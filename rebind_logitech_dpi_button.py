#!/usr/bin/env python3
"""HID++ thumb button -> Direct actions via Quartz CGEvents"""

import time

import hid
from keyboard import send_keystroke
from Quartz import (
    CGEventSourceFlagsState,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskShift,
    kCGEventSourceStateHIDSystemState,
)


# Update this!
def on_thumb_button_press():
    """Handle thumb button press"""
    cmd = _is_modifier_held(kCGEventFlagMaskCommand)
    shift = _is_modifier_held(kCGEventFlagMaskShift)
    control = _is_modifier_held(kCGEventFlagMaskControl)

    if cmd and shift:
        print("  -> Action: Command+Shift+T (restore tab)")
        send_keystroke("t", ["command down", "shift down"])
    elif control and shift:
        print("  -> Action: Paste")
        send_keystroke("v", ["command down"])
    elif control:
        print("  -> Action: Copy")
        send_keystroke("c", ["command down"])
    elif shift:
        pass
    elif cmd:
        print("  -> Action: Command+T (new tab)")
        send_keystroke("t", ["command down"])
    else:
        print("  -> Action: Command+W (close tab)")
        send_keystroke("w", ["command down"])


# ============================================================================
# Configuration
# ============================================================================

LOGITECH_VID = 0x046D
UNIFYING_RECEIVER_PID = 0xC52B
BOLT_PID = 0xC52B

RECEIVER_PID = UNIFYING_RECEIVER_PID  # Change to BOLT_PID for Bolt receiver
DEVICE_INDEX = 0x01  # Change to 0x02 if you have multiple devices on receiver

HIDPP_SHORT_REPORT = 0x10
HIDPP_LONG_REPORT = 0x11
SPECIAL_KEYS_FEATURE_ID = 0x1B04
TARGET_CONTROL_CID = 0x00FD  # Resolution Switch (thumb button)

# HID++ 1.0 notification register (for device connect/disconnect events)
HIDPP_REGISTER_NOTIF_DISCONNECT = 0x41
HIDPP_DEVICE_CONNECTION = 0x04

RECONNECT_MAX_ATTEMPTS = int(1e6)
RECONNECT_MAX_WAIT_SECONDS = 10

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


###################################
# ---- don't update below here ----
###################################


# ============================================================================
# Modifier key helpers
# ============================================================================


def _is_modifier_held(mask):
    """Check if a modifier key is currently held down."""
    flags = CGEventSourceFlagsState(kCGEventSourceStateHIDSystemState)
    return bool(flags & mask)


# ============================================================================
# HID++ Protocol
# ============================================================================


def find_hidpp_interface():
    """Find the HID++ long-message interface path.

    Returns the device path for usage_page=0xFF00, usage=0x0002 (Logitech HID++).
    """
    for dev in hid.enumerate(LOGITECH_VID, RECEIVER_PID):
        if dev["usage_page"] == 0xFF00 and dev["usage"] == 0x0002:
            return dev["path"]
    return None


def send_hidpp(device, device_idx, feature_idx, func_id, *args):
    """Send an HID++ command and wait for the matching response."""
    data = [HIDPP_LONG_REPORT, device_idx, feature_idx, (func_id << 4) | 0x0A]
    data += list(args)
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
    """Query the feature index for a given HID++ feature ID."""
    hi, lo = (feature_id >> 8) & 0xFF, feature_id & 0xFF
    response = send_hidpp(device, DEVICE_INDEX, 0x00, 0x00, hi, lo)
    if response and response[2] == 0x00:
        return response[4]
    return None


def set_diversion(device, feature_idx, cid, enabled):
    """Enable or disable diversion for a control ID."""
    cid_hi, cid_lo = (cid >> 8) & 0xFF, cid & 0xFF
    divert_flags = 0x03 if enabled else 0x02
    return send_hidpp(
        device,
        DEVICE_INDEX,
        feature_idx,
        0x03,
        cid_hi,
        cid_lo,
        divert_flags,
        0x00,
        0x00,
        0x00,
    )


# ============================================================================
# Connection management
# ============================================================================


def safe_close(device):
    """Safely close a HID device, ignoring errors."""
    try:
        device.close()
    except Exception:
        pass


def connect_device():
    """Open and initialize the HID++ device.

    Returns:
        tuple: (device, special_keys_feature_index) on success
        None: if connection or initialization fails
    """
    path = find_hidpp_interface()
    if not path:
        return None

    try:
        dev = hid.device()
        dev.open_path(path)
        dev.set_nonblocking(False)

        feature_idx = get_feature_index(dev, SPECIAL_KEYS_FEATURE_ID)
        if feature_idx is None or feature_idx == 0:
            dev.close()
            return None

        return dev, feature_idx
    except Exception as e:
        print(f"Connection error: {e}")
        return None


def reconnect_with_backoff(old_feature_idx):
    """Attempt to reconnect with exponential backoff.

    Args:
        old_feature_idx: Previous feature index for comparison logging

    Returns:
        tuple: (device, feature_index) on success
        None: if all reconnection attempts fail
    """
    for attempt in range(RECONNECT_MAX_ATTEMPTS):
        wait_time = min(2**attempt, RECONNECT_MAX_WAIT_SECONDS)
        print(
            f"Reconnecting in {wait_time}s (attempt {attempt + 1}/{RECONNECT_MAX_ATTEMPTS})..."
        )
        time.sleep(wait_time)

        result = connect_device()
        if not result:
            print("  Device not found, waiting...")
            continue

        dev, feature_idx = result

        if feature_idx != old_feature_idx:
            print(f"  Feature index changed: {old_feature_idx} -> {feature_idx}")

        if set_diversion(dev, feature_idx, TARGET_CONTROL_CID, enabled=True):
            print("Reconnected and diversion re-enabled!")
            dev.set_nonblocking(True)
            return dev, feature_idx

        print("  Failed to re-enable diversion, retrying...")
        safe_close(dev)

    return None


# ============================================================================
# Device discovery
# ============================================================================


def find_target_control(device, feature_idx):
    """Find and list all controls, returning the target control if found.

    Returns:
        int: Control ID if found, None otherwise
    """
    response = send_hidpp(device, DEVICE_INDEX, feature_idx, 0x00)
    if not response:
        print("Failed to get control count")
        return None

    control_count = response[4]
    print(f"Number of controls: {control_count}")

    # === List all controls, see if we can find the thumb button ===
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
    target_cid = None
    for i in range(control_count):
        response = send_hidpp(device, DEVICE_INDEX, feature_idx, 0x01, i)
        if not response:
            continue

        cid = (response[4] << 8) | response[5]
        flags = response[8]
        name = CONTROL_IDS.get(cid, f"Unknown (0x{cid:04X})")
        divertable = "divertable" if (flags & 0x01) else ""
        print(f"  [{i}] CID: 0x{cid:04X} ({name}) flags: {flags:02X} {divertable}")

        if cid == TARGET_CONTROL_CID:
            target_cid = cid

    return target_cid


# ============================================================================
# Main event loop
# ============================================================================


def main():
    result = connect_device()
    if not result:
        print("Could not find HID++ interface!")
        return

    dev, special_keys_idx = result

    print("\n=== Finding Special Keys feature (0x1B04) ===")
    print(f"Special Keys feature at index: {special_keys_idx}")

    print("\n=== Querying reprogrammable controls ===")
    target_cid = find_target_control(dev, special_keys_idx)

    if target_cid is None:
        print(f"\nTarget control (0x{TARGET_CONTROL_CID:04X}) not found!")
        dev.close()
        return

    # === Enable diversion for Resolution Switch ===
    # (This is the cool part)
    # AKA: Tell the logitech mouse to send events when the button is pressed
    # Normally it supresses them until Options+ connects to it and sends it this command
    print(f"\n=== Enabling diversion for CID 0x{target_cid:04X} ===")
    if set_diversion(dev, special_keys_idx, target_cid, enabled=True):
        print("Diversion enabled!")
    else:
        print("Failed to enable diversion")

    print("\n=== Listening for thumb button events ===")
    print("Actions:")
    print("  - Thumb button alone    -> Command+W (close tab)")
    print("  - Command + Thumb       -> Command+T (new tab)")
    print("  - Command + Shift + Thumb -> Command+Shift+T (restore tab)")
    print("(Ctrl+C to stop)")

    dev.set_nonblocking(True)

    try:
        while True:
            try:
                data = dev.read(64, timeout_ms=5000)
                if not data:
                    continue

                print(f"EVENT: {[hex(b) for b in data]}")

                # Check for device disconnect/connect notification (HID++ 1.0)
                # 0x10 = short HID++ message, 0x41 = wireless device connection register
                if (
                    len(data) >= 7
                    and data[0] == HIDPP_SHORT_REPORT
                    and data[2] == HIDPP_REGISTER_NOTIF_DISCONNECT
                ):
                    # Byte 3 = wireless PID low, Byte 4 = flags
                    # For device connection: flag bit 6 indicates link status
                    # We'll trigger reconnect on ANY 0x41 event to be safe
                    print("  -> Device disconnect/connect event detected!")
                    raise ConnectionResetError("Device state changed")

                # Check for device arrival notification (HID++ 2.0 long message)
                # 0x11 = long HID++ message, 0x04 = device connection feature
                if (
                    len(data) >= 7
                    and data[0] == HIDPP_LONG_REPORT
                    and data[2] == HIDPP_DEVICE_CONNECTION
                ):
                    print("  -> Device connection event detected!")
                    raise ConnectionResetError("Device reconnected")

                if data[2] == special_keys_idx:
                    cid = (data[4] << 8) | data[5]
                    name = CONTROL_IDS.get(cid, "Unknown")

                    if cid == TARGET_CONTROL_CID:
                        print(f"  -> {name} (0x{cid:04X}) PRESSED")
                        on_thumb_button_press()
                    elif cid == 0x0000:
                        print("  -> Button RELEASED")
                    else:
                        print(f"  -> {name} (0x{cid:04X})")

            except (ConnectionResetError, Exception) as e:
                if isinstance(e, ConnectionResetError):
                    print(f"[INFO] {e} - initiating reconnect...")
                else:
                    print(f"[ERROR] Device read failed: {e}")
                safe_close(dev)

                result = reconnect_with_backoff(special_keys_idx)
                if result:
                    dev, special_keys_idx = result
                else:
                    print("Failed to reconnect. Exiting.")
                    return

    except KeyboardInterrupt:
        print("Exiting...")

    print("\n=== Disabling diversion ===")
    dev.set_nonblocking(False)
    set_diversion(dev, special_keys_idx, TARGET_CONTROL_CID, enabled=False)
    dev.close()
    print("Done.")


if __name__ == "__main__":
    main()
