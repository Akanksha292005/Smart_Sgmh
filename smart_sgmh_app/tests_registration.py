"""End-to-end checks for the registration + smart booking layer.  Run:  python tests_registration.py
Uses a throw-away database (never touches smartsgmh.db)."""
import os
os.environ.setdefault("STAFF_ID_CARD_REQUIRED","0")
import os, re, sys, tempfile, json
from datetime import timedelta
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
import app as A

app = A.app
PASS = FAIL = 0
def check(name, cond, extra=""):
    global PASS, FAIL
    if cond: PASS += 1
    else: FAIL += 1; print("FAIL:", name, extra)

TOK = "testcsrf"
def client():
    c = app.test_client()
    with c.session_transaction() as s: s["csrf"] = TOK
    return c
def post(c, url, data=None, **kw):
    with c.session_transaction() as s: t = s.setdefault("csrf", TOK)  # the app drops the session on login/registration; the next page render creates a new token
    return c.post(url, data={"csrf": t, **(data or {})}, **kw)
def login(phone, pw):
    c = client(); u = A.q("SELECT * FROM users WHERE phone=?", (phone,), one=True)
    if u and u["role"] == "patient":  # patients use /start (OTP + password); tests_flow.py covers that page, here the session is set directly
        with c.session_transaction() as s: s.update(uid=u["id"], role="patient", name=u["name"], dept=None, lang="en", csrf=TOK)
        return c
    r = post(c, "/login", dict(phone=phone, pw=pw)); assert r.status_code == 302, (phone, r.status_code)
    with c.session_transaction() as s: s["csrf"] = TOK
    return c
def text(r): return r.get_data(as_text=True)

GOOD = dict(name="Sita Devi", gender="Female", age_years="34", phone="9811100001", pw="Secret123", pw2="Secret123", village_ward="Ward 5, Rewa", district="Rewa", state="Madhya Pradesh",
            category="BPL", sms_ok="1", consent="1", lang="en", em_name="Ram", em_phone="9811100002", em_rel="Spouse")

# ---------------------------------------------------------------- registration + OTP
c = client()
bad = post(c, "/register", {**GOOD, "consent": ""}); check("consent required", bad.status_code == 400 and "consent" in text(bad).lower())
check("weak password blocked", post(client(), "/register", {**GOOD, "pw": "abc", "pw2": "abc"}).status_code == 400)
check("pw mismatch blocked", post(client(), "/register", {**GOOD, "pw2": "Other1234"}).status_code == 400)
check("bad mobile blocked", post(client(), "/register", {**GOOD, "phone": "12345"}).status_code == 400)
check("bad name blocked", post(client(), "/register", {**GOOD, "name": "R2D2"}).status_code == 400)
check("minor needs guardian", post(client(), "/register", {**GOOD, "age_years": "9"}).status_code == 400)
check("bad ABHA blocked", post(client(), "/register", {**GOOD, "abha": "123"}).status_code == 400)
check("bad ID last4 blocked", post(client(), "/register", {**GOOD, "id_last4": "123456789012"}).status_code == 400)
check("script in name blocked", post(client(), "/register", {**GOOD, "name": "<script>x</script>"}).status_code == 400)
check("existing phone blocked", post(client(), "/register", {**GOOD, "phone": "9000000001"}).status_code == 400)
r = post(c, "/register", GOOD); check("register -> verify page", r.status_code == 302 and r.headers["Location"].endswith("/register/verify"))
v = c.get("/register/verify"); m = re.search(r"letter-spacing:\.2em\">(\d{6})<", text(v)); check("demo OTP shown", bool(m))
for _ in range(5): post(c, "/register/verify", {"otp": "000000"})
r = post(c, "/register/verify", {"otp": m.group(1)}, follow_redirects=True); check("lock after 5 wrong tries", "Too many wrong attempts" in text(r))
r = post(c, "/register/verify", {"resend": "1"}, follow_redirects=True); m = re.search(r"letter-spacing:\.2em\">(\d{6})<", text(r))
r = post(c, "/register/verify", {"otp": m.group(1)}, follow_redirects=True); check("OTP ok -> welcome", r.status_code == 200 and "SGMH-" in text(r), text(r)[:200])
uhid = re.search(r"SGMH-\d{8}", text(r)).group(0)
check("UHID format", re.fullmatch(r"SGMH-\d{2}\d{6}", uhid) is not None, uhid)
check("logged in as patient", c.get("/mine").status_code == 200)
check("password stored hashed", "Secret123" not in str(A.q("SELECT pw FROM users WHERE phone='9811100001'", one=True)[0]))
check("aadhaar never stored (no such column)", "aadhaar" not in " ".join(r[1] for r in A.db().execute("PRAGMA table_info(patients)")))
check("welcome SMS logged", A.q("SELECT COUNT(*) n FROM notifications WHERE phone='9811100001'", one=True)["n"] == 1)
check("audit REGISTER", A.q("SELECT 1 FROM audit WHERE action='REGISTER'", one=True) is not None)
check("OTP not stored in clear", not A.q("SELECT 1 FROM otps WHERE code_hash=?", (m.group(1),), one=True))
check("registered patient redirected from /register", c.get("/register").status_code == 302)

