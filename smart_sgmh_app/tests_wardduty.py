"""Workflow check: no patient IPD request, doctor admits from OPD, emergency admit, ward duty, ward-wise alerts, auto care team, ward view. Run: python tests_wardduty.py (throw-away database)."""
import os, re, sys, io, tempfile
d = tempfile.mkdtemp(); os.environ["DB_PATH"] = d + "/t.db"; os.environ["UPLOAD_DIR"] = d + "/up"; os.environ["DEMO_MODE"] = "1"
import app as A
app = A.app; ok = bad = 0
def ck(n, c, x=""):
    global ok, bad
    if c: ok += 1
    else: bad += 1; print("FAIL", n, x)
def issue(phone): return A.issue_card(A.q("SELECT id FROM users WHERE phone=?", (phone,), one=True)["id"], "test")
def mk(): 
    c = app.test_client()
    with c.session_transaction() as s: s["csrf"] = "t"; s["lang"] = "en"
    return c
def post(c, url, data=None, **kw):
    with c.session_transaction() as s: t = s.setdefault("csrf", "t")
    return c.post(url, data={"csrf": t, **(data or {})}, **kw)
def staff(phone, pw):
    c = mk(); r = post(c, "/login", dict(phone=phone, pw=pw, card=issue(phone))); assert r.status_code == 302 and "/login" not in r.headers["Location"], (phone, r.status_code); return c
def body(r): return r.get_data(as_text=True)
# patient + booking with doctor 10 (login 9000000045 / doc123)
P = mk(); post(P, "/start", dict(name="Ipd Test", phone="9866600022")); o = re.search(r"<b>(\d{6})</b>", body(P.get("/start/verify"))).group(1); post(P, "/start/verify", dict(otp=o))
pr = A.q("SELECT * FROM patients WHERE owner_id=(SELECT id FROM users WHERE phone='9866600022')", one=True)
loc = P.get("/book?dept=Cardiology&doctor=10").headers["Location"]; nxt = __import__("urllib.parse").parse.unquote(loc.split("next=")[1])
post(P, "/register/details", dict(name="Ipd Test", gender="Male", age_years="40", village_ward="X", district="Rewa", state="MP", category="General", consent="1", lang="en", next=nxt, pid=str(pr["id"]), pw="Secret123", pw2="Secret123"))
nf = A.next_free(10); r = post(P, "/book", dict(pid=pr["id"], dept="Cardiology", doctor=10, date=nf["date"], slot=nf["slot"], reason="fever")); code = r.headers["Location"].split("/appt/")[1]
aid = A.q("SELECT id FROM appts WHERE code=?", (code,), one=True)["id"]

D = staff("9000000045", "doc123"); D2 = staff("9000000042", "doc123"); REC = staff("9000000010", "rec123"); NU = staff("9000000060", "nurse123"); PH = staff("9000000030", "ph123"); L = staff("9000000020", "lab123")
def loc(r): return r.headers.get("Location", "")

CRIT = dict(bp_sys="86", bp_dia="54", pulse="134", spo2="88", temp="39.4")
def alerts_for(c): return json_(c.get("/api/alerts/latest"))["alerts"]
def json_(r): return __import__("json").loads(r.get_data(as_text=True))
def codes(c): return {a["code"] for a in alerts_for(c)}
def open_n(c): d = json_(c.get("/api/alerts/count")); return d["open"] + d["escalated"]

# ---------- A. patient side: no IPD request any more
r = P.get("/admit"); ck("patient /admit goes to the IPD info page", r.status_code == 302 and loc(r).endswith("/ipd"), loc(r))
r = post(P, "/admit", dict(type="Planned", dept="Medicine", ward="General ward", reason="fever", att_name="A B", att_phone="9876543210", att_rel="Father", consent="1")); ck("patient cannot post an admission request", loc(r).endswith("/ipd") and A.q("SELECT COUNT(*) n FROM appts WHERE kind='IPD'", one=True)["n"] == 0)
pub = app.test_client(); ip_html = body(pub.get("/ipd")); ck("IPD page open to all, explains doctor / emergency flow", "Doctor admits" in ip_html and "Emergency" in ip_html and 'href="/admit' not in ip_html)
ck("no IPD tab on the booking page", 'href="/admit' not in body(P.get("/book?dept=Cardiology&doctor=10")))
ck("OPD doctor cards have no IPD admission button", 'href="/admit' not in body(pub.get("/opd")) and 'href="/admit' not in body(pub.get("/doctors")))
ck("home tiles have no admit tile", 'href="/admit"' not in body(P.get("/home")))

