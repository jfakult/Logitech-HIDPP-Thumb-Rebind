"""Keyboard utilities for sending keystrokes via Quartz CGEvents.

Handles keyboard layout translation to find the correct keycode for any character.
"""

import ctypes
from ctypes import byref, c_uint16, c_uint32, c_uint8, c_void_p, POINTER

from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    CGEventSourceCreate,
    CGEventSourceFlagsState,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskShift,
    kCGEventSourceStateHIDSystemState,
    kCGEventSourceStatePrivate,
    kCGHIDEventTap,
)

# Layout-independent special keys
SPECIAL_KEYS = {
    "space": 0x31,
    "return": 0x24,
    "tab": 0x30,
    "delete": 0x33,
    "escape": 0x35,
    "left": 0x7B,
    "right": 0x7C,
    "down": 0x7D,
    "up": 0x7E,
}

_carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
_cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")


def _get_keycode_for_char(char):
    """Get the keycode that produces this character on the current keyboard layout."""
    if char.lower() in SPECIAL_KEYS:
        return SPECIAL_KEYS[char.lower()]

    _carbon.TISCopyCurrentKeyboardLayoutInputSource.restype = c_void_p
    _carbon.TISGetInputSourceProperty.argtypes = [c_void_p, c_void_p]
    _carbon.TISGetInputSourceProperty.restype = c_void_p
    _carbon.LMGetKbdType.restype = c_uint8
    _cf.CFDataGetBytePtr.argtypes = [c_void_p]
    _cf.CFDataGetBytePtr.restype = c_void_p
    _carbon.UCKeyTranslate.argtypes = [
        c_void_p,
        c_uint16,
        c_uint16,
        c_uint32,
        c_uint32,
        c_uint32,
        POINTER(c_uint32),
        c_uint32,
        POINTER(c_uint32),
        ctypes.c_wchar * 4,
    ]
    _carbon.UCKeyTranslate.restype = c_uint32

    source = _carbon.TISCopyCurrentKeyboardLayoutInputSource()
    layout_data = _carbon.TISGetInputSourceProperty(
        source, c_void_p.in_dll(_carbon, "kTISPropertyUnicodeKeyLayoutData")
    )
    layout = _cf.CFDataGetBytePtr(layout_data)
    kbd_type = _carbon.LMGetKbdType()

    for keycode in range(128):
        dead_key = c_uint32(0)
        length = c_uint32(0)
        output = (ctypes.c_wchar * 4)()
        _carbon.UCKeyTranslate(
            layout,
            keycode,
            0,
            0,
            kbd_type,
            1,
            byref(dead_key),
            4,
            byref(length),
            output,
        )
        if length.value > 0 and output[0].lower() == char.lower():
            return keycode

    print(f"[WARN] No keycode found for '{char}'")
    return None


# Modifier keycodes and their corresponding flag masks
MODIFIER_INFO = {
    "command": (55, kCGEventFlagMaskCommand),
    "shift": (56, kCGEventFlagMaskShift),
    "option": (58, kCGEventFlagMaskAlternate),
    "control": (59, kCGEventFlagMaskControl),
}


def send_keystroke(key, modifiers):
    """Send keystroke via Quartz CGEvents.

    Smart modifier handling:
    - If a modifier is physically held, we just send the key with flags (no synthetic modifier events)
    - If a modifier is NOT physically held, we send synthetic modifier down/up events

    This avoids fighting with physically held keys while still properly cleaning up
    synthetic modifier state.

    Args:
        key: Single character or key name (e.g., "v", "t", "return")
        modifiers: List of modifier strings like ["command down", "shift down"]
    """
    key_code = _get_keycode_for_char(key)
    if key_code is None:
        return

    # Get current physical modifier state
    physical_flags = CGEventSourceFlagsState(kCGEventSourceStateHIDSystemState)

    # Parse which modifiers we want
    wanted_mods = set()
    flags = 0
    for mod in modifiers:
        mod_lower = mod.lower()
        if "command" in mod_lower:
            wanted_mods.add("command")
            flags |= kCGEventFlagMaskCommand
        if "shift" in mod_lower:
            wanted_mods.add("shift")
            flags |= kCGEventFlagMaskShift
        if "option" in mod_lower or "alternate" in mod_lower:
            wanted_mods.add("option")
            flags |= kCGEventFlagMaskAlternate
        if "control" in mod_lower:
            wanted_mods.add("control")
            flags |= kCGEventFlagMaskControl

    # Determine which modifiers we need to synthesize (not physically held)
    synthetic_mods = []
    for mod_name in wanted_mods:
        keycode, mask = MODIFIER_INFO[mod_name]
        if not (physical_flags & mask):
            synthetic_mods.append(mod_name)

    source = CGEventSourceCreate(kCGEventSourceStatePrivate)

    # Press only the modifiers that aren't physically held
    for mod_name in synthetic_mods:
        keycode, _ = MODIFIER_INFO[mod_name]
        mod_down = CGEventCreateKeyboardEvent(source, keycode, True)
        CGEventPost(kCGHIDEventTap, mod_down)

    # Press and release the main key (with flags so apps recognize the combo)
    key_down = CGEventCreateKeyboardEvent(source, key_code, True)
    key_up = CGEventCreateKeyboardEvent(source, key_code, False)
    CGEventSetFlags(key_down, flags)
    CGEventSetFlags(key_up, flags)
    CGEventPost(kCGHIDEventTap, key_down)
    CGEventPost(kCGHIDEventTap, key_up)

    # Release only the modifiers we synthetically pressed
    for mod_name in reversed(synthetic_mods):
        keycode, _ = MODIFIER_INFO[mod_name]
        mod_up = CGEventCreateKeyboardEvent(source, keycode, False)
        CGEventPost(kCGHIDEventTap, mod_up)
