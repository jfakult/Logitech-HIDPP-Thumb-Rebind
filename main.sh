#!/bin/bash

# Generate usage:
# if start, copy over the plist file and start the service
# if stop, stop the service

# Help menu if -h or no args
if [ "$1" = "-h" ] || [ "$1" = "--help" ] || [ "$#" -eq 0 ]; then
    echo "Usage: $0 [-h] [-s] [-k]"
    echo "  -h, --help    Show this help message and exit"
    echo "  start   Start the service"
    echo "  stop    Kill the service"
    exit 0
fi

PLIST_NAME="com.user.rebind_logitech_dpi_button"
PLIST_PATH="$PLIST_NAME".plist

if [ "$1" = "start" ]; then
    echo "--- Copying over the plist file"
    cp $PLIST_PATH ~/Library/LaunchAgents/

    echo -e "\n--- Verifying the plist file" && \
    plutil ~/Library/LaunchAgents/$PLIST_PATH && \
    echo -e "\n--- Starting the service" && \
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/$PLIST_PATH

    echo -e "\n--- Verifying the service" && \
    launchctl print gui/$(id -u)/$PLIST_NAME
elif [ "$1" = "stop" ]; then
    echo "Stopping the service" && \
    launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/$PLIST_PATH

    echo "Done"
fi
