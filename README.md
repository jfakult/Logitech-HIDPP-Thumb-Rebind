# Logitech HID++ Thumb Button Rebinder (for Mac)

Capture and rebind the "Resolution Switch" thumb button on Logitech MX Vertical mice using the HID++ protocol. Works with mice connected via the **Unifying USB receiver** on macOS.

---

## Why This Exists

Logitech Options+ software may be banned or you just might not want to install it.

The MX Vertical's thumb button ("Resolution Switch") cycles DPI settings by default. It emits a Logitech-proprietary HID++ event instead of a standard HID button press, so macOS and tools like Karabiner don't recognize it as a button.

This script enables HID++ "diversion" — telling the mouse firmware to send thumb button events to the host instead of handling them internally — then listens for those events and triggers custom actions.

**No Logitech software required.**

---

## Default Bindings

| Input                  | Action              |
|------------------------|---------------------|
| Thumb button           | ⌘W  (close tab)      |
| ⌘ + thumb button       | ⌘T  (new tab)        |
| ⌘ + ⇧ + thumb button   | ⌘⇧T (restore tab)    |

Users can modify the on_thumb_button_press() function to change the bindings.

---

## Requirements

- **macOS** Ventura 13+ or Sonoma 14+
- **Logitech MX Vertical** via **Unifying USB receiver** (not Bluetooth)
- **Python 3.9+**

> ⚠️ Bluetooth is not supported—macOS doesn't expose raw HID access over Bluetooth.
> ⚠️ Not tested on other Logitech mice but the same principles should apply.

---

## Project Files

```
logitech-hidpp-rebind/
├── README.md
├── requirements.txt
├── setup.sh
├── rebind_logitech_dpi_button.py
└── com.user.rebind_logitech_dpi_button.plist (auto-generated)
```

---

## Installation

### 1. Download the Project

```bash
mkdir -p ~/logitech-hidpp-rebind
cd ~/logitech-hidpp-rebind
git clone https://github.com/jfakult/Logitech-HIDPP-Thumb-Rebind.git
```

### 2. Run Setup

```bash
chmod +x setup.sh
./setup.sh
```

This creates a Python virtual environment and installs:
- `hidapi` — HID device communication
- `pyobjc-framework-Quartz` — Modifier key detection

Then it builds the plist file for the Launch Agent.

### 3. Grant Accessibility Permissions

The script sends keystrokes via AppleScript, which requires Accessibility access:

1. When you run the script and hit the thumb button, you'll be prompted to grant permissions to `venv/bin/python3` (and/or Terminal if you run it from there).

> Without this permission, keystrokes will silently fail.

---

## Usage

### Run Manually

```bash
cd ~/logitech-hidpp-rebind
source venv/bin/activate
python rebind_logitech_dpi_button.py
```

Output:
```
=== Logitech HID++ Thumb Button Rebinder ===

Found HID++ interface: DevSrvsID:4295003619
Special Keys feature at index: 10
Diversion enabled for Resolution Switch

Listening for thumb button events... (Ctrl+C to quit)

  Thumb press       → Command+W
  Command + thumb   → Command+T
  Command + shift + thumb   → Command+Shift+T
  ...
```

Press **Ctrl+C** to stop. Diversion is automatically disabled on exit.

### Auto-Start at Login

1. Run `./main.sh start`

2. **Install the Launch Agent:**
   ```bash
   chmod u+x main.sh
   ./main.sh start
   ```

3. **Check logs:**
   ```bash
   tail -f /tmp/rebind_logitech_dpi_button.log
   ```

4. **To stop:**
   ```bash
   ./main.sh stop
   ```

---

## How It Works

### The Problem

Standard mouse buttons send HID reports that macOS understands. But Logitech's Resolution Switch button sends a **proprietary HID++ event** that only Logitech software recognizes. macOS, Karabiner, and other tools never see it.

### The Solution: HID++ Diversion

Logitech's HID++ protocol includes a "Special Keys" feature that lets software **divert** button events. Instead of the mouse firmware handling the button internally, it sends the event to the host computer.

Here's what the script does:

1. **Finds the Unifying receiver's HID++ interface** — a vendor-specific USB endpoint
2. **Queries the mouse for its "Special Keys" feature** — this lists all reprogrammable buttons
3. **Enables diversion for the Resolution Switch button** — the mouse will now send events to us
4. **Listens for button events** — when pressed, we receive a notification with the button ID
5. **Triggers actions** — sends keystrokes via AppleScript
6. **Cleans up on exit** — disables diversion so the button returns to normal

### Why Not Karabiner (or BTT, etc)?

Karabiner intercepts HID events at the driver level. Software-injected keystrokes (CGEventPost, AppleScript, etc.) happen *after* this point, so Karabiner never sees them. There's no way to make Karabiner recognize the thumb button—we have to perform actions directly in Python.

---

## Customization

### Change Key Bindings

Edit `on_thumb_button_press()` in the script:

```python
def on_thumb_button_press():
    if is_command_held():
        send_keystroke("t", ["command down"])  # ⌘T
    else:
        send_keystroke("w", ["command down"])  # ⌘W
```

### Run Shell Commands Instead

```python
def on_thumb_button_press():
    if is_command_held():
        subprocess.run(["open", "-a", "Safari"])
    else:
        subprocess.run(["open", "-a", "Finder"])
```

### Keystroke Syntax

```python
# Single modifier
send_keystroke("w", ["command down"])

# Multiple modifiers
send_keystroke("z", ["command down", "shift down"])  # ⌘⇧Z (redo)

# Special keys via key code
subprocess.run(["osascript", "-e",
    'tell application "System Events" to key code 53'])  # Escape
```

---

## Troubleshooting

### Keystrokes Not Sent

Run the script manually and press the thumb button. If you don't see any output, the script is not receiving events. (see commands above to run manually)

1. **Grant Accessibility permissions** to both `venv/bin/python3` and Terminal

2. **Test AppleScript manually:**
   ```bash
   osascript -e 'tell application "System Events" to keystroke "a"'
   ```
   If this fails, permissions are missing.

### Script Works, Launch Agent Doesn't

- Verify paths in the plist are absolute
- Check errors: `cat /tmp/rebind_logitech_dpi_button.err`
- Ensure the venv Python binary has Accessibility permissions

### Events Stop After Sleep

macOS may reset USB devices after sleep. The Launch Agent's `KeepAlive` setting restarts the script automatically.

### PEP 668 / "Externally Managed Environment" Error

Don't install packages to system Python. Use the virtual environment:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### It's not working => I have Multiple Paired Devices

If multiple devices are paired to the receiver, edit `DEVICE_INDEX`:
```python
DEVICE_INDEX = 0x01  # First device
DEVICE_INDEX = 0x02  # Second device
```

### I have a Logi Bolt receiver

Change UNIFYING_PID in the rebind_logitech_dpi_button.py:

``` python
UNIFYING_PID = 0xC52B
BOLT_PID = 0xC548
```

---

## Uninstalling

```bash
# Stop the Launch Agent
./main.sh stop
```

---

## References

- [Logitech HID++ 2.0 Specification](https://lekensteyn.nl/files/logitech/logitech_hidpp_2.0_specification_draft_2012-06-04.pdf)
- [hidapi Python package](https://pypi.org/project/hidapi/)

---

## License

MIT — do whatever you want.