# ---------- B. doctor admits from OPD into the ICU, reception gives the bed, care team fills itself
A.q("UPDATE appts SET status='arrived',token=1 WHERE code=?", (code,), commit=True)  # reception check-in (admission is allowed only after the patient came)
post(D, f"/doctor/{code}", dict(diagnosis="Acute chest pain", meds="Aspirin 75 mg", followup_date="", followup="", do_text="", avoid_text="", care=""))
post(D, f"/doctor/{code}/refer-admit", dict(ward="ICU / HDU", type="Urgent", reason="Acute chest pain, needs monitoring"))
ip = A.q("SELECT a.* FROM appts a JOIN ipd_info i ON i.appt_id=a.id WHERE i.ref_from=?", (code,), one=True); IC = ip["code"]
post(REC, f"/reception/admit/{IC}", dict(bed="ICU-1", id_ok="1")); ip = A.q("SELECT * FROM appts WHERE code=?", (IC,), one=True)
ck("admitted in the ICU, bed given", ip["status"] == "admitted" and ip["ward"] == "ICU / HDU" and ip["bed"] == "ICU-1")
ct = A.q("SELECT * FROM careteam WHERE appt_id=?", (ip["id"],), one=True)
ck("care team filled from the ward roster", ct and ct["duty_doctor"] == "Dr. Kuwer Devi Singh" and "Nurse Sunita (ICU)" in ct["nurse"] and ct["shift"] == "All day" and ct["by"].startswith("auto"), dict(ct) if ct else None)
v = body(P.get(f"/visit/{IC}")); ck("patient sees ward, bed, duty nurse and doctor", "ICU / HDU" in v and "ICU-1" in v and "Nurse Sunita" in v and "Dr. Kuwer Devi Singh" in v)
ck("treating doctor sees the same card", "Nurse Sunita" in body(D.get(f"/ward/{IC}")))

A.q("UPDATE alerts SET status='closed'", commit=True)  # start from a clean alert list
# ---------- C. OPD closed: emergency admit by a nurse, serious patient
A.q("UPDATE ward_duty SET shift='All day' WHERE user_id=(SELECT id FROM users WHERE phone='9000000060')", commit=True)  # the test must not depend on the time of day it runs
r = post(NU, "/emergency", dict(triage="Red", complaint="Road accident, head injury", ward="General ward", bed="G-5", gender="Male", age_years="35", brought_by="Passer-by", brought_phone="9876500001"), follow_redirects=False)
ec = re.search(r"/ipd/(IP-\w+)/chart", loc(r)); ck("emergency admit works without booking", ec is not None, loc(r) or body(r)[:200]); EC = ec.group(1)
ea = A.q("SELECT * FROM appts WHERE code=?", (EC,), one=True)
ck("emergency patient is in the ward and the care team is filled", ea["status"] == "admitted" and A.q("SELECT nurse FROM careteam WHERE appt_id=?", (ea["id"],), one=True)["nurse"].startswith("Nurse Station"))

