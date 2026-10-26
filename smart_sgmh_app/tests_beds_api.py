"""Bed API authorization and validation tests. Run: python tests_beds_api.py"""
import os
os.environ.setdefault("STAFF_ID_CARD_REQUIRED","0")
import os
import tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "beds_api_test.db")

import app as A

client = A.app.test_client()
passed = failed = 0

def ck(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print("FAIL:", name, detail)

r = client.get("/api/v1/beds")
ck("public beds endpoint works", r.status_code == 200 and len(r.json.get("units", [])) == 7, r.status_code)
admin = client.post("/api/v1/login", json={"phone": "9000000000", "password": "admin123"})
ck("demo admin login works in isolated test DB", admin.status_code == 200, admin.status_code)
admin_token = admin.json["token"] if admin.status_code == 200 else ""
rec = client.post("/api/v1/login", json={"phone": "9000000010", "password": "rec123"})
rec_token = rec.json["token"] if rec.status_code == 200 else ""
r = client.post("/api/v1/beds/update", json={"unit": "General Ward", "total": 10, "occupied": 0, "unavailable": 0}, headers={"Authorization": "Bearer " + rec_token})
ck("non-admin cannot update beds", r.status_code == 403, r.status_code)
r = client.post("/api/v1/beds/update", json={"unit": "General Ward", "total": -1, "occupied": 0, "unavailable": 0}, headers={"Authorization": "Bearer " + admin_token})
ck("negative capacity rejected", r.status_code == 400, r.status_code)
r = client.post("/api/v1/beds/update", json={"unit": "General Ward", "total": 10, "occupied": 99, "unavailable": 0}, headers={"Authorization": "Bearer " + admin_token})
ck("mapped ward occupancy derived from admitted records", r.status_code == 200 and r.json.get("ok"), r.status_code)
unit = A.q("SELECT total_beds,occupied_beds FROM bed_inventory WHERE unit_name='General Ward'", one=True)
ck("mapped occupancy not taken from manually supplied value", unit["total_beds"] == 10 and unit["occupied_beds"] == 0, dict(unit))
print("PASS", passed, "FAIL", failed)
