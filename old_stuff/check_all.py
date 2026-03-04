import hid

for d in hid.enumerate():
    if d['vendor_id'] == 1133 and d['product_id'] == 50475 and d.get('usage_page') == 65280:
        print("Trying interface:", d)
        dev = hid.device()
        dev.open_path(d['path'])
        dev.set_nonblocking(True)
        print("Listening...")
        for i in range(5):
            data = dev.read(64, 500)
            print("Report:", data)
        dev.close()
