"""Recall (doctor), Flag (pharmacist) and lab PDF upload. Run: python tests_rx_controls.py (throw-away database)."""
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
P = mk(); post(P, "/start", dict(name="Rx Test", phone="9866600001")); o = re.search(r"<b>(\d{6})</b>", body(P.get("/start/verify"))).group(1); post(P, "/start/verify", dict(otp=o))
pr = A.q("SELECT * FROM patients WHERE owner_id=(SELECT id FROM users WHERE phone='9866600001')", one=True)
loc = P.get("/book?dept=Cardiology&doctor=10").headers["Location"]; nxt = __import__("urllib.parse").parse.unquote(loc.split("next=")[1])
post(P, "/register/details", dict(name="Rx Test", gender="Male", age_years="40", village_ward="X", district="Rewa", state="MP", category="General", consent="1", lang="en", next=nxt, pid=str(pr["id"]), pw="Secret123", pw2="Secret123"))
nf = A.next_free(10); r = post(P, "/book", dict(pid=pr["id"], dept="Cardiology", doctor=10, date=nf["date"], slot=nf["slot"], reason="fever")); code = r.headers["Location"].split("/appt/")[1]
aid = A.q("SELECT id FROM appts WHERE code=?", (code,), one=True)["id"]
D = staff("9000000045", "doc123"); PH = staff("9000000030", "ph123"); L = staff("9000000020", "lab123")
post(D, f"/doctor/{code}", dict(diagnosis="Viral fever", meds="Paracetamol 500 mg twice daily", followup_date="", followup="", do_text="", avoid_text="", care="", tests=["Complete Blood Count (CBC)"]))
# --- recall ---
ck("recall before approval refused", b"Only an approved" in post(D, f"/doctor/{code}/recall", dict(reason="x y z"), follow_redirects=True).data)
post(D, f"/doctor/{code}/approve")
ck("approved note shows Recall button", b"Recall prescription" in D.get(f"/doctor/{code}").data)
ck("pharmacy sees it", code in body(PH.get("/pharmacy")))
ck("recall needs a reason", b"reason for recalling" in post(D, f"/doctor/{code}/recall", dict(reason=""), follow_redirects=True).data)
D2 = staff("9000000042", "doc123") if A.q("SELECT 1 FROM users WHERE phone='9000000042'", one=True) else None
if D2: ck("other doctor cannot recall", post(D2, f"/doctor/{code}/recall", dict(reason="abcd")).status_code == 404)
# --- flag ---
ck("flag needs approved rx", b"No approved prescription" in post(PH, "/pharmacy/flag", dict(code="AP-NOPE", reason="Other"), follow_redirects=True).data)
r = post(PH, "/pharmacy/flag", dict(code=code, reason="Doctor says he/she did not write this", note="caller unsure"), follow_redirects=True); ck("flag accepted", b"Flagged. Dispensing is paused" in r.data)
ck("pharmacy list shows FLAGGED, no dispense button", b"FLAGGED" in PH.get("/pharmacy").data)
r = post(PH, "/pharmacy/verify", dict(code=code, batch="B4001"), follow_redirects=True); ck("verify blocked while flagged", b"FLAGGED by the pharmacy" in r.data, body(r)[:0])
ck("mark-all-dispensed blocked while flagged", b"FLAGGED" in post(PH, f"/pharmacy/dispense/{aid}", follow_redirects=True).data)
ck("doctor sees flag + confirm button", b"Pharmacy flagged this prescription" in D.get(f"/doctor/{code}").data and b"I wrote this" in D.get(f"/doctor/{code}").data)
ck("doctor/nurse alert exists (critical)", A.q("SELECT 1 FROM alerts WHERE appt_id=? AND kind='RX_FLAGGED' AND level='critical' AND status='open'", (aid,), one=True) is not None)
ck("patient told calmly", b"paused your medicines" in P.get("/notifications").data)
ck("non-pharmacy cannot flag", post(L, "/pharmacy/flag", dict(code=code, reason="Other")).status_code == 403)
ck("patient cannot confirm", post(P, f"/doctor/{code}/confirm-rx").status_code == 403)
ck("doctor confirms genuine", b"Confirmed" in post(D, f"/doctor/{code}/confirm-rx", follow_redirects=True).data)
ck("flag alert closed", A.q("SELECT status FROM alerts WHERE appt_id=? AND kind='RX_FLAGGED'", (aid,), one=True)["status"] == "closed")
r = post(PH, "/pharmacy/verify", dict(code=code, batch="B4001"), follow_redirects=True); ck("dispense works after confirm", b"OK: Paracetamol" in r.data)
# --- recall after partial dispense ---
r = post(D, f"/doctor/{code}/recall", dict(reason="Wrong dose written"), follow_redirects=True); ck("recall accepted", b"Prescription recalled" in r.data)
ck("note shows Recalled banner", b"Recalled" in D.get(f"/doctor/{code}").data and b"Wrong dose written" in D.get(f"/doctor/{code}").data)
ck("pharmacy queue no longer has it", code not in body(PH.get("/pharmacy")).split("Batch check")[0])
r = post(PH, "/pharmacy/verify", dict(code=code, batch="B4001"), follow_redirects=True); ck("dispense blocked after recall", b"RECALLED" in r.data)
ck("flag refused after recall", b"No approved prescription" in post(PH, "/pharmacy/flag", dict(code=code, reason="Other"), follow_redirects=True).data)
ck("patient alerted about recall", b"WITHDRAWN" in P.get("/notifications").data)
ck("patient /rx hidden after recall", b"withdrawn" in P.get(f"/rx/{code}", follow_redirects=True).data.lower())
ck("recall alert is critical (medicine already given)", A.q("SELECT level FROM alerts WHERE appt_id=? AND kind='RX_RECALLED'", (aid,), one=True)["level"] == "critical")
ck("audit has recall+flag+confirm", all(A.q("SELECT 1 FROM audit WHERE action=?", (k,), one=True) for k in ("RX_RECALLED", "RX_FLAGGED", "RX_CONFIRMED")))
r = post(D, f"/doctor/{code}/approve", follow_redirects=True); ck("doctor can re-approve corrected rx", b"Recall prescription" in D.get(f"/doctor/{code}").data and A.q("SELECT recalled FROM notes WHERE appt_id=?", (aid,), one=True)["recalled"] == 0)
# --- PDF upload ---
sid = A.q("SELECT id,barcode FROM samples WHERE appt_id=? LIMIT 1", (aid,), one=True); bc = sid["barcode"]
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
def lab(data, name="r.pdf", result="", code_=code, barcode=bc):
    with L.session_transaction() as s: t = s.setdefault("csrf", "t")
    form = {"csrf": t, "code": code_, "barcode": barcode, "result": result}
    if data is not None: form["pdf"] = (io.BytesIO(data), name)
    return L.post("/lab/report", data=form, content_type="multipart/form-data", follow_redirects=True)
