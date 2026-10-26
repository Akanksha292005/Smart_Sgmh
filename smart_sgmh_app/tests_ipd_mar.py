"""Nurse medicine record (MAR), late-dose alerts, shift-aware duty, and the patient/family A-to-Z stay view. Run: python tests_ipd_mar.py (throw-away database)."""
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
P = mk(); post(P, "/start", dict(name="Mar Test", phone="9866600005")); o = re.search(r"<b>(\d{6})</b>", body(P.get("/start/verify"))).group(1); post(P, "/start/verify", dict(otp=o))
pr = A.q("SELECT * FROM patients WHERE owner_id=(SELECT id FROM users WHERE phone='9866600005')", one=True)
loc = P.get("/book?dept=Cardiology&doctor=10").headers["Location"]; nxt = __import__("urllib.parse").parse.unquote(loc.split("next=")[1])
post(P, "/register/details", dict(name="Mar Test", gender="Male", age_years="40", village_ward="X", district="Rewa", state="MP", category="General", consent="1", lang="en", next=nxt, pid=str(pr["id"]), pw="Secret123", pw2="Secret123"))
nf = A.next_free(10); r = post(P, "/book", dict(pid=pr["id"], dept="Cardiology", doctor=10, date=nf["date"], slot=nf["slot"], reason="fever")); code = r.headers["Location"].split("/appt/")[1]
aid = A.q("SELECT id FROM appts WHERE code=?", (code,), one=True)["id"]

import datetime as _dt
D = staff("9000000045", "doc123"); D2 = staff("9000000042", "doc123"); REC = staff("9000000010", "rec123"); NU = staff("9000000060", "nurse123")
A.q("UPDATE ward_duty SET shift='All day'", commit=True)   # clock-independent
def loc(r): return r.headers.get("Location", "")
def ago(h=0, m=0): return (A.now() - _dt.timedelta(hours=h, minutes=m)).strftime(A.FMT)
# ---------- frequency reader
for txt, exp in [("Inj. Ceftriaxone 1 g IV twice daily", (12, False)), ("Tab X 500 mg BD", (12, False)), ("Tab X TDS", (8, False)), ("Tab X thrice daily", (8, False)), ("Tab X QID", (6, False)), ("Tab X OD", (24, False)),
                 ("Tab X once daily", (24, False)), ("Inj. Y every 6 hours", (6, False)), ("Inj. Y q4h", (4, False)), ("Tab Z 650 mg 6 hourly", (6, False)), ("Tab Z SOS", (None, True)), ("Tab Z if needed for pain", (None, True)),
                 ("O2 inhalation stat", (None, False)), ("Tab Q 500 mg", (None, False))]:
    ck(f"frequency read: {txt}", A.interval_of(txt) == exp, A.interval_of(txt))
