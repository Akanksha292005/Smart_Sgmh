"""Staff never see patient booking buttons; patients and visitors still do; a doctor can admit only after the patient was checked in. Run: python tests_staff_ui.py"""
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
STAFF = {"doctor": D, "reception": REC, "nurse": NU, "lab": L, "pharmacy": PH, "admin": staff("9000000000", "admin123")}  # reuse the logged-in clients (a second login issues a new card)
BOOK = re.compile(r'href="(/book[^"]*|/family[^"]*)"')
def menu(h):
    m = re.search(r'<div class="lk">(.*?)</div>', h, re.S); return re.findall(r">([^<]+)</a>", m.group(1)) if m else []
PAGES = ["/opd", "/doctors", "/ipd", "/workflow", "/about", "/help", "/departments"]
# ---------- 1. staff: no Book / Family links on any public page, no OPD / Doctors / website in the menu
for role, c in STAFF.items():
    for p in PAGES:
        h = body(c.get(p, follow_redirects=True)); ck(f"{role}: no booking link on {p}", not BOOK.search(h), BOOK.findall(h)[:2])
    it = menu(body(c.get("/about")))
    ck(f"{role}: menu has no OPD / Doctors / Hospital website", not ({"OPD", "Doctors", "Hospital website"} & set(it)), it)
    ck(f"{role}: /book still refused", c.get("/book").status_code == 403)
# ---------- 2. patient and visitor still get booking
pub = mk()
for who, c in (("patient", P), ("visitor", pub)):
    ck(f"{who}: Book OPD buttons on /doctors", "Book OPD" in body(c.get("/doctors")))
    ck(f"{who}: Book by department on /opd", "Book by department" in body(c.get("/opd")))
    ck(f"{who}: menu has OPD and Doctors", {"OPD", "Doctors"} <= set(menu(body(c.get("/about")))))
# ---------- 3. staff still reach their own work
for p in ("/doctor", "/ipd/board", "/emergency", "/wardview", "/alerts"): ck(f"doctor can open {p}", D.get(p).status_code == 200)
# ---------- 4. doctor can admit only after check-in
post(D, f"/doctor/{code}", dict(diagnosis="Pneumonia", meds="Azithromycin 500 mg", followup_date="", followup="", do_text="", avoid_text="", care=""))
A.q("UPDATE appts SET status='booked',token=NULL WHERE code=?", (code,), commit=True)
n0 = A.q("SELECT COUNT(*) n FROM appts WHERE kind='IPD'", one=True)["n"]
r = post(D, f"/doctor/{code}/refer-admit", dict(ward="General ward", type="Urgent", reason="Pneumonia, needs IV antibiotics"), follow_redirects=True)
ck("booked-only patient: admission refused with a clear message", b"not been checked in" in r.data)
ck("booked-only patient: no IPD record created", A.q("SELECT COUNT(*) n FROM appts WHERE kind='IPD'", one=True)["n"] == n0)
ck("booked-only patient: admit form hidden on the note page", b"Not checked in yet" in D.get(f"/doctor/{code}").data and b"/refer-admit" not in D.get(f"/doctor/{code}").data)
A.q("UPDATE appts SET status='arrived',token=1 WHERE code=?", (code,), commit=True)
r = post(D, f"/doctor/{code}/refer-admit", dict(ward="General ward", type="Urgent", reason="Pneumonia, needs IV antibiotics"), follow_redirects=True)
ck("after check-in: admission is created", A.q("SELECT COUNT(*) n FROM appts WHERE kind='IPD'", one=True)["n"] == n0 + 1)
for who, c in (("patient", P), ("reception", REC), ("nurse", NU)):
    ck(f"{who} cannot use refer-admit", post(c, f"/doctor/{code}/refer-admit", dict(ward="General ward", type="Urgent", reason="x y z")).status_code in (302, 403))
ck("patient POST /admit creates nothing", (lambda n: (post(P, "/admit", dict(reason="fever")), A.q("SELECT COUNT(*) n FROM appts WHERE kind='IPD'", one=True)["n"] == n)[1])(A.q("SELECT COUNT(*) n FROM appts WHERE kind='IPD'", one=True)["n"]))
print(f"PASS {ok} FAIL {bad}")