ck("nothing entered refused", b"Enter patient code" in lab(None).data)
ck("fake pdf refused", b"Only real PDF" in lab(b"MZ not a pdf").data)
ck("wrong extension refused", b"Only real PDF" in lab(PDF, "r.exe").data)
ck("script pdf refused", b"active content" in lab(b"%PDF-1.4 /JavaScript (app.alert(1))").data)
ck("too big refused", b"too large" in lab(b"%PDF-" + b"0" * (5 * 1024 * 1024 + 10)).data)
ck("no file stored so far", A.q("SELECT report_file FROM samples WHERE id=?", (sid["id"],), one=True)["report_file"] is None)
r = lab(PDF, result="Hb 12.5"); ck("PDF + text accepted", b"PDF attached" in r.data, body(r)[:0])
rf = A.q("SELECT report_file FROM samples WHERE id=?", (sid["id"],), one=True)["report_file"]; ck("file saved on disk", rf and os.path.isfile(os.path.join(A.LAB_ROOT, rf)))
g = P.get(f"/report-file/{sid['id']}"); ck("owner patient can open PDF", g.status_code == 200 and g.data.startswith(b"%PDF") and g.mimetype == "application/pdf" and "sandbox" in g.headers.get("Content-Security-Policy", ""))
ck("reports page links PDF", b"/report-file/" in P.get("/reports").data)
ck("doctor can open PDF", D.get(f"/report-file/{sid['id']}").status_code == 200)
P2 = mk(); post(P2, "/start", dict(name="Other Pt", phone="9866600002")); o2 = re.search(r"<b>(\d{6})</b>", body(P2.get("/start/verify"))).group(1); post(P2, "/start/verify", dict(otp=o2))
ck("other patient cannot open PDF", P2.get(f"/report-file/{sid['id']}").status_code == 403)
ck("anonymous cannot open PDF", mk().get(f"/report-file/{sid['id']}").status_code == 403)
ck("missing file 404", P.get("/report-file/99999").status_code == 404)
# wrong patient: blocked, file never stored
post(P2, "/start", dict(name="Other Pt", phone="9866600002"))
o_appt = A.q("SELECT code FROM appts WHERE code!=? LIMIT 1", (code,), one=True)
if o_appt:
    before = len(os.listdir(A.LAB_ROOT)); r = lab(PDF, result="x", code_=o_appt["code"])
    ck("wrong-patient report still blocked", b"BLOCKED" in r.data and len(os.listdir(A.LAB_ROOT)) == before)
ck("PDF-only report accepted", b"Report matched" in lab(PDF, result="").data)
print(f"\n{ok} passed, {bad} failed")
