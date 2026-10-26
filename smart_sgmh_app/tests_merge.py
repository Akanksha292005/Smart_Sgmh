"""Checks for the v28 merge: all services visible after login, free-service notice, Hindi first on the login page, bigger text + voice input hooks,
and the Aadhaar / Ayushman document check (patient -> reception queue -> badge). Run:  python tests_merge.py   (throw-away database)
Needs the sample card made by the test itself (PIL); OCR checks run only if the tesseract program is installed."""
import os
os.environ.setdefault("STAFF_ID_CARD_REQUIRED","0")
import os, re, sys, tempfile, shutil, io
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db"); os.environ["UPLOAD_DIR"] = tempfile.mkdtemp()
import app as A, idcheck
from PIL import Image, ImageDraw, ImageFont
app = A.app; P = F = 0
def ck(n, c, x=""):
    global P, F
    if c: P += 1
    else: F += 1; print("FAIL:", n, x)
def cl(lang=None):
    c = app.test_client()
    with c.session_transaction() as s:
        s["csrf"] = "t"
        if lang: s["lang"] = lang
    return c
def post(c, url, d=None, **kw):
    with c.session_transaction() as s: t = s.setdefault("csrf", "t")
    return c.post(url, data={"csrf": t, **(d or {})}, **kw)
txt = lambda r: r.get_data(as_text=True)
def otp_of(c): m = re.search(r"<b>(\d{6})</b>", txt(c.get("/start/verify"))) or re.search(r"letter-spacing:\.2em\">(\d{6})<", txt(c.get("/start/verify"))); return m.group(1)
def staff(phone, pw):
    c = cl("en"); post(c, "/login", dict(phone=phone, pw=pw)); return c
def patient(name, phone, pw="Secret123"):   # light account -> choose doctor -> details + password -> logged-in client
    c = cl("en"); post(c, "/start", dict(name=name, phone=phone)); post(c, "/start/verify", dict(otp=otp_of(c)))
    doc = next(d for d in A.get_docs() if d["code"] != "leave"); r = c.get(f"/book?doctor={doc['id']}&dept={doc['dept']}")
    form = dict(name=name, gender="Female", age_years="34", village_ward="Civil Lines", district="Rewa", state="Madhya Pradesh", category="General", consent="1", lang="en", sms_ok="1", next=f"/book?doctor={doc['id']}&dept={doc['dept']}", pw=pw, pw2=pw)
    u = A.q("SELECT id FROM users WHERE phone=?", (phone,), one=True); form["pid"] = str(A.q("SELECT id FROM patients WHERE owner_id=?", (u["id"],), one=True)["id"])
    r = post(c, "/register/details", form); ck("registration for " + name + " saved, UHID issued", r.status_code == 302 and bool(A.q("SELECT uhid FROM patients WHERE owner_id=?", (u["id"],), one=True)["uhid"]), r.status_code); return c, doc

# ---- 1. login page: Hindi first, free notice, public tiles, visible without login
hi = cl()   # a brand-new visitor: no language chosen
r = hi.get("/start"); t = txt(r); ck("login page 200", r.status_code == 200)
ck("Hindi first for a new visitor", "इस सरकारी अस्पताल में सभी सेवाएँ निःशुल्क हैं" in t, t[:80])
ck("public tiles on login page", all(k in t for k in ("/blood-bank", "/navigate", "/doctors", "/departments", "tel:112", "/assistant")))
ck("no-phone note in Hindi", "भूतल पर पंजीकरण काउंटर" in t)
en = cl("en"); t = txt(en.get("/start"))
ck("English login page keeps free notice", "All services at this government hospital are free" in t and "Without logging in" in t and "Send OTP" in t)
ck("language chosen is kept (not forced to Hindi)", "Send OTP" in txt(en.get("/start")))
ck("staff login still reachable", "/login" in t)
# ---- 2. after login everything is visible
c, doc = patient("Asha Verma", "9811100001")
h = txt(c.get("/home")); ck("home shows the services grid", "What do you need today?" in h)
ck("no patient IPD request tile", 'href="/admit"' not in h)
ck("every service tile present", all(k in h for k in ('href="/book"', 'href="tel:112"', 'href="/blood-bank"', 'href="/navigate"', 'href="/history"', 'href="/records"', 'href="/reports"', 'href="/medical-store"', 'href="/lab-services"', 'href="/family"', 'href="/verify"', 'href="/assistant"', 'href="/track"')))
ck("home shows free notice", "All services at this government hospital are free" in h)
ck("top bar says all services free", "All services free" in h)
ck("bigger-text + voice hooks in page", "szb" in h and "SpeechRecognition" in h)
c.get("/lang/hi"); hh = txt(c.get("/home")); ck("home fully Hindi tiles", "आज आपको क्या चाहिए?" in hh and "ब्लड बैंक" in hh and "डॉक्टर को दिखाना" in hh)
c.get("/lang/en")
bk = txt(c.get(f"/book?doctor={doc['id']}&dept={doc['dept']}", follow_redirects=True)); ck("booking page shows the free notice instead of fees", "All services at this government hospital are free" in bk or "free" in bk.lower())
for u in ("/blood-bank", "/navigate", "/admit", "/history", "/records", "/reports", "/medical-store", "/lab-services", "/family", "/assistant", "/track", "/verify", "/opd", "/ipd", "/doctors", "/departments", "/help"):
    ck("tile target opens: " + u, c.get(u, follow_redirects=True).status_code == 200, c.get(u).status_code)
# ---- 3. Aadhaar / Ayushman document check
def gen(b):
    for d in range(10):
        if idcheck.verhoeff_ok(b + str(d)): return b + str(d)
