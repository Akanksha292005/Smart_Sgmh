"""IPD admission desk, bed capacity and discharge. Patients no longer request admission themselves (doctor referral / emergency only), so the requests here are created the way a doctor referral creates them. Run: python tests_ipd.py"""
import os
os.environ.setdefault("STAFF_ID_CARD_REQUIRED","0")
import os, re, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
import app as A
app = A.app; P = F = 0
def ck(n, c, x=""):
    global P, F
    if c: P += 1
    else: F += 1; print("FAIL:", n, x)
def client(phone, pw):
    c = app.test_client(); u = A.q("SELECT * FROM users WHERE phone=?", (phone,), one=True)
    with c.session_transaction() as s:
        s["csrf"] = "t"; s["lang"] = "en"
        if u["role"] == "patient": s.update(uid=u["id"], role="patient", name=u["name"], dept=None)
    if u["role"] != "patient": assert c.post("/login", data=dict(phone=phone, pw=pw, csrf="t")).status_code == 302
    with c.session_transaction() as s: s["csrf"] = "t"; s["lang"] = "en"
    return c
def loc(r): return r.headers.get("Location", "")
ATT = dict(att_name="Ramesh Kumar", att_phone="9876543210", att_rel="Father", consent="1")
BASE = dict(type="Planned", reason="surgery advised", dept="Medicine", ward="General ward", doctor="auto", csrf="t")

A.q("UPDATE ward_duty SET shift='All day'", commit=True)  # the test must not depend on the time of day it runs (duty is shift-aware)
def mkreq(pid, owner, ward="General ward", code=None):
    c = code or A.code("IP-")
    A.q("INSERT INTO appts(code,patient_id,doctor_id,dept,date,slot,reason,created,kind,ward,pid,src,adm_type,att_name,att_phone,att_rel,prio,prio_why) VALUES(?,?,?,'Medicine',?,'24x7','surgery advised',?,'IPD',?,?,'referral','Planned','Ramesh Kumar','9876543210','Father',1,'Senior citizen')",
        (c, owner, 6, A.now().date().isoformat(), A.ts(), ward, pid), commit=True); return c

# patients cannot ask for admission any more
A.q("INSERT INTO users(name,phone,role,pw) VALUES('New Pat','9111111111','patient','x')", commit=True)
new = client("9111111111", "x")
r = new.get("/admit"); ck("new patient: /admit goes to the IPD info page", r.status_code == 302 and loc(r).endswith("/ipd"), loc(r))
r = new.post("/admit", data={**BASE, **ATT}); ck("posting an admission request creates nothing", loc(r).endswith("/ipd") and A.q("SELECT COUNT(*) n FROM appts WHERE kind='IPD'", one=True)["n"] == 0)
pat = client("9000000001", "pat123")
html = pat.get("/ipd").get_data(as_text=True)
ck("IPD page explains the doctor / emergency route", "Doctor admits" in html and "Emergency" in html and 'href="/admit' not in html)
pat.post("/patients/new", data=dict(csrf="t", relation="Mother", name="Sita Devi", gender="Female", age_years="62", village_ward="Ward 5", district="Rewa", consent="1", phone="9222222222"))
fam = A.q("SELECT * FROM patients WHERE name='Sita Devi'", one=True); ck("family member exists", bool(fam))
pat.post("/patients/new", data=dict(csrf="t", relation="Brother", name="Mohan Lal", gender="Male", age_years="30", village_ward="Ward 2", district="Rewa", consent="1", phone="9333333333"))
m = A.q("SELECT * FROM patients WHERE name='Mohan Lal'", one=True)
owner = A.q("SELECT id FROM users WHERE phone='9000000001'", one=True)["id"]
code = mkreq(fam["id"], owner)
pg = pat.get("/appt/" + code).get_data(as_text=True)
ck("patient sees the request page with attendant + IPD bring list", "Ramesh Kumar" in pg and "attendant" in pg.lower() and "Sita Devi" in pg)
rec = client("9000000010", "rec123")
ck("reception list shows attendant", "Ramesh Kumar" in rec.get("/reception").get_data(as_text=True))
# Configure a tiny test capacity so occupancy synchronization and full-ward guard are exercised.
A.q("UPDATE bed_inventory SET total_beds=1,occupied_beds=0,unavailable_beds=0,updated_at=?,updated_by='test' WHERE unit_name='General Ward'", (A.ts(),), commit=True)
rec.post("/reception/admit/" + code, data=dict(csrf="t", bed="G-1")); ck("no admit without ID check", A.q("SELECT status FROM appts WHERE code=?", (code,), one=True)["status"] == "booked")
rec.post("/reception/admit/" + code, data=dict(csrf="t", bed="G-1", id_ok="1")); ck("admit with ID check", A.q("SELECT status,bed FROM appts WHERE code=?", (code,), one=True)["bed"] == "G-1")
ck("admission increments General Ward occupancy", A.q("SELECT occupied_beds FROM bed_inventory WHERE unit_name='General Ward'", one=True)["occupied_beds"] == 1)
ck("care team filled automatically on admission", A.q("SELECT duty_doctor,nurse FROM careteam WHERE appt_id=(SELECT id FROM appts WHERE code=?)", (code,), one=True)["nurse"] != "")
# patient can cancel an admission request that is still waiting
c2 = mkreq(m["id"], owner)
pat.post("/cancel/" + c2, data=dict(csrf="t")); ck("IPD request can be cancelled", A.q("SELECT status FROM appts WHERE code=?", (c2,), one=True)["status"] == "cancelled")
# A second admission cannot exceed configured capacity; discharge frees the slot again.
c3 = mkreq(m["id"], owner)
rec.post("/reception/admit/" + c3, data=dict(csrf="t", bed="G-2", id_ok="1"))
ck("full mapped ward blocks additional admission", A.q("SELECT status FROM appts WHERE code=?", (c3,), one=True)["status"] == "booked")
rec.post("/reception/discharge/" + code, data=dict(csrf="t"))
ck("discharge frees General Ward occupancy", A.q("SELECT occupied_beds FROM bed_inventory WHERE unit_name='General Ward'", one=True)["occupied_beds"] == 0)
rec.post("/reception/admit/" + c3, data=dict(csrf="t", bed="G-2", id_ok="1"))
ck("admission succeeds after capacity is freed", A.q("SELECT status FROM appts WHERE code=?", (c3,), one=True)["status"] == "admitted")
ck("second admission occupancy synced", A.q("SELECT occupied_beds FROM bed_inventory WHERE unit_name='General Ward'", one=True)["occupied_beds"] == 1)
# Hindi pages render
hi = client("9000000001", "pat123")
with hi.session_transaction() as s: s["lang"] = "hi"
ck("Hindi IPD page ok", hi.get("/ipd").status_code == 200 and "भर्ती कैसे होती है" in hi.get("/ipd").get_data(as_text=True))
print("PASS", P, "FAIL", F)