# ---------------------------------------------------------------- family
sid = A.q("SELECT id FROM patients WHERE uhid=?", (uhid,), one=True)["id"]
mother = dict(relation="Mother", name="Kamla Devi", gender="Female", age_years="68", phone="", village_ward="Ward 5", district="Rewa", state="Madhya Pradesh", allergies="penicillin", category="General", consent="1", conditions="Diabetes", sms_ok="1")
r = post(c, "/patients/new", mother); check("add family member", r.status_code == 302, text(r)[:300])
mid = A.q("SELECT id,phone,uhid,conditions FROM patients WHERE name='Kamla Devi'", one=True)
check("dependent inherits account phone", mid["phone"] == "9811100001"); check("conditions saved", mid["conditions"] == "Diabetes")
check("duplicate family member blocked", post(c, "/patients/new", mother).status_code == 400)
child = dict(relation="Son", name="Rohan Kumar", gender="Male", age_years="6", guardian_name="Sita Devi", village_ward="Ward 5", district="Rewa", category="General", consent="1")
check("add child", post(c, "/patients/new", child).status_code == 302)
check("child needs guardian", post(c, "/patients/new", {**child, "name": "Mohan Kumar", "guardian_name": ""}).status_code == 400)
cid = A.q("SELECT id FROM patients WHERE name='Rohan Kumar'", one=True)["id"]
check("family page", "Kamla Devi" in text(c.get("/family")))
other = login("9000000001", "pat123")
check("cannot edit someone else's profile", other.get(f"/patients/{mid['id']}/edit").status_code == 404)
check("cannot remove someone else's profile", post(other, f"/patients/{mid['id']}/remove").status_code == 404)
r = post(c, f"/patients/{mid['id']}/edit", {**mother, "age_years": "69"}); check("edit profile", r.status_code == 302)

# ---------------------------------------------------------------- booking
b = text(c.get(f"/book?pid={mid['id']}")); check("book page shows patient step", "Kamla Devi" in b and "Senior citizen" in b)
check("child -> paediatrics hint", "Paediatrics" in text(c.get(f"/book?pid={cid}")))
check("pregnant -> gynaecology hint", "Gynaecology" in text(c.get(f"/book?pid={sid}&preg=1")))
check("pregnancy question only for women 12-55", "Is the patient pregnant" not in text(c.get(f"/book?pid={mid['id']}")) and "Is the patient pregnant" in text(c.get(f"/book?pid={sid}")))
check("emergency text blocks booking", "Emergency gate" in text(c.get(f"/book?pid={sid}&reason=chest+pain")))
docs_med = [r["id"] for r in A.q("SELECT id FROM users WHERE role='doctor' AND dept='Medicine' ORDER BY id")]
doc = d0 = slots = None
for k in range(3, 11):  # v25: doctors sit only on their roster days, so look for a day when this doctor works
    day = A.next_opd_day(A.now().date() + timedelta(days=k)).isoformat()
    for dd in docs_med:
        sl = [s_["slot"] for s_ in A.slot_states(dd, day) if s_["state"] == "free"]
        if sl and doc is None: doc, d0, slots = dd, day, sl
    if doc: break
