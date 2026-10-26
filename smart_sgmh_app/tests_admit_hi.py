"""Checks for: no direct IPD admission on the home pages, and Hindi + English on the admission pages.
Run:  python tests_admit_hi.py   (throw-away database)"""
import os, re, sys, tempfile
os.environ.setdefault("STAFF_ID_CARD_REQUIRED", "0")
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db"); os.environ["UPLOAD_DIR"] = tempfile.mkdtemp()
import app as A
app = A.app; P = F = 0
def ck(n, c, x=""):
    global P, F
    if c: P += 1
    else: F += 1; print("FAIL:", n, x)
DEV = re.compile(r"[\u0900-\u097f]")
def cl(lang="en", role=None, phone=None):
    c = app.test_client()
    with c.session_transaction() as s:
        s["csrf"] = "t"; s["lang"] = lang
        if role:
            u = A.q("SELECT * FROM users WHERE phone=?", (phone,), one=True)
            s.update(uid=u["id"], role=u["role"], name=u["name"], dept=u["dept"])
    return c
txt = lambda r: r.get_data(as_text=True)

# 1. patients cannot ask for an IPD bed themselves
for lang in ("en", "hi"):
    r = cl(lang, "patient", "9000000001").get("/admit"); ck("/admit redirects to the info page", r.status_code == 302 and r.headers["Location"].endswith("/ipd"))
    r = cl(lang, "patient", "9000000001").post("/admit", data={"csrf": "t"}); ck("POST /admit does not create an IPD request", r.status_code == 302)
ck("no IPD request row from a patient", A.q("SELECT COUNT(*) n FROM appts WHERE kind='IPD'", one=True)["n"] == 0)

# 2. patient and public menus: no IPD link in the main bar, info link kept in Services, wording says emergency
h = txt(cl("en", "patient", "9000000001").get("/home"))
ck("patient menu: no IPD link in the main bar", '<a href="/ipd">IPD</a>' not in h)
ck("patient menu: info page still reachable", 'href="/ipd">How admission works</a>' in h)
ck("top bar says emergency admission", "Emergency admission: 24x7" in h and "IPD admission: 24x7" not in h)
h = txt(cl("en").get("/doctors")); ck("public menu: no IPD link in the main bar", '<a href="/ipd">IPD</a>' not in h)
h = txt(cl("en", "doctor", "9000000041").get("/doctor")); ck("staff still see the IPD link", '<a href="/ipd">IPD</a>' in h)

# 3. Hindi on the admission-related pages
for url, role, phone, must in [
    ("/ipd", None, None, "डॉक्टर"), ("/opd", None, None, "भर्ती"),
    ("/emergency", "reception", "9000000010", "अभी भर्ती करें"), ("/ipd/board", "doctor", "9000000041", "IPD बोर्ड"),
    ("/wardview", "doctor", "9000000041", "निदान / कारण"), ("/beds", None, None, "यूनिट"), ("/alerts", "doctor", "9000000041", "कोई अलर्ट नहीं"),
    ("/privacy", None, None, "संपर्क:"), ("/navigate", None, None, "यह प्रोटोटाइप के लिए नमूना नक्शा है")]:
    c = cl("hi", role, phone); h = txt(c.get(url, follow_redirects=True))
    ck(f"hindi {url}", must in h, must)
    ck(f"english {url} stays English", must not in txt(cl("en", role, phone).get(url, follow_redirects=True)), must)
# flash message after the old /admit link, in Hindi
c = cl("hi", "patient", "9000000001"); c.get("/admit"); h = txt(c.get("/ipd")); ck("hindi flash after /admit", "डॉक्टर या इमरजेंसी टीम" in h)
# dynamic role sentence
c = cl("hi", "nurse", "9000000061" if A.q("SELECT 1 FROM users WHERE phone='9000000061'", one=True) else "9000000041")
h = txt(c.get("/book", follow_redirects=True)); ck("hindi 'logged in as' sentence", "के रूप में लॉग इन हैं" in h or "लॉग आउट" in h)
print("PASS", P, "FAIL", F); sys.exit(1 if F else 0)
