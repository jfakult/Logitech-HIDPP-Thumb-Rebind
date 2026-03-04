import hid

devinfo = next(
    d for d in hid.enumerate()
    if d["vendor_id"] == 1133
    and d["product_id"] == 50475
    and d.get("usage_page") == 65280
    and d.get("interface_number") == 2
)



try:
    dev = hid.device()
    dev.open_path(devinfo["path"])
except Exception as e:
    print("Failed to open device:", e)
    exit(1)

print("Listening for HID++ reports. Press Ctrl+C to exit.")
try:
    while True:
        report = dev.read(64, timeout_ms=500)
        if report:
            print("Report:", report)
except KeyboardInterrupt:
    print("\nExiting.")
finally:
    dev.close()
