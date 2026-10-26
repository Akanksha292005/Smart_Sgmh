"""End-to-end checks for the patient journey: OTP start page -> welcome home -> details asked at the first booking -> history -> records.
Run:  python tests_flow.py   (throw-away database)"""
import os
os.environ.setdefault("STAFF_ID_CARD_REQUIRED","0")
import os, re, sys, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db"); os.environ["UPLOAD_DIR"] = tempfile.mkdtemp()
import app as A
app = A.app; P = F = 0
def ck(n, c, x=""):
    global P, F
    if c: P += 1
    else: F += 1; print("FAIL:", n, x)
def cl(lang="en"):
    c = app.test_client()
    with c.session_transaction() as s: s["csrf"] = "t"; s["lang"] = lang
    return c
def post(c, url, d=None, **kw):
    with c.session_transaction() as s: t = s.setdefault("csrf", "t")
    return c.post(url, data={"csrf": t, **(d or {})}, **kw)
txt = lambda r: r.get_data(as_text=True)
def otp_of(c): return re.search(r"letter-spacing:\.2em\">(\d{6})<|<b>(\d{6})</b>", txt(c.get("/start/verify"))).group(1) or re.search(r"<b>(\d{6})</b>", txt(c.get("/start/verify"))).group(1)
def gate(c, name, phone, pw=None, otp=None):
    r = post(c, "/start", dict(name=name, phone=phone)); assert r.status_code == 302, (r.status_code, txt(r)[:100])
    o = otp or otp_of(c); d = dict(otp=o); d.update(pw=pw) if pw else None
    return post(c, "/start/verify", d)

anon = cl()
ck("root -> the full website, no login wall", anon.get("/").headers["Location"].endswith("/app/"))
s = anon.get("/start"); ck("start page", s.status_code == 200 and "Send OTP" in txt(s) and "Mobile number" in txt(s))
ck("bad mobile", "valid 10-digit" in txt(post(cl(), "/start", dict(name="Asha", phone="12345"), follow_redirects=True)))
ck("new needs name", "enter your name" in txt(post(cl(), "/start", dict(name="", phone="9811100001"), follow_redirects=True)).lower())
ck("staff number refused", "hospital staff" in txt(post(cl(), "/start", dict(name="x y", phone="9000000010"), follow_redirects=True)))
# ---- new patient
c = cl(); post(c, "/start", dict(name="Asha Verma", phone="9811100001")); ok = otp_of(c)
r = post(c, "/start/verify", dict(otp="000000"), follow_redirects=True); ck("wrong otp", "not correct" in txt(r) or "Wrong OTP" in txt(r))
r = post(c, "/start/verify", dict(otp=ok)); ck("explicit login -> full website", r.status_code == 302 and r.headers["Location"].endswith("/app/"), r.headers.get("Location"))
h = txt(c.get("/home")); ck("welcome name", "Welcome," in h and "Asha Verma" in h); ck("first step shown", "book your first appointment" in h.lower())
u = A.q("SELECT * FROM users WHERE phone='9811100001'", one=True); pr = A.q("SELECT * FROM patients WHERE owner_id=?", (u["id"],), one=True)
ck("light account: no password, no UHID yet", u["pw"] == "!" and pr["uhid"] is None)
ck("/ -> full website when logged in", c.get("/").headers["Location"].endswith("/app/"))
ck("start redirects when logged in", c.get("/start").status_code == 302)
# ---- choose doctor -> details asked
doc = next(d for d in A.get_docs() if d["code"] != "leave"); nf = A.next_free(doc["id"])
bu = f"/book?doctor={doc['id']}&dept={doc['dept']}"
r = c.get(bu); ck("doctor chosen -> details page", r.status_code == 302 and "/register/details" in r.headers["Location"], r.headers.get("Location"))
d = c.get(r.headers["Location"]); dt = txt(d); ck("details page shows doctor + password", doc["name"] in dt and 'name="pw"' in dt and "Set your password" in dt)
form = dict(name="Asha Verma", gender="Female", age_years="34", village_ward="Civil Lines", district="Rewa", state="Madhya Pradesh", category="General", consent="1", lang="en", sms_ok="1", next=r.headers["Location"].split("next=")[1] and __import__("urllib.parse").parse.unquote(r.headers["Location"].split("next=")[1]), pid=str(pr["id"]))
bad = post(c, "/register/details", {**form, "pw": "abc", "pw2": "abc"}); ck("weak password rejected", bad.status_code == 400)
bad = post(c, "/register/details", {**form, "pw": "Secret123", "pw2": "Other1234"}); ck("mismatch rejected", bad.status_code == 400)
bad = post(c, "/register/details", {**form, "pw": "Secret123", "pw2": "Secret123", "consent": ""}); ck("consent needed", bad.status_code == 400)
ok = post(c, "/register/details", {**form, "pw": "Secret123", "pw2": "Secret123"}); ck("details saved -> back to booking", ok.status_code == 302 and "/book" in ok.headers["Location"], re.findall(r'class="f">(.*?)</div>', txt(ok)))
pr = A.q("SELECT * FROM patients WHERE id=?", (pr["id"],), one=True); u = A.q("SELECT * FROM users WHERE id=?", (u["id"],), one=True)
ck("UHID issued + password set", bool(pr["uhid"]) and u["pw"] != "!"); uhid = pr["uhid"]
b = txt(c.get(ok.headers["Location"], follow_redirects=True)); ck("booking continues with the same doctor", doc["name"] in b)
rb = post(c, "/book", dict(pid=pr["id"], dept=doc["dept"], doctor=doc["id"], date=nf["date"], slot=nf["slot"], reason="fever"))
ck("appointment booked", rb.status_code == 302 and "/appt/" in rb.headers["Location"], rb.headers.get("Location")); code = rb.headers["Location"].split("/appt/")[1]
ap = txt(c.get("/appt/" + code)); ck("appointment page has 'What happens next'", "What happens next" in ap)
h = txt(c.get("/home")); ck("home shows next appointment", "Your next appointment" in h and doc["name"] in h and uhid in h)
# ---- second login: OTP + password
c.get("/logout")
c2 = cl(); post(c2, "/start", dict(name="", phone="9811100001")); o = otp_of(c2)
ck("returning: password asked", 'name="pw"' in txt(c2.get("/start/verify")))
r = post(c2, "/start/verify", dict(otp=o), follow_redirects=True); ck("OTP alone is not enough", "not correct" in txt(r), txt(r)[-300:])
o = otp_of(c2) if False else None
post(c2, "/start/verify", dict(resend="1")); o = otp_of(c2)
r = post(c2, "/start/verify", dict(otp=o, pw="WrongPass1"), follow_redirects=True); ck("wrong password refused", "not correct" in txt(r))
post(c2, "/start/verify", dict(resend="1")); o = otp_of(c2)
r = post(c2, "/start/verify", dict(otp=o, pw="Secret123")); ck("OTP + password -> full website", r.status_code == 302 and r.headers["Location"].endswith("/app/"))
# lock after wrong tries
c3 = cl(); post(c3, "/start", dict(name="", phone="9811100001"))
for i in range(6):
    post(c3, "/start/verify", dict(otp="111111", pw="Nope12345"))