# ---------- shift-aware duty
H = lambda h: _dt.datetime(2026, 1, 5, h, 0)
ck("Morning shift runs 8 to 2 only", [A.ward_shift_on("Morning (8-2)", H(h)) for h in (7, 8, 13, 14)] == [False, True, True, False])
ck("Evening shift runs 2 to 8 only", [A.ward_shift_on("Evening (2-8)", H(h)) for h in (13, 14, 19, 20)] == [False, True, True, False])
ck("Night shift crosses midnight", [A.ward_shift_on("Night (8-8)", H(h)) for h in (19, 20, 23, 2, 7, 8)] == [False, True, True, True, True, False])
ck("All day is always on", A.ward_shift_on("All day", H(3)) and A.ward_shift_on("All day", H(15)))
nid = A.q("SELECT id FROM users WHERE phone='9000000060'", one=True)["id"]
A.q("UPDATE ward_duty SET shift='Night (8-8)' WHERE user_id=?", (nid,), commit=True); h_ = A.now().hour; night = (h_ >= 20 or h_ < 8)
ck("on-duty list follows the clock (night nurse)", ("Nurse Station" in A.duty_live("General ward")["nurses"]) == night, (h_, A.duty_live("General ward")))
A.q("UPDATE ward_duty SET shift='All day' WHERE user_id=?", (nid,), commit=True)
# ---------- referral -> admission, doctor orders medicines
A.q("UPDATE appts SET status='arrived',token=1 WHERE code=?", (code,), commit=True)  # reception check-in (admission is allowed only after the patient came)
post(D, f"/doctor/{code}", dict(diagnosis="Pneumonia", meds="Azithromycin 500 mg", followup_date="", followup="", do_text="", avoid_text="", care=""))
post(D, f"/doctor/{code}/refer-admit", dict(ward="General ward", type="Urgent", reason="Pneumonia, IV antibiotics"))
IC = A.q("SELECT a.code FROM appts a JOIN ipd_info i ON i.appt_id=a.id WHERE i.ref_from=?", (code,), one=True)["code"]; ia = A.appt_row(IC)
post(REC, f"/reception/admit/{IC}", dict(bed="G-1", id_ok="1")); ck("admitted", A.appt_row(IC)["status"] == "admitted")
r = post(D, f"/ipd/{IC}/note", dict(kind="admission", diagnosis="Pneumonia", findings="Fever 102 F, crepts right base", family_text="Chest infection. Antibiotic drip started. Blood test sent.",
         meds="Inj. Ceftriaxone 1 g IV twice daily\nTab. Paracetamol 500 mg SOS\nInj. Pantoprazole 40 mg IV every 8 hours\nO2 inhalation stat", tests=["Complete Blood Count (CBC)"], plan="Monitor SpO2"), follow_redirects=True)