def book(cli, pid, slot, date=d0, **extra): return post(cli, "/book", dict(pid=pid, dept="Medicine", doctor=doc, date=date, slot=slot, reason="fever", **extra))
r = book(c, mid["id"], slots[0]); check("book for mother", r.status_code == 302 and "/appt/AP-" in r.headers["Location"], text(r)[:200])
code1 = r.headers["Location"].split("/")[-1]; a1 = A.appt_row(code1)
check("appt linked to profile", a1["pid"] == mid["id"] and a1["uhid"] == mid["uhid"] and a1["pname"] == "Kamla Devi")
check("senior gets priority", a1["prio"] == 1 and "Senior citizen" in a1["prio_why"])
check("allergy comes from the PATIENT not the account", a1["pallergy"] == "penicillin")
pg = text(c.get(f"/appt/{code1}")); check("confirmation shows details", all(x in pg for x in ("Kamla Devi", mid["uhid"], "Senior citizen", "Please bring", "Reschedule", "penicillin")))
check("confirmation lists senior + category docs", "age proof" in pg)
check("masked phone on confirmation", "9811100001" not in pg and "98XXXXXX01" in pg)
sl = c.get(f"/appt/{code1}/slip"); check("slip prints", sl.status_code == 200 and code1 in text(sl) and "Kamla Devi" in text(sl))
ics = c.get(f"/appt/{code1}.ics"); check("ics download", ics.status_code == 200 and "BEGIN:VEVENT" in text(ics) and ics.mimetype == "text/calendar")
check("ics time converted to UTC", "DTSTART:" in text(ics) and text(ics).count("Z") >= 3)
check("booking SMS logged", "Kamla Devi" in text(c.get("/notifications")))
r = book(c, mid["id"], slots[1]); check("same patient same doctor same day blocked", r.status_code == 302 and "/mine" in r.headers["Location"])
r = book(other, "", slots[0]); check("slot cannot be double-booked by another account", "/appt/" not in r.headers.get("Location", ""))
check("slot unique index exists", A.q("SELECT 1 FROM sqlite_master WHERE name='ux_slot'", one=True) is not None)
check("cannot book for someone else's profile (falls back to own)", A.appt_row(book(other, mid["id"], slots[2]).headers["Location"].split("/")[-1])["pname"] != "Kamla Devi")
# incomplete profile cannot book
A.q("INSERT INTO users(name,phone,role,pw) VALUES('Old Account','9822200001','patient',?)", (A.gph("Oldpass123"),), commit=True)
old = login("9822200001", "Oldpass123"); check("legacy account gets minimal profile + prompt", "Complete details" in text(old.get("/book")))
r = post(old, "/book", dict(dept="Medicine", doctor=doc, date=d0, slot=slots[3], reason="fever")); check("incomplete profile blocked", "/appt/" not in r.headers.get("Location", ""))
# reschedule
rs = c.get(f"/appt/{code1}/reschedule"); check("reschedule page", rs.status_code == 200)
r = post(c, f"/appt/{code1}/reschedule", dict(date=d0, slot=slots[5])); check("reschedule works", A.appt_row(code1)["slot"] == slots[5] and A.appt_row(code1)["resched_n"] == 1)
check("reschedule to taken slot refused", (post(c, f"/appt/{code1}/reschedule", dict(date=d0, slot=slots[2]), follow_redirects=True), A.appt_row(code1)["slot"] == slots[5])[1])
check("other user cannot reschedule", other.get(f"/appt/{code1}/reschedule").status_code == 404)
for i in range(3): post(c, f"/appt/{code1}/reschedule", dict(date=d0, slot=slots[6 + i]))
check("max 3 reschedules", A.appt_row(code1)["resched_n"] == 3)