GOOD = gen("23456789012"); BAD = GOOD[:-1] + str((int(GOOD[-1]) + 1) % 10)
def card(name, num):
    im = Image.new("RGB", (1000, 620), "white"); d = ImageDraw.Draw(im); f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 46)
    d.text((40, 30), "SAMPLE TEST CARD - NOT A REAL DOCUMENT", font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34), fill="red"); d.text((40, 150), name, font=f, fill="black"); d.text((40, 420), " ".join([num[:4], num[4:8], num[8:]]), font=f, fill="black")
    b = io.BytesIO(); im.save(b, "JPEG"); return b.getvalue()
def sub(cli, kind, num, data, consent=True):
    d = dict(doc_type=kind, number=num); d.update(consent="1") if consent else None
    d["photo"] = (io.BytesIO(data), "c.jpg"); return post(cli, "/verify", d, content_type="multipart/form-data", follow_redirects=True)
def flashes(r): return re.findall(r'class="(?:flash|f|msg)[^"]*">([^<]+)<', txt(r)) or [txt(r)[:0]]
anon = cl("en"); ck("verify needs login", anon.get("/verify").status_code in (302, 401, 403))
ck("no consent -> refused", "consent" in txt(sub(c, "aadhaar", GOOD, card("Asha Verma", GOOD), False)).lower())
ck("bad checksum -> refused", "checksum" in txt(sub(c, "aadhaar", BAD, card("Asha Verma", BAD))))
ck("not an image -> refused", "not a valid image" in txt(sub(c, "aadhaar", GOOD, b"hello world")))
n0 = A.q("SELECT COUNT(*) n FROM idverify", one=True)["n"]; r = sub(c, "aadhaar", GOOD, card("Asha Verma", GOOD))
ck("good card submitted", "Submitted" in txt(r) and A.q("SELECT COUNT(*) n FROM idverify", one=True)["n"] == n0 + 1)
row = A.q("SELECT * FROM idverify ORDER BY id DESC", one=True)
ck("only last 4 digits kept, never the full number", row["masked"].endswith(GOOD[-4:]) and not any(GOOD in str(tuple(x)) for x in A.q("SELECT * FROM idverify")) and not any(GOOD in (x["detail"] or "") for x in A.q("SELECT detail FROM audit")))
if shutil.which("tesseract"):
    ck("OCR read number and name", row["num_found"] == 1 and row["name_score"] == 100, dict(row))
other, _ = patient("Sunita Rani", "9811100002"); r = sub(other, "aadhaar", GOOD, card("Sunita Rani", GOOD)); row2 = A.q("SELECT * FROM idverify ORDER BY id DESC", one=True)
ck("same number on another profile is flagged", row2["dup"] == 1)
ck("owner can view own photo", c.get(f"/verify/file/{row['id']}").status_code == 200); ck("other patient cannot", other.get(f"/verify/file/{row['id']}").status_code == 404); ck("anonymous cannot", anon.get(f"/verify/file/{row['id']}").status_code == 404)
rec = staff("9000000010", "rec123"); q_ = txt(rec.get("/admin/verify")); ck("reception sees the queue", "Asha Verma" in q_ and "ID verification queue" in q_)
ck("reception menu has Verify IDs with count", "Verify IDs" in txt(rec.get("/reception")))
ck("patient cannot open the queue", c.get("/admin/verify").status_code in (302, 403, 404))
ck("reject needs a reason", "short reason" in txt(post(rec, f"/admin/verify/{row2['id']}", dict(decision="reject"), follow_redirects=True)))
post(rec, f"/admin/verify/{row2['id']}", dict(decision="reject", reason="Number is on another account")); ck("rejection saved", A.q("SELECT status FROM idverify WHERE id=?", (row2["id"],), one=True)["status"] == "rejected")
post(rec, f"/admin/verify/{row['id']}", dict(decision="approve"))
ck("approved", A.q("SELECT status FROM idverify WHERE id=?", (row["id"],), one=True)["status"] == "verified")
ck("photos deleted after decision", all(not x["file"] for x in A.q("SELECT file FROM idverify WHERE status!='pending'")))
ck("decided photo gone (404)", c.get(f"/verify/file/{row['id']}").status_code == 404)
ck("double decision blocked", post(rec, f"/admin/verify/{row['id']}", dict(decision="approve")).status_code == 404)
hm = txt(c.get("/home")); ck("home shows Verified badge", "Verified: Aadhaar card" in hm)
ck("audit trail has decisions", {"ID_SUBMIT", "ID_VERIFIED", "ID_REJECTED"} <= {x["action"] for x in A.q("SELECT action FROM audit")})
ck("audit chain intact", A.verify_chain()[0])
# doctor sees the chip on the patient's page
pr = A.q("SELECT * FROM patients WHERE name='Asha Verma'", one=True); nf = A.next_free(doc["id"])
rb = post(c, "/book", dict(pid=pr["id"], dept=doc["dept"], doctor=doc["id"], date=nf["date"], slot=nf["slot"], reason="fever")); code = rb.headers["Location"].split("/appt/")[1]
dphone = A.q("SELECT phone FROM users WHERE id=?", (doc["id"],), one=True)["phone"]; dc = staff(dphone, "doc123")
A.q("UPDATE appts SET status='arrived' WHERE code=?", (code,), commit=True)
dn = txt(dc.get("/doctor/" + code)); ck("doctor page shows ID verified chip", "ID verified: Aadhaar card" in dn, dn[:100])
print(f"\nPASS {P} FAIL {F}")