# ---------- D. who gets which alert
N_ICU = staff("9000000061", "nurse123"); N_GEN = NU; N_MAT = staff("9000000062", "nurse123"); DR_GEN = staff("9000000041", "doc123"); DR_ICU = D; ADM = staff("9000000000", "admin123")
post(N_ICU, f"/vitals/{IC}", CRIT)
ck("ICU critical alert exists", A.q("SELECT COUNT(*) n FROM alerts al WHERE al.appt_id=? AND al.kind='DETERIORATION' AND al.status='open'", (ip["id"],), one=True)["n"] == 1)
ck("treating / duty doctor of the ICU gets it", IC in codes(DR_ICU) and open_n(DR_ICU) == 1)
ck("ICU duty nurse gets it", IC in codes(N_ICU))
ck("General ward doctor does NOT get it", IC not in codes(DR_GEN))
ck("General ward nurse does NOT get it", IC not in codes(N_GEN))
ck("Maternity nurse does NOT get it", IC not in codes(N_MAT))
ck("admin sees it", IC in codes(ADM))
ck("alerts page of another ward does not list it", IC not in body(N_GEN.get("/alerts")) and IC in body(N_ICU.get("/alerts")))
ck("alerts page says who was told", "Sent to:" in body(N_ICU.get("/alerts")) and "Nurse Sunita (ICU)" in body(N_ICU.get("/alerts")) and "Dr. Kuwer Devi Singh" in body(N_ICU.get("/alerts")))
al = A.q("SELECT id FROM alerts WHERE appt_id=? AND kind='DETERIORATION'", (ip["id"],), one=True)["id"]
ck("other ward cannot acknowledge it", post(N_GEN, f"/alerts/{al}/ack", dict(note="x")).status_code == 403 and A.q("SELECT status FROM alerts WHERE id=?", (al,), one=True)["status"] == "open")
# emergency patient (General ward): the General ward doctor + nurse get the emergency alert
ck("General ward nurse and doctor get the emergency alert", EC in codes(N_GEN) and EC in codes(DR_GEN), (codes(N_GEN), codes(DR_GEN)))
ck("ICU nurse does not get the General ward emergency", EC not in codes(N_ICU))
# nobody acknowledges: escalated -> everybody on duty
A.q("UPDATE alerts SET status='escalated' WHERE id=?", (al,), commit=True)
ck("escalated alert reaches every doctor and nurse", all(IC in codes(c) for c in (DR_GEN, N_GEN, N_MAT)))
r = post(N_ICU, f"/alerts/{al}/ack", dict(note="Doctor called")); ck("duty nurse can acknowledge", A.q("SELECT status FROM alerts WHERE id=?", (al,), one=True)["status"] == "acknowledged")
# a nurse with no ward set still sees everything (fail-safe)
A.q("INSERT INTO users(name,phone,role,pw) VALUES('Nurse New','9000000069','nurse',?)", (A.gph("nurse123"),), commit=True)
N_NEW = staff("9000000069", "nurse123"); ck("nurse with no ward set sees all open alerts", EC in codes(N_NEW))

# ---------- E. ward live view
w = body(N_ICU.get("/wardview")); ck("ICU nurse opens her own ward by default", "Ward view: ICU / HDU" in w and "ICU-1" in w and "Ipd Test" in w and "Acute chest pain" in w)
ck("ward view shows duty staff and latest vitals", "Nurse Sunita" in w and "Dr. Kuwer Devi Singh" in w and "critical" in w and "134" in w)
ck("ward view of General ward shows emergency patient", "G-5" in body(N_GEN.get("/wardview")) and "Doctor review pending" in body(N_GEN.get("/wardview")))
ck("doctor can look at another ward", "Ward view: Maternity ward" in body(DR_GEN.get("/wardview?ward=Maternity%20ward")))
ck("patient and reception cannot open ward view", P.get("/wardview").status_code in (302, 403) and REC.get("/wardview").status_code == 403)

# ---------- F. admin roster
ck("admin opens the roster", "Ward duty roster" in body(ADM.get("/admin/ward-duty")) and "Nurse Sunita" in body(ADM.get("/admin/ward-duty")))
ck("doctor cannot edit the roster", DR_GEN.get("/admin/ward-duty").status_code == 403 and post(DR_GEN, "/admin/ward-duty", dict(user_id="1")).status_code == 403)
uid = A.q("SELECT id FROM users WHERE phone='9000000069'", one=True)["id"]
post(ADM, "/admin/ward-duty", {"user_id": str(uid), "ward": ["ICU / HDU"], "shift": "Night (8-8)"})
ck("roster saved", A.q("SELECT shift FROM ward_duty WHERE user_id=? AND ward='ICU / HDU'", (uid,), one=True)["shift"] == "Night (8-8)")
ck("that nurse now sees only her ward", EC not in codes(N_NEW) and A.q("SELECT 1 FROM alerts WHERE status='open' AND appt_id=?", (ea["id"],), one=True) is not None)
# an emergency-admission alert nobody acknowledges must escalate to every doctor and nurse (not only deterioration alerts)
import datetime as _dt
_e = A.q("SELECT al.id FROM alerts al WHERE al.kind='EMERGENCY_ADMIT' AND al.status='open' ORDER BY al.id DESC", one=True)
ck("an open emergency alert exists to test escalation", _e is not None)
if _e:
    _n = staff("9000000060", "nurse123")
    A.q("UPDATE alerts SET ts=? WHERE id=?", ((A.now() - _dt.timedelta(minutes=30)).strftime(A.FMT), _e["id"]), commit=True)
    ck("unacknowledged emergency alert escalates to other wards", _n.get("/api/alerts/count").get_json()["escalated"] >= 1 and A.q("SELECT status FROM alerts WHERE id=?", (_e["id"],), one=True)["status"] == "escalated")
print(f"{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