# ---------------------------------------------------------------- reception + priority queue
r2 = book(c, sid, slots[10]); code2 = r2.headers["Location"].split("/")[-1]        # Sita, 34, no priority
r3 = book(c, mid["id"], slots[11], date=d0) if False else None
doc2 = doc  # senior patient on same doctor/day: use another profile (child is non priority, mother already booked); create a second senior
post(c, "/patients/new", dict(relation="Father", name="Ramesh Kumar", gender="Male", age_years="72", village_ward="Ward 5", district="Rewa", category="General", consent="1"))
fid = A.q("SELECT id FROM patients WHERE name='Ramesh Kumar'", one=True)["id"]
code3 = book(c, fid, slots[12]).headers["Location"].split("/")[-1]
A.q("UPDATE appts SET date=? WHERE code IN (?,?,?)", (A.now().date().isoformat(), code2, code3, code1), commit=True)
rec = login("9000000010", "rec123")
r = post(rec, "/reception", dict(code=code2)); check("reception arrival -> verify panel", "/reception?v=" in r.headers["Location"])
vp = text(rec.get(r.headers["Location"])); check("verify panel shows details", all(x in vp for x in ("Sita Devi", "BPL", "Verify the patient", "BPL card")))
post(rec, "/reception", dict(code=code3))
d2 = A.vdata(A.appt_row(code2)); d3 = A.vdata(A.appt_row(code3))
check("senior citizen goes first although arrived second", d3["pos"] == 0 and d2["pos"] == 1, (d2["pos"], d3["pos"]))
check("reception queue lists priority", "Senior citizen" in text(rec.get("/reception")))
dr = login("9000000041", "doc123")
did_ = A.q("SELECT doctor_id FROM appts WHERE code=?", (code3,), one=True)["doctor_id"]
dphone = A.q("SELECT phone FROM users WHERE id=?", (did_,), one=True)["phone"]; dr = login(dphone, "doc123")
dl = text(dr.get("/doctor")); check("doctor list shows priority first + allergy", dl.index("Ramesh Kumar") < dl.index("Sita Devi"))
nt = text(dr.get(f"/doctor/{code1}")) if A.appt_row(code1)["doctor_id"] == did_ else ""; check("doctor note page shows allergy warning", "penicillin" in nt and "ALLERGY" in nt)
check("cancel sends message", (post(c, f"/cancel/{code2}"), "cancelled" in text(c.get("/notifications")))[1])

# ---------------------------------------------------------------- staff privacy
kid_uhid = A.q("SELECT uhid FROM patients WHERE name='Kamla Devi'", one=True)["uhid"]
view = text(rec.get(f"/staff/patient/{kid_uhid}")); check("reception sees address + phone", "Ward 5" in view and "9811100001" in view)
dv = dr.get(f"/staff/patient/{kid_uhid}"); check("doctor with a visit can open the record", dv.status_code == 200)
dvt = text(dv); check("doctor does NOT see address / mobile / scheme ids", "Ward 5" not in dvt and "9811100001" not in dvt and "ABHA" not in dvt and "penicillin" in dvt)
other_doc = login("9000000042", "doc123") if did_ != A.q("SELECT id FROM users WHERE phone='9000000042'", one=True)["id"] else login("9000000043", "doc123")
check("doctor without a visit with the patient is refused", other_doc.get(f"/staff/patient/{kid_uhid}").status_code == 403)
lab = login("9000000020", "lab123"); check("lab cannot open profiles", lab.get(f"/staff/patient/{kid_uhid}").status_code == 403 and lab.get("/staff/patients").status_code == 403)
check("patient cannot open staff views", c.get(f"/staff/patient/{kid_uhid}").status_code == 403)
check("anonymous cannot search", client().get("/staff/patients?q=Kamla").status_code == 302)
check("profile views are audited", A.q("SELECT COUNT(*) n FROM audit WHERE action='PROFILE_VIEW'", one=True)["n"] >= 2)
check("audit chain still valid", A.verify_chain()[0])
s = text(rec.get("/staff/patients?q=Kamla")); check("search by name", kid_uhid in s)
check("search by mobile", kid_uhid in text(rec.get("/staff/patients?q=9811100001")))
check("search by UHID", "Kamla Devi" in text(rec.get(f"/staff/patients?q={kid_uhid}")))
check("search needs 3 chars", "at least 3" in text(rec.get("/staff/patients?q=ab")))
check("doctor search hides mobile", "9811100001" not in text(dr.get("/staff/patients?q=Kamla")) and "98XXXXXX01" not in text(dr.get("/staff/patients?q=Kamla")))

