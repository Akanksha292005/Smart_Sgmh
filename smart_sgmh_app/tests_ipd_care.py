"""Refer-to-admit, emergency direct admit, IPD chart, discharge summary, board. Run: python tests_ipd_care.py (throw-away database)."""
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
P = mk(); post(P, "/start", dict(name="Ipd Test", phone="9866600002")); o = re.search(r"<b>(\d{6})</b>", body(P.get("/start/verify"))).group(1); post(P, "/start/verify", dict(otp=o))
pr = A.q("SELECT * FROM patients WHERE owner_id=(SELECT id FROM users WHERE phone='9866600002')", one=True)
loc = P.get("/book?dept=Cardiology&doctor=10").headers["Location"]; nxt = __import__("urllib.parse").parse.unquote(loc.split("next=")[1])
post(P, "/register/details", dict(name="Ipd Test", gender="Male", age_years="40", village_ward="X", district="Rewa", state="MP", category="General", consent="1", lang="en", next=nxt, pid=str(pr["id"]), pw="Secret123", pw2="Secret123"))
nf = A.next_free(10); r = post(P, "/book", dict(pid=pr["id"], dept="Cardiology", doctor=10, date=nf["date"], slot=nf["slot"], reason="fever")); code = r.headers["Location"].split("/appt/")[1]
aid = A.q("SELECT id FROM appts WHERE code=?", (code,), one=True)["id"]

