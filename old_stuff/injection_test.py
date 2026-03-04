#!/usr/bin/env python3
"""Test key injection"""
import time

from Quartz import CGEventCreateKeyboardEvent, CGEventPost, kCGHIDEventTap

KEYCODE_F13 = 0x7

print("Injecting F13 in 2 seconds... watch Karabiner EventViewer")
time.sleep(2)

# Key down
event = CGEventCreateKeyboardEvent(None, KEYCODE_F13, True)
CGEventPost(kCGHIDEventTap, event)

time.sleep(0.05)

# Key up
event = CGEventCreateKeyboardEvent(None, KEYCODE_F13, False)
CGEventPost(kCGHIDEventTap, event)

print("Done!")