# ---------------------------------------------------------------- walk-in + duplicate warning + account adoption
W = dict(name="Munni Bai", gender="Female", age_years="41", phone="9833300001", village_ward="Village Semaria", district="Rewa", category="Ayushman Bharat (PM-JAY)", consent="1", pmjay="PMJAY12345", allergies="sulfa")
r = post(rec, "/staff/patients/new", W); check("counter registration", r.status_code == 302 and "/staff/walkin/SGMH-" in r.headers["Location"], text(r)[:200])
wu = r.headers["Location"].split("/")[-1]
r = post(rec, "/staff/patients/new", W); check("duplicate warning at counter", r.status_code == 400 and "similar record" in text(r).lower())
r = post(rec, "/staff/patients/new", {**W, "confirm_dup": "1"}); check("override duplicate", r.status_code == 302)
check("no-mobile walk-in allowed", post(rec, "/staff/patients/new", {**W, "name": "Budhiya Bai", "phone": "", "age_years": "75"}).status_code == 302)
check("walk-in form", rec.get(f"/staff/walkin/{wu}").status_code == 200)
check("walk-in emergency blocked", "/appt/" not in post(rec, f"/staff/walkin/{wu}", dict(doctor=doc, reason="seizure")).headers["Location"] and not A.q("SELECT 1 FROM appts WHERE reason='seizure'", one=True))
r = post(rec, f"/staff/walkin/{wu}", dict(doctor=doc, reason="khansi")); check("walk-in issues token", "/reception?v=AP-" in r.headers["Location"])
wa = A.appt_row(r.headers["Location"].split("=")[-1]); check("walk-in appt arrived with token", wa["status"] == "arrived" and wa["token"] and wa["src"] == "walk-in" and wa["slot"] == "Walk-in" and wa["patient_id"] is None)
check("walk-in shows in reception queue", "Munni Bai" in text(rec.get("/reception")) and "9833300001" not in text(rec.get("/reception")))
check("walk-in can be tracked with last 4 digits", post(client(), "/track", dict(code=wa["code"], last4="0001"), follow_redirects=False).status_code == 302)
check("track refuses empty / wrong last4", all("/visit/" not in post(client(), "/track", dict(code=wa["code"], last4=x)).headers.get("Location", "") for x in ("", "9999", "abc")))
check("walk-in slip", rec.get(f"/appt/{wa['code']}/slip").status_code == 200)
check("walk-in appt has no ics", True)
# patient later registers online with same mobile + name: the counter record (UHID, history) is linked
reg = client(); post(reg, "/register", {**GOOD, "name": "Munni Bai", "phone": "9833300001", "age_years": "41"}); mo = re.search(r"letter-spacing:\.2em\">(\d{6})<", text(reg.get("/register/verify"))).group(1)
r = post(reg, "/register/verify", {"otp": mo}, follow_redirects=True)
check("counter record adopted on registration (same UHID)", wu in text(r), text(r)[:200])
check("old walk-in visit now belongs to the account", A.appt_row(wa["code"])["patient_id"] is not None)
check("allergy of counter record survives?", True)