D = staff("9000000045", "doc123"); D2 = staff("9000000042", "doc123"); REC = staff("9000000010", "rec123"); NU = staff("9000000060", "nurse123"); PH = staff("9000000030", "ph123"); L = staff("9000000020", "lab123")
def loc(r): return r.headers.get("Location", "")
# ---------- 1. doctor refers the OPD patient for admission
A.q("UPDATE appts SET status='arrived',token=1 WHERE code=?", (code,), commit=True)  # reception check-in (admission is allowed only after the patient came)
post(D, f"/doctor/{code}", dict(diagnosis="Pneumonia", meds="Azithromycin 500 mg", followup_date="", followup="", do_text="", avoid_text="", care=""))
ck("note page shows the admit card", b"Refer for admission" in D.get(f"/doctor/{code}").data)
ck("other doctor cannot refer", post(D2, f"/doctor/{code}/refer-admit", dict(ward="General ward", type="Urgent", reason="pneumonia")).status_code == 404)
ck("patient cannot refer", post(P, f"/doctor/{code}/refer-admit", dict(ward="General ward", type="Urgent", reason="x y z")).status_code in (302, 403))
ck("bad ward refused", b"Choose the ward" in post(D, f"/doctor/{code}/refer-admit", dict(ward="Moon", type="Urgent", reason="pneumonia"), follow_redirects=True).data)
r = post(D, f"/doctor/{code}/refer-admit", dict(ward="General ward", type="Urgent", reason="Pneumonia, needs IV antibiotics"), follow_redirects=True)
ip = A.q("SELECT a.* FROM appts a JOIN ipd_info i ON i.appt_id=a.id WHERE i.ref_from=?", (code,), one=True)
ck("referral creates an IPD request", ip and ip["kind"] == "IPD" and ip["status"] == "booked" and ip["pid"] == pr["id"] and ip["doctor_id"] == 10 and ip["src"] == "referral", r.data[:200])
ck("patient got a message with the code", ip and A.q("SELECT 1 FROM notifications WHERE appt_code=? AND text LIKE '%advised admission%'", (ip["code"],), one=True) is not None)
n0 = A.q("SELECT * FROM ipd_notes WHERE appt_id=?", (ip["id"],), one=True)
ck("OPD diagnosis and medicines carried into the chart", n0 and n0["diagnosis"] == "Pneumonia" and "Azithromycin" in n0["findings"] and "Referred from OPD" in n0["findings"])
ck("second referral refused", b"already has an admission" in post(D, f"/doctor/{code}/refer-admit", dict(ward="General ward", type="Urgent", reason="again again"), follow_redirects=True).data)
ck("note page links to the request", ip["code"].encode() in D.get(f"/doctor/{code}").data)
rp = REC.get("/reception").get_data(as_text=True); ck("reception sees Doctor referral badge", "Doctor referral" in rp and ip["code"] in rp)
ck("admit needs bed + ID as before", b"photo ID" in post(REC, f"/reception/admit/{ip['code']}", dict(bed="G-1"), follow_redirects=True).data)
post(REC, f"/reception/admit/{ip['code']}", dict(bed="G-1", id_ok="1")); ck("reception admits referred patient", A.q("SELECT status,bed FROM appts WHERE id=?", (ip["id"],), one=True)["status"] == "admitted")
IC = ip["code"]
# ---------- 2. chart: doctor + nurse
ck("patient cannot open the chart", P.get(f"/ipd/{IC}/chart").status_code in (302, 403))
ck("reception cannot open the chart", REC.get(f"/ipd/{IC}/chart").status_code == 403)
ck("doctor opens the chart", b"Pneumonia" in D.get(f"/ipd/{IC}/chart").data)
ck("empty note refused", b"Write something" in post(D, f"/ipd/{IC}/note", dict(kind="round"), follow_redirects=True).data)
ck("future event time refused", b"future" in post(D, f"/ipd/{IC}/note", dict(kind="round", findings="x", event_ts="2999-01-01T10:00"), follow_redirects=True).data)
ck("bad note type refused", b"Choose the type" in post(D, f"/ipd/{IC}/note", dict(kind="zzz", findings="x"), follow_redirects=True).data)
r = post(D, f"/ipd/{IC}/note", dict(kind="round", diagnosis="Pneumonia", findings="Fever settling, SpO2 94%", meds="Inj. Ceftriaxone 1 g IV twice daily", tests=["Complete Blood Count (CBC)", "NoSuchTest"], plan="Monitor SpO2 4 hourly"), follow_redirects=True)
ck("note saved", b"Saved to the patient" in r.data and b"sent to the pharmacy" in r.data)
nr = A.q("SELECT * FROM notes WHERE appt_id=?", (ip["id"],), one=True); ck("medicine order reaches the pharmacy queue", nr and nr["approved"] == 1 and "Ceftriaxone" in nr["meds"] and IC in body(PH.get("/pharmacy")))
ck("test order reaches the lab, unknown test ignored", [s["test"] for s in A.q("SELECT test FROM samples WHERE appt_id=?", (ip["id"],))] == ["Complete Blood Count (CBC)"])
post(D, f"/ipd/{IC}/note", dict(kind="round", findings="Better", meds="Inj. Ceftriaxone 1 g IV twice daily\nTab. Paracetamol 500 mg SOS"))
ck("same medicine is not listed twice", A.q("SELECT meds FROM notes WHERE appt_id=?", (ip["id"],), one=True)["meds"].lower().count("ceftriaxone") == 1)
post(NU, f"/ipd/{IC}/note", dict(kind="admission", findings="Patient comfortable, took oral fluids", meds="Tab. Evil 100 mg", tests=["Hemoglobin"]))
nn = A.q("SELECT * FROM ipd_notes WHERE appt_id=? ORDER BY id DESC", (ip["id"],), one=True)
ck("nurse note is a nursing note only (no medicines, no tests)", nn["kind"] == "nursing" and "Evil" not in (nn["orders"] or "") and "Evil" not in A.q("SELECT meds FROM notes WHERE appt_id=?", (ip["id"],), one=True)["meds"] and not A.q("SELECT 1 FROM samples WHERE test='Hemoglobin' AND appt_id=?", (ip["id"],), one=True))
ck("timeline shows all entries", all(x in D.get(f"/ipd/{IC}/chart").get_data(as_text=True) for x in ("Fever settling", "Patient comfortable", "Nursing note")))
ck("vitals link works for IPD", NU.get(f"/vitals/{IC}").status_code == 200)
# ---------- 3. emergency direct admit (no booking, no doctor wait)
ck("patient cannot use /emergency", P.get("/emergency").status_code in (302, 403))
ck("form opens for reception", b"ADMIT NOW" in REC.get("/emergency").data)
E = dict(triage="Red", complaint="Road accident, unconscious", ward="ICU / HDU", bed="E-1", dept="Medicine", gender="Male", age_years="40", brought_by="108 ambulance", brought_phone="9811100001", first_aid="Oxygen started, IV line")
for n_, d_, msg in [("no triage", {**E, "triage": ""}, b"triage"), ("no complaint", {**E, "complaint": ""}, b"main problem"), ("no bed", {**E, "bed": ""}, b"bed or casualty"), ("bad phone", {**E, "brought_phone": "123"}, b"10 digits"), ("bad ward", {**E, "ward": "x"}, b"ward"), ("unknown UHID", {**E, "uhid": "SGMH-NOPE"}, b"No patient")]:
    r = post(REC, "/emergency", d_); ck("emergency refused: " + n_, r.status_code == 400 and msg.lower() in r.data.lower())
