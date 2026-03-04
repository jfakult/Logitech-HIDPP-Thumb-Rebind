#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PLIST_NAME="com.user.rebind_logitech_dpi_button"
PLIST_PATH="$SCRIPT_DIR/$PLIST_NAME.plist"

echo "=== Logitech HID++ Thumb Button Rebinder Setup ==="

# Create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists. Continuing..."
fi

# Activate and install dependencies
echo "Installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install -r "$SCRIPT_DIR/requirements.txt"

echo "Generating Launch Agent plist..."
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>

    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>$SCRIPT_DIR/rebind_logitech_dpi_button.py</string>
    </array>

    <key>EnvironmentVariables</key>
    <dict>
        <key>VIRTUAL_ENV</key>
        <string>$VENV_DIR</string>
        <key>PATH</key>
        <string>$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>/tmp/$PLIST_NAME.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/$PLIST_NAME.err</string>

    <key>ThrottleInterval</key>
    <integer>5</integer>
</dict>
</plist>
EOF

echo "Created: $PLIST_PATH"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To run manually:"
echo "  source $VENV_DIR/bin/activate"
echo "  python $SCRIPT_DIR/rebind_logitech_dpi_button.py"
echo ""
echo "To install as Launch Agent (auto-start at login):"
echo "  chmod u+x main.sh"
echo "  ./main.sh [start|stop]"
echo ""
echo "IMPORTANT: Grant Accessibility permissions to:"
echo "  System Settings > Privacy & Security > Accessibility"
echo "  Add: $VENV_DIR/bin/python"