od = {o["drug"].split()[1]: o for o in A.q("SELECT * FROM ipd_orders WHERE appt_id=?", (ia["id"],))}
ck("each medicine line became an order", len(od) == 4 and set(od) == {"Ceftriaxone", "Paracetamol", "Pantoprazole", "inhalation"}, list(od))
ck("schedules read correctly", od["Ceftriaxone"]["interval_h"] == 12 and od["Pantoprazole"]["interval_h"] == 8 and od["Paracetamol"]["prn"] == 1 and od["inhalation"]["interval_h"] is None)
post(D, f"/ipd/{IC}/note", dict(kind="round", findings="Better", meds="Inj. Ceftriaxone 1 g IV twice daily"))
ck("repeating a medicine does not duplicate the order", A.q("SELECT COUNT(*) n FROM ipd_orders WHERE appt_id=?", (ia["id"],), one=True)["n"] == 4)
ck("chart shows the medicine chart to the nurse", b"Medicine chart" in NU.get(f"/ipd/{IC}/chart").data and b"Ceftriaxone" in NU.get(f"/ipd/{IC}/chart").data)
# ---------- nurse records doses
CEF, PAN, PCM = od["Ceftriaxone"]["id"], od["Pantoprazole"]["id"], od["Paracetamol"]["id"]
ck("patient cannot record a dose", post(P, f"/ipd/{IC}/mar/{CEF}", dict(status="given")).status_code in (302, 403))
ck("bad status refused", b"Choose given" in post(NU, f"/ipd/{IC}/mar/{CEF}", dict(status="xx"), follow_redirects=True).data)
ck("order of another patient is not reachable", post(NU, f"/ipd/NOPE/mar/{CEF}", dict(status="given")).status_code == 404)
post(NU, f"/ipd/{IC}/mar/{CEF}", dict(status="given")); g = A.q("SELECT * FROM ipd_mar WHERE order_id=?", (CEF,), one=True)
ck("dose saved with nurse name and time", g and g["status"] == "given" and g["by"] == "nurse:Nurse Station" and g["ts"])
ck("same dose again right away is blocked (duplicate guard)", b"duplicate dose" in post(NU, f"/ipd/{IC}/mar/{CEF}", dict(status="given"), follow_redirects=True).data and A.q("SELECT COUNT(*) n FROM ipd_mar WHERE order_id=?", (CEF,), one=True)["n"] == 1)
post(NU, f"/ipd/{IC}/mar/{CEF}", dict(status="given", confirm_early="1")); ck("'give anyway' is allowed and recorded", A.q("SELECT COUNT(*) n FROM ipd_mar WHERE order_id=?", (CEF,), one=True)["n"] == 2)
ck("held needs a reason", b"Write the reason" in post(NU, f"/ipd/{IC}/mar/{PCM}", dict(status="held", note=""), follow_redirects=True).data)
post(NU, f"/ipd/{IC}/mar/{PCM}", dict(status="refused", note="Patient vomited, refused tablet"))
al = A.q("SELECT * FROM alerts WHERE appt_id=? AND kind='MED_NOT_GIVEN'", (ia["id"],), one=True); ck("refused dose alerts the doctor", al and "REFUSED" in al["message"] and "vomited" in al["message"])
ck("doctor sees that alert", b"REFUSED" in D.get("/alerts").data)
# ---------- late dose raises an alert once, closes when the dose is given
A.q("UPDATE ipd_orders SET ordered_ts=? WHERE id=?", (ago(h=3), PAN), commit=True)
NU.get("/api/alerts/count"); NU.get("/api/alerts/count")
ov = A.q("SELECT * FROM alerts WHERE appt_id=? AND kind='MED_DOSE_OVERDUE'", (ia["id"],)); ck("one overdue alert, not one per poll", len(ov) == 1 and "Pantoprazole" in ov[0]["message"] and f"order #{PAN}" in ov[0]["message"], len(ov))
ck("the alert names the nurse on duty", "Nurse Station" in ov[0]["message"])
ck("board shows overdue doses", "1 overdue" in D.get("/ipd/board").get_data(as_text=True))
fam = P.get(f"/visit/{IC}").get_data(as_text=True)
ck("family sees the delayed dose", "Delayed" in fam and "Pantoprazole" in fam)
post(NU, f"/ipd/{IC}/mar/{PAN}", dict(status="given")); ck("giving the dose closes the alert", A.q("SELECT status FROM alerts WHERE id=?", (ov[0]["id"],), one=True)["status"] == "closed")
# a dose due again after the interval
A.q("UPDATE ipd_mar SET ts=? WHERE order_id=?", (ago(h=13), CEF), commit=True); NU.get("/api/alerts/count")
ck("second-round dose overdue is detected", A.q("SELECT COUNT(*) n FROM alerts WHERE appt_id=? AND kind='MED_DOSE_OVERDUE' AND message LIKE ? AND status!='closed'", (ia["id"], f"%order #{CEF},%"), one=True)["n"] == 1)
a_id = A.q("SELECT id FROM alerts WHERE appt_id=? AND kind='MED_DOSE_OVERDUE' AND status!='closed'", (ia["id"],), one=True)["id"]
A.q("UPDATE alerts SET ts=? WHERE id=?", (ago(m=30), a_id), commit=True)
ck("unacknowledged late-dose alert escalates", NU.get("/api/alerts/count").get_json()["escalated"] >= 1 and A.q("SELECT status FROM alerts WHERE id=?", (a_id,), one=True)["status"] == "escalated")
ck("PRN medicine never raises a late alert", A.q("SELECT COUNT(*) n FROM alerts WHERE message LIKE ?", (f"%order #{PCM},%",), one=True)["n"] == 0)
# ---------- doctor stops a medicine
ck("only a doctor can stop an order", post(NU, f"/ipd/{IC}/order/{PCM}/stop").status_code == 403)
post(D, f"/ipd/{IC}/order/{PCM}/stop"); ck("stopped order is inactive", A.q("SELECT active FROM ipd_orders WHERE id=?", (PCM,), one=True)["active"] == 0)
ck("stopped medicine cannot be given", b"stopped" in post(NU, f"/ipd/{IC}/mar/{PCM}", dict(status="given"), follow_redirects=True).data)
# ---------- patient / family view: everything from A to Z, on the patient's own account
v = P.get(f"/visit/{IC}").get_data(as_text=True)
for what, key in [("patient details", "Mar Test"), ("UHID", "UHID"), ("admission ward and bed", "G-1"), ("treating doctor", ia["doctor"] if "doctor" in ia.keys() else "Dr."), ("OPD origin link", f"/visit/{code}"), ("journey", "Reception"), ("diagnosis", "Pneumonia"),
                  ("plain message for family", "In simple words"), ("doctor note findings", "crepts right base"), ("doctor name in timeline", "doctor:" if False else "Dr."), ("medicine", "Ceftriaxone"), ("dose given by nurse", "Nurse Station"),
                  ("refused dose with reason", "vomited"), ("stopped medicine", "stopped by"), ("test", "Complete Blood Count"), ("on duty now", "On duty now"), ("safety alert section", "Safety alerts")]:
    ck("family sees: " + what, key in v, key)