ck("account locked after repeated failures", "Too many wrong attempts" in txt(post(cl(), "/start", dict(name="", phone="9811100001"), follow_redirects=True)))
A.q("DELETE FROM authfail", commit=True)
# ---- visit done -> history + doctors consulted + doctor's earlier visit shown at booking
aid = A.q("SELECT id FROM appts WHERE code=?", (code,), one=True)["id"]
A.q("UPDATE appts SET status='seen' WHERE id=?", (aid,), commit=True)
A.q("INSERT OR REPLACE INTO notes(appt_id,diagnosis,meds,followup,approved) VALUES(?,?,?,?,1)", (aid, "Viral fever", "Paracetamol 500 mg", "After 5 days", ), commit=True)
A.q("INSERT INTO samples(appt_id,barcode,test,status,ts) VALUES(?,?,?,?,?)", (aid, "BC-T1", "CBC", "ready", A.ts()), commit=True)
h = txt(c2.get("/home")); ck("home: doctor consulted", doc["name"] in h and "Doctors you have consulted" in h)
ck("home: history shows date, finding, test, medicine", nf["date"] in h and "Viral fever" in h and "CBC" in h and "Paracetamol" in h)
ck("history page", "Viral fever" in txt(c2.get("/history")))
bk = txt(c2.get(f"/book?doctor={doc['id']}&dept={doc['dept']}&pid={pr['id']}")); ck("booking shows earlier visit with this doctor", "You have seen this doctor before" in bk and "Viral fever" in bk)
A.q("UPDATE notes SET approved=0 WHERE appt_id=?", (aid,), commit=True); ck("unapproved advice stays hidden", "Viral fever" not in txt(c2.get("/home")))
# ---- records
pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
import io
def up(cx, data, name, title="Old prescription"): return post(cx, "/records", dict(title=title, pid=str(pr["id"]), file=(io.BytesIO(data), name)), content_type="multipart/form-data", follow_redirects=True)
ck("pdf uploaded", "Saved." in txt(up(c2, pdf, "rx.pdf")))
ck("exe rejected", "Only PDF, JPG or PNG" in txt(up(c2, b"MZ\x90\x00bad", "x.pdf")))
ck("too large rejected", "larger than 5 MB" in txt(up(c2, b"%PDF" + b"0" * (5 * 1024 * 1024 + 10), "big.pdf")))
rid = A.q("SELECT id FROM records", one=True)["id"]
ck("owner views file", c2.get(f"/records/{rid}/file").status_code == 200)
oth = cl(); post(oth, "/start", dict(name="Ravi Kumar", phone="9811100002")); gate_o = otp_of(oth); post(oth, "/start/verify", dict(otp=gate_o))
ck("other patient cannot open", oth.get(f"/records/{rid}/file").status_code == 404)
ck("other patient has empty home", doc["name"] not in txt(oth.get("/home")))
ck("anonymous redirected", cl().get(f"/records/{rid}/file").status_code == 302)
dr = cl(); post(dr, "/login", dict(phone="9000000041", pw="doc123")); ck("doctor can open record", dr.get(f"/records/{rid}/file").status_code == 200)
dphone = A.q("SELECT phone FROM users WHERE id=?", (doc["id"],), one=True)["phone"]; own = cl(); post(own, "/login", dict(phone=dphone, pw="doc123"))
dres = own.get("/doctor/" + code); ck("doctor's note page lists the patient's records", dres.status_code == 200 and "Old prescription" in txt(dres), dres.status_code)
ck("other patient cannot delete", post(oth, f"/records/{rid}/delete").status_code == 404)
post(c2, f"/records/{rid}/delete"); ck("owner deletes", A.q("SELECT COUNT(*) n FROM records", one=True)["n"] == 0)
# ---- old doors closed
r = post(cl(), "/login", dict(phone="9811100001", pw="Secret123")); ck("patient password-only login blocked", r.status_code == 302 and r.headers["Location"].endswith("/start"))
ck("api login blocked for patient", app.test_client().post("/api/v1/login", json=dict(phone="9811100001", password="Secret123")).status_code == 403)
ck("me-token for session patient", c2.get("/api/v1/me-token").status_code == 200 and cl().get("/api/v1/me-token").status_code == 401)
rec = cl(); ck("staff login still works", post(rec, "/login", dict(phone="9000000010", pw="rec123")).status_code == 302)
ck("demo patient: OTP + password", gate(cl(), "", "9000000001", pw="pat123").headers["Location"].endswith("/app/"))
# ---- login only when needed: the website is open, booking / personal data ask for login and bring the patient back
pub = cl()
for u in ("/opd", "/ipd", "/doctors", "/blood-bank", "/navigate", "/workflow", "/departments", "/help", "/assistant", "/track"):
    ck("public without login: " + u, pub.get(u).status_code == 200, pub.get(u).status_code)
o = txt(pub.get("/opd")); ck("OPD hub: doctors with Book OPD, no IPD buttons", "Choose your doctor" in o and "Book OPD" in o and "/admit?dept" not in o)
ck("OPD hub filters by department", doc["name"] in txt(cl().get("/opd?dept=" + doc["dept"])))
for u in ("/book", "/records", "/history", "/mine", "/family", "/reports", "/home"):
    r = cl().get(u); ck("personal page asks for login: " + u, r.status_code == 302 and r.headers["Location"].endswith("/start"), (r.status_code, r.headers.get("Location")))
bk = cl(); r = bk.get(f"/book?doctor={doc['id']}&dept={doc['dept']}"); ck("Book remembers the doctor through login", r.status_code == 302 and r.headers["Location"].endswith("/start"))
post(bk, "/start", dict(name="Geeta Rani", phone="9811100055")); r = post(bk, "/start/verify", dict(otp=otp_of(bk)))
ck("after login the patient returns to the booking (then registration details)", r.status_code == 302 and f"/book?doctor={doc['id']}" in r.headers["Location"], r.headers.get("Location"))
print("PASS", P, "FAIL", F); sys.exit(1 if F else 0)