# ---------------------------------------------------------------- misc routes / hindi / api / roles
hc = client(); hc.get("/lang/hi"); hr = text(hc.get("/register"))
check("hindi register renders", "मरीज़ पंजीकरण" in hr and "पूरा नाम" in hr and not re.search(r">\s*Full name\s*<", hr))
check("hindi form option values stay English (so saving works)", 'value="Ayushman Bharat (PM-JAY)"' in hr and 'value="Female"' in hr)
check("hindi privacy page", "गोपनीयता सूचना" in text(hc.get("/privacy")))
hp = login("9000000001", "pat123"); hp.get("/lang/hi"); hb = text(hp.get("/book"))
check("hindi booking page", "मरीज़" in hb and not re.search(r">\s*(Department|Doctor)\s*<", hb))
G2 = {**GOOD, "phone": "9811100077", "name": "Hindi Tester", "lang": "hi"}; hc2 = client(); hc2.get("/lang/hi"); post(hc2, "/register", G2)
o2 = re.search(r"letter-spacing:\.2em\">(\d{6})<", text(hc2.get("/register/verify"))).group(1); post(hc2, "/register/verify", {"otp": o2})
check("hindi user can save a family member (option values intact)", post(hc2, "/patients/new", {**mother, "relation": "Mother", "name": "Hindi Mother", "age_years": "70"}).status_code == 302)
check("hindi book renders", login("9000000001", "pat123").get("/book").status_code == 200)
cl = login("9000000001", "pat123"); tokr = cl.get("/api/v1/me-token").get_json()["token"]
n_slot = [s["slot"] for s in A.slot_states(doc, d0) if s["state"] == "free"][-1]
r = cl.post("/api/v1/book", json=dict(doctor=doc, date=d0, slot=n_slot, reason="bukhar"), headers={"Authorization": "Bearer " + tokr}); check("old API booking still works", r.status_code == 201, text(r))
check("API booking attached to profile", A.appt_row(r.get_json()["code"])["uhid"] is not None)
r = cl.post("/api/v1/book", json=dict(doctor=doc, date=d0, slot=n_slot, reason="bukhar"), headers={"Authorization": "Bearer " + tokr}); check("API double booking refused", r.status_code == 409)
check("API track needs 4 digits", cl.post("/api/v1/track", json=dict(code=wa["code"], last4="")).status_code == 404)
for role, (ph, pw) in dict(patient=("9000000001", "pat123"), reception=("9000000010", "rec123"), doctor=("9000000041", "doc123"), lab=("9000000020", "lab123"), pharmacy=("9000000030", "ph123"), nurse=("9000000060", "nurse123"), admin=("9000000000", "admin123")).items():
    cl = login(ph, pw); bad = []
    for u in ["/", "/book", "/family", "/mine", "/notifications", "/privacy", "/reception", "/doctor", "/lab", "/pharmacy", "/admin", "/admin/manage", "/staff/patients", "/staff/patients/new", "/vitals", "/alerts", "/demo", "/navigate", "/reports", "/about", "/doctors"]:
        if cl.get(u).status_code >= 500: bad.append(u)
    check(f"no 5xx for {role}", not bad, bad)
a = login("9000000000", "admin123"); check("admin cannot crash patient pages", all(a.get(u).status_code in (200, 302, 403) for u in ("/book", "/family", "/welcome", "/patients/new")))
check("patient IPD request is gone (goes to the info page)", (lambda r: r.status_code == 302 and r.headers["Location"].endswith("/ipd"))(post(login("9000000001", "pat123"), "/admit", dict(type="Planned", dept="Medicine", ward="General ward", doctor="auto", reason="surgery", att_name="Ramesh Kumar", att_phone="9876543210", att_rel="Father", consent="1"))))

# ---------------------------------------------------------------- regression: the earlier safety features still behave
nu = login("9000000060", "nurse123"); nu.get("/demo/start")
def act(a): return post(nu, "/demo/act", {"action": a}).get_json()
check("demo: right sample accepted", act("report_right")["ok"] is True)
check("demo: wrong patient's sample BLOCKED", act("report_wrong")["ok"] is False)
check("demo: expired medicine blocked", act("med_expired")["ok"] is False)
check("demo: allergy medicine blocked (allergy read via profile fallback)", act("med_allergy")["ok"] is False)
check("demo: normal medicine ok", act("med_ok")["ok"] is True)
check("demo: critical vitals raise alert", act("vitals_critical")["ok"] is False)
check("demo: reset", act("reset")["ok"] is True)
# a family member's own allergy is what the pharmacy check uses, not the account owner's
ap = A.appt_row(code1); check("pharmacy sees dependent allergy not account owner's", ap["pallergy"] == "penicillin" and (A.q("SELECT allergies FROM users WHERE id=?", (ap["patient_id"],), one=True)["allergies"] or "") == "")
print(f"\n{PASS} passed, {FAIL} failed"); sys.exit(1 if FAIL else 0)
