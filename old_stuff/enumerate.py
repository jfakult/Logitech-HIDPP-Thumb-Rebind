import hid
import json

for d in hid.enumerate():
    if d['vendor_id']==0x046D:
        print(d)
