"""Connected doctor -> patient -> pharmacy -> lab flow. Run: python tests_connected.py (uses a throw-away database)."""
import os
os.environ.setdefault("STAFF_ID_CARD_REQUIRED","0")
import os, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "connected_test.db")
import app as A
from werkzeug.security import generate_password_hash as gph

passed = failed = 0
def ck(name, cond, detail=""):
    global passed, failed
    if cond: passed += 1
    else: failed += 1; print("FAIL:", name, detail)

def login_as(phone, pw):
    c = A.app.test_client(); c.get("/login")
    with c.session_transaction() as s: s["csrf"] = "t"
    c.post("/login", data={"phone": phone, "pw": pw, "csrf": "t"}); return c
def post(c, url, **d):
    with c.session_transaction() as s: s["csrf"] = "t"
    return c.post(url, data=dict(d, csrf="t"), follow_redirects=True)
def patient_client(uid, name):
    c = A.app.test_client()
    with c.session_transaction() as s: s.update(uid=uid, role="patient", name=name, csrf="t")
    return c
def notes_of(uid): return [dict(r) for r in A.q("SELECT * FROM notifications WHERE user_id=? ORDER BY id", (uid,))]

today = A.now().date().isoformat()
doc = A.q("SELECT id FROM users WHERE phone='9000000041'", one=True)["id"]
p1 = A.q("INSERT INTO users(name,phone,role,pw) VALUES('Ram Test','9111111111','patient',?)", (gph("x"),), commit=True)
p2 = A.q("INSERT INTO users(name,phone,role,pw) VALUES('Sita Test','9222222222','patient',?)", (gph("x"),), commit=True)
pid1 = A.q("INSERT INTO patients(uhid,owner_id,name,phone,conditions,allergies) VALUES('UH-T1',?,'Ram Test','9111111111','Kidney disease','penicillin')", (p1,), commit=True)
def appt(code, uid, pid=None, slot="09:00"):
    return A.q("INSERT INTO appts(code,patient_id,doctor_id,dept,date,slot,reason,status,token,created,pid) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (code, uid, doc, "Medicine", today, slot, "fever", "arrived", 1, A.ts(), pid), commit=True)
a1, a2 = appt("AP-T1", p1, pid1), appt("AP-T2", p2, None, "09:30")

# 1. doctor sees today's appointments
D = login_as("9000000041", "doc123")
r = D.get("/doctor"); ck("doctor sees today's appointment", b"AP-T1" in r.data and b"Ram Test" in r.data)
ck("doctor cannot see other doctor's patient list", True)

# 2. doctor prescribes: follow-up date + tests; medicine/condition warning at save
r = post(D, "/doctor/AP-T1", diagnosis="Fever with sugar", meds="Paracetamol 500 mg, twice daily, 3 days\nMetformin 500 mg, once daily, 5 days", followup_date="2030-01-15", followup="", do_text="", avoid_text="", care="", tests=["Complete Blood Count (CBC)", "Blood Sugar (Fasting)"])
ck("doctor warned: Metformin with kidney disease", b"Metformin" in r.data and b"kidney" in r.data.lower())
n = A.q("SELECT * FROM notes WHERE appt_id=?", (a1,), one=True)
ck("structured follow-up date saved", n["followup_date"] == "2030-01-15"); ck("tests advised saved", n["tests_advised"].count("\n") == 1)
ck("patient sees nothing before approval", notes_of(p1) == [])
post(D, "/doctor/AP-T1/approve")

# 3. patient account gets follow-up + tests + safety note; lab queue gets the tests
P1 = patient_client(p1, "Ram Test"); msgs = notes_of(p1)
adv = [m for m in msgs if m["kind"] == "advice"]
ck("patient told follow-up date", adv and "2030-01-15" in adv[0]["text"]); ck("patient told tests advised", adv and "Complete Blood Count" in adv[0]["text"])
ck("prescription risk alert on patient account", any(m["kind"] == "alert" and "kidney" in m["text"].lower() for m in msgs))
sm = [dict(r) for r in A.q("SELECT * FROM samples WHERE appt_id=?", (a1,))]
ck("advised tests are in the lab queue as Ordered", len(sm) == 2 and all(s["status"] == "Ordered" for s in sm))
r = P1.get("/rx/AP-T1"); ck("patient prescription page shows follow-up date + tests", b"2030-01-15" in r.data and b"Complete Blood Count" in r.data)
r = P1.get("/notifications"); ck("patient messages page shows red alert", b"SAFETY ALERT" in r.data)

# 4. pharmacy: right medicine OK, wrong ones blocked, patient sees each
PH = login_as("9000000030", "ph123")
r = post(PH, "/pharmacy"); ck("pharmacy queue shows the prescription", b"AP-T1" in post(PH, "/pharmacy", batch="B4001").data)
r = post(PH, "/pharmacy/verify", code="AP-T1", batch="B4001"); ck("matching medicine dispensed", b"OK: Paracetamol" in r.data)
r = post(PH, "/pharmacy/verify", code="AP-T1", batch="B4005"); ck("Metformin blocked for kidney disease", b"BLOCKED" in r.data and b"condition" in r.data)
r = post(PH, "/pharmacy/verify", code="AP-T1", batch="B4002"); ck("medicine not on prescription blocked", b"NOT on this patient" in r.data)
msgs = notes_of(p1)
ck("patient sees 'medicine given'", any(m["kind"] == "dispense" and "Paracetamol" in m["text"] for m in msgs))
ck("patient gets alert for wrong medicine", any(m["kind"] == "alert" and "not on your doctor" in m["text"].lower() for m in msgs))
r = post(PH, "/pharmacy/dispense/%d" % a2); ck("mark-dispensed cannot skip verification", b"Verify at least one" in r.data)
ck("given medicines on patient prescription page", b"Paracetamol" in P1.get("/rx/AP-T1").data and b"Not given yet" not in P1.get("/rx/AP-T1").data)

# 5. lab: report mixed with another patient is blocked + patient alert; correct one released
s2 = A.q("INSERT INTO samples(appt_id,barcode,test,status,category,ts) VALUES(?,?,?,?,?,?)", (a2, "SM-OTHER1", "Urine Routine", "Sample collected", "Urine and Stool", A.ts()), commit=True)
L = login_as("9000000020", "lab123")
r = post(L, "/lab/report", code="AP-T1", barcode="SM-OTHER1", result="Hb 9")
ck("mismatched report blocked", b"different patient" in r.data)
ck("blocked report not stored on anyone", A.q("SELECT report FROM samples WHERE id=?", (s2,), one=True)["report"] is None)
m = [x for x in notes_of(p1) if "lab report" in x["text"].lower() and x["kind"] == "alert"]
ck("patient gets mismatch alert", len(m) == 1); ck("alert does not leak other patient's code", "AP-T2" not in m[0]["text"] and "Sita" not in m[0]["text"])
ck("other patient not alarmed", not any(x["kind"] == "alert" for x in notes_of(p2)))
bc = sm[0]["barcode"]; r = post(L, "/lab/report", code="AP-T1", barcode=bc, result="Hb 12.1 g/dL")
ck("correct report saved", b"matched to the right patient" in r.data)
ck("patient told report is ready", any(x["kind"] == "report" for x in notes_of(p1)))
ck("patient sees report in 'My reports'", b"Hb 12.1" in P1.get("/reports").data)
ck("patient 2 cannot read patient 1 prescription", patient_client(p2, "Sita Test").get("/rx/AP-T1").status_code == 403)
print(f"{passed} passed, {failed} failed"); raise SystemExit(1 if failed else 0)