fr = P.get(f"/ipd/{IC}/family"); ck("live block works for the patient account", fr.status_code == 200 and "Ceftriaxone" in fr.get_data(as_text=True))
O = mk(); post(O, "/start", dict(name="Other Person", phone="9866600006")); o2 = re.search(r"<b>(\d{6})</b>", body(O.get("/start/verify"))).group(1); post(O, "/start/verify", dict(otp=o2))
ck("another patient cannot read it", O.get(f"/ipd/{IC}/family").status_code == 403 and "Ceftriaxone" not in body(O.get(f"/visit/{IC}", follow_redirects=True)))
ck("not logged in: nothing", mk().get(f"/ipd/{IC}/family").status_code == 403)
T = mk(); r = post(T, "/track", dict(code=IC, last4="9866600005"[-4:])); ck("family with code + last 4 digits can open it", loc(r).endswith(f"/visit/{IC}") and "Ceftriaxone" in body(T.get(f"/visit/{IC}")) and T.get(f"/ipd/{IC}/family").status_code == 200)
# ---------- emergency patient: family follows with the relative's phone
E = dict(triage="Red", complaint="Road accident, unconscious", ward="ICU / HDU", bed="E-1", dept="Medicine", gender="Male", age_years="40", brought_by="108 ambulance", brought_phone="9811100055", first_aid="Oxygen started")
r = post(REC, "/emergency", E); ec = loc(r).split("/ipd/")[1].split("/")[0]
T2 = mk(); post(T2, "/track", dict(code=ec, last4="0055")); ev = body(T2.get(f"/visit/{ec}"))
ck("emergency family sees admission + waiting for doctor", "Emergency admission" in ev and "has not yet examined" in ev and "Oxygen started" in ev and "Unknown male" in ev)
post(D2, f"/ipd/{ec}/note", dict(kind="admission", diagnosis="Head injury", findings="GCS 10", family_text="Head scan advised. Patient is being watched closely.", take_over="1"))
ev = body(T2.get(f"/visit/{ec}")); ck("after the doctor sees the patient the family sees who and when", "Examined by" in ev and "Head scan advised" in ev and "has not yet examined" not in ev)
# ---------- after discharge nothing can be recorded, summary link appears
post(D, f"/ipd/{IC}/summary/edit", dict(final_dx="Pneumonia", course="Recovered on antibiotics.", approve="1", cond="Improved"))
post(REC, f"/reception/discharge/{IC}"); ck("discharged", A.appt_row(IC)["status"] == "discharged")
ck("no dose after discharge", b"only while the patient is admitted" in post(NU, f"/ipd/{IC}/mar/{CEF}", dict(status="given"), follow_redirects=True).data)
vv = body(P.get(f"/visit/{IC}")); ck("family still sees the full record + summary after discharge", "Ceftriaxone" in vv and "Discharge summary is ready" in vv and "Discharge" in vv)
print(f"\n{ok} passed, {bad} failed")