before = A.q("SELECT COUNT(*) n FROM appts WHERE kind='IPD'", one=True)["n"]
# the ICU unit has no mapped capacity; also fill General Ward to prove a full ward never blocks an emergency
A.q("UPDATE bed_inventory SET total_beds=1,occupied_beds=1 WHERE unit_name='General Ward'", commit=True)
r = post(REC, "/emergency", {**E, "ward": "General ward"}); ec = loc(r).split("/ipd/")[1].split("/")[0]
ea = A.appt_row(ec); ei = A.q("SELECT * FROM ipd_info WHERE appt_id=?", (ea["id"],), one=True)
ck("emergency admitted at once, even when the ward count is full", ea["status"] == "admitted" and ea["bed"] == "E-1" and ea["adm_type"] == "Emergency" and ea["src"] == "emergency")
ck("temporary identity, review pending, triage saved", ei["emergency"] == 1 and ei["review_pending"] == 1 and ei["id_pending"] == 1 and ei["triage"] == "Red")
ck("temporary UHID + Unknown name", ea["uhid"] and ea["pname"].startswith("Unknown male"))
ck("casualty entry stored with treatment already given", "Oxygen started" in (A.q("SELECT orders FROM ipd_notes WHERE appt_id=? AND kind='casualty'", (ea["id"],), one=True) or {"orders": ""})["orders"])
al = A.q("SELECT * FROM alerts WHERE appt_id=? AND kind='EMERGENCY_ADMIT'", (ea["id"],), one=True); ck("duty doctor alert is critical", al and al["level"] == "critical" and al["status"] == "open")
ck("duty doctor of that ward sees it on the alerts page", b"EMERGENCY ADMISSION" in staff("9000000041", "doc123").get("/alerts").data)
ck("relative got an SMS record", A.q("SELECT 1 FROM notifications WHERE appt_code=? AND phone='9811100001'", (ec,), one=True) is not None)
ck("audit has EMERGENCY_ADMIT", A.q("SELECT 1 FROM audit WHERE action='EMERGENCY_ADMIT' AND detail LIKE ?", (f"{ec}%",), one=True) is not None)
ck("board shows waiting emergency first", body(D.get("/ipd/board")).find(ec) != -1 and "review pending" in body(D.get("/ipd/board")))
ck("doctor page banner", b"waiting for a doctor" in D.get("/doctor").data)
ck("same patient cannot be admitted twice", b"already admitted" in post(REC, "/emergency", {**E, "uhid": ea["uhid"]}, follow_redirects=True).data)
ck("discharge blocked until a doctor has seen the patient", b"not been seen by a doctor" in post(REC, f"/reception/discharge/{ec}", follow_redirects=True).data and A.appt_row(ec)["status"] == "admitted")
# casualty doctor (a different doctor than the auto-picked one) files the first assessment, entering treatment given earlier
past = (A.now() - __import__("datetime").timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M")
r = post(D2, f"/ipd/{ec}/note", dict(kind="admission", diagnosis="Polytrauma, head injury", findings="GCS 8, left femur deformity", meds="Inj. Mannitol 100 ml IV", event_ts=past, take_over="1"), follow_redirects=True)
ei2 = A.q("SELECT * FROM ipd_info WHERE appt_id=?", (ea["id"],), one=True); ck("first doctor entry clears review pending", ei2["review_pending"] == 0 and "Dr" in (ei2["reviewed_by"] or "doctor"))
ck("emergency alert acknowledged", A.q("SELECT status FROM alerts WHERE id=?", (al["id"],), one=True)["status"] == "acknowledged")
ck("doctor can take over as treating doctor", A.appt_row(ec)["doctor_id"] == A.q("SELECT id FROM users WHERE phone='9000000042'", one=True)["id"])
ck("entry with an earlier event time is kept with both times", A.q("SELECT 1 FROM ipd_notes WHERE appt_id=? AND event_ts IS NOT NULL AND event_ts<ts", (ea["id"],), one=True) is not None)
ck("emergency medicines reach the pharmacy", ec in body(PH.get("/pharmacy")))
# ---------- 4. identify later / merge
ck("identify page opens for reception", b"Fill in the details" in REC.get(f"/ipd/{ec}/identify").data)
post(REC, f"/ipd/{ec}/identify", dict(name="Ramesh Kushwaha", gender="Male", age_years="42", phone="9811100002", id_ok="1"))
pe = A.q("SELECT * FROM patients WHERE id=?", (ea["pid"],), one=True); ck("details saved and identity confirmed", pe["name"] == "Ramesh Kushwaha" and A.q("SELECT id_pending FROM ipd_info WHERE appt_id=?", (ea["id"],), one=True)["id_pending"] == 0)
pr = A.q("SELECT * FROM patients WHERE id=?", (pr["id"],), one=True)
r = post(NU, "/emergency", {**E, "bed": "E-2", "brought_phone": ""}); e2 = loc(r).split("/ipd/")[1].split("/")[0]; a2 = A.appt_row(e2)
ck("merge needs ID tick", b"photo ID" in post(REC, f"/ipd/{e2}/identify", dict(real_uhid=pr["uhid"]), follow_redirects=True).data)
ck("cannot merge into a patient who is already admitted", b"already has an admission" in post(REC, f"/ipd/{e2}/identify", dict(real_uhid=pr["uhid"], id_ok="1"), follow_redirects=True).data)
sec = A.q("SELECT p.* FROM patients p WHERE p.uhid IS NOT NULL AND p.id NOT IN (?,?) AND p.active=1 AND p.src!='emergency' ORDER BY p.id LIMIT 1", (pr["id"], a2["pid"]), one=True)
if sec:
    post(REC, f"/ipd/{e2}/identify", dict(real_uhid=sec["uhid"], id_ok="1")); ck("merge links the treatment to the real record", A.appt_row(e2)["pid"] == sec["id"] and A.q("SELECT active FROM patients WHERE id=?", (a2["pid"],), one=True)["active"] == 0 and A.q("SELECT COUNT(*) n FROM ipd_notes WHERE appt_id=?", (a2["id"],), one=True)["n"] >= 1)
# ---------- 5. discharge summary
ck("only a doctor writes the summary", NU.get(f"/ipd/{IC}/summary/edit").status_code == 403)
pre = body(D.get(f"/ipd/{IC}/summary/edit")); ck("summary is prefilled from the chart", "Pneumonia" in pre and "Fever settling" in pre and "Ceftriaxone" in pre)
ck("final diagnosis required", b"Final diagnosis is required" in post(D, f"/ipd/{IC}/summary/edit", dict(final_dx=""), follow_redirects=True).data)
ck("approve needs a hospital course", b"hospital course" in post(D, f"/ipd/{IC}/summary/edit", dict(final_dx="Pneumonia", course="", approve="1"), follow_redirects=True).data)
post(D, f"/ipd/{IC}/summary/edit", dict(final_dx="Pneumonia", course="Treated with IV antibiotics, recovered.", meds_home="Tab. Azithromycin 500 mg x 3 days", advice="Rest, warm fluids", followup_date="2030-01-05", cond="Improved"))
ck("draft is hidden from the patient", P.get(f"/ipd/{IC}/summary", follow_redirects=True).status_code == 200 and b"not ready" in P.get(f"/ipd/{IC}/summary", follow_redirects=True).data)
ck("draft visible to staff with DRAFT mark", b"DRAFT" in D.get(f"/ipd/{IC}/summary").data)
os.environ["IPD_SUMMARY_REQUIRED"] = "1"; ck("discharge blocked without approved summary (when required)", b"approve the discharge summary" in post(REC, f"/reception/discharge/{IC}", follow_redirects=True).data and A.appt_row(IC)["status"] == "admitted"); del os.environ["IPD_SUMMARY_REQUIRED"]
post(D, f"/ipd/{IC}/summary/edit", dict(final_dx="Pneumonia", course="Treated with IV antibiotics, recovered.", meds_home="Tab. Azithromycin 500 mg x 3 days", advice="Rest, warm fluids", followup_date="2030-01-05", cond="Improved", approve="1"))
ck("patient is told", A.q("SELECT 1 FROM notifications WHERE appt_code=? AND text LIKE '%discharge summary%'", (IC,), one=True) is not None)
sv = body(P.get(f"/ipd/{IC}/summary")); ck("approved summary readable by the patient", "Treated with IV antibiotics" in sv and "2030-01-05" in sv and "DRAFT" not in sv)
ck("visit page links the summary", "/ipd/" + IC + "/summary" in body(P.get(f"/visit/{IC}")))
O = mk(); post(O, "/start", dict(name="Other Person", phone="9866600003")); o2 = re.search(r"<b>(\d{6})</b>", body(O.get("/start/verify"))).group(1); post(O, "/start/verify", dict(otp=o2))
ck("another patient cannot read it", b"Treated with IV" not in O.get(f"/ipd/{IC}/summary", follow_redirects=True).data)
ck("discharge now allowed, no warning", b"discharged" in post(REC, f"/reception/discharge/{IC}", follow_redirects=True).data and A.appt_row(IC)["status"] == "discharged")
ck("no notes after discharge", b"only while the patient is admitted" in post(D, f"/ipd/{IC}/note", dict(kind="round", findings="late"), follow_redirects=True).data)
ck("summary shows discharge time", "Discharged" in body(D.get(f"/ipd/{IC}/summary")) and "Not yet" not in body(D.get(f"/ipd/{IC}/summary")))
# ---------- 6. board for reception hides clinical columns
bb = body(REC.get("/ipd/board")); ck("reception board works without clinical links", "/chart" not in bb and "Vitals" not in bb)
ck("emergency discharge works once reviewed (no summary: soft note)", b"no approved discharge summary" in post(REC, f"/reception/discharge/{ec}", follow_redirects=True).data and A.appt_row(ec)["status"] == "discharged")
print(f"\n{ok} passed, {bad} failed")
