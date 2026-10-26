"""Staff ID-card login tests (card check ON). Run: python tests_staffauth.py (throw-away database)."""
import os, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "staffauth_test.db"); os.environ["STAFF_ID_CARD_REQUIRED"] = "1"
import app as A

passed = failed = 0
def ck(name, cond, detail=""):
    global passed, failed
    if cond: passed += 1
    else: failed += 1; print("FAIL:", name, detail)

def web(phone, pw, card=None):
    c = A.app.test_client(); c.get("/login")
    with c.session_transaction() as s: s["csrf"] = "t"
    d = {"phone": phone, "pw": pw, "csrf": "t"}
    if card is not None: d["card"] = card
    r = c.post("/login", data=d); return c, r
def inside(c, url="/doctor"): return c.get(url).status_code == 200
def uid(phone): return A.q("SELECT id FROM users WHERE phone=?", (phone,), one=True)["id"]

DOC, DOC2, ADM, PAT = "9000000041", "9000000051", "9000000000", "9000000001"
doc_card = A.issue_card(uid(DOC), "test"); doc2_card = A.issue_card(uid(DOC2), "test"); adm_card = A.issue_card(uid(ADM), "test")

# --- the card is required
c, r = web(DOC, "doc123"); ck("password only: no card field -> refused", not inside(c))
c, r = web(DOC, "doc123", ""); ck("password + empty card -> refused", not inside(c))
c, r = web(DOC, "doc123", "SGMH-DR-0006-AAAAAAAAAA"); ck("password + wrong secret -> refused", not inside(c))
c, r = web(DOC, "doc123", "random text"); ck("password + junk card -> refused", not inside(c))
c, r = web(DOC, "wrongpw", doc_card); ck("right card + wrong password -> refused", not inside(c))
A.q("DELETE FROM staff_authfail", commit=True)  # 5 failures above rightly locked this phone; clear it
c, r = web(DOC, "doc123", doc_card); ck("password + own ID card -> doctor signed in", inside(c), r.status_code)
c, r = web(DOC, "doc123", doc_card.lower()); ck("card typed in lower case still works", inside(c))

# --- the card is tied to ONE person
c, r = web(DOC2, "doc123", doc_card); ck("doctor B with doctor A's card -> refused", not inside(c))
c, r = web(DOC, "doc123", doc2_card); ck("doctor A with doctor B's card -> refused", not inside(c))
last = A.q("SELECT detail FROM audit WHERE action='STAFF_LOGIN_FAILED' ORDER BY id DESC LIMIT 1", one=True)["detail"]
ck("failed login is in the audit log with the reason", "CARD_OF_ANOTHER_USER" in last, last)
ck("secret is stored only as a hash", all(doc_card.rsplit("-", 1)[1] not in (r["secret_hash"] or "") for r in A.q("SELECT secret_hash FROM staff_cards")))

# --- only patients use OTP: a patient cannot become staff
c, r = web(PAT, "pat123", doc_card); ck("patient phone+password at staff login -> sent to OTP page", r.status_code == 302 and "/start" in r.headers["Location"])
ck("patient cannot open doctor page", not inside(c)); ck("patient cannot open admin cards", c.get("/admin/cards").status_code in (302, 403))
for role_phone in ("9000000010", "9000000020", "9000000030", "9000000060"):
    c, r = web(role_phone, {"9000000010": "rec123", "9000000020": "lab123", "9000000030": "ph123", "9000000060": "nurse123"}[role_phone])
    ck(f"{role_phone} (no card issued) refused", c.get("/doctor").status_code != 200 and c.get("/lab").status_code != 200 and c.get("/pharmacy").status_code != 200)

# --- demo shortcuts cannot bypass the card
c = A.app.test_client(); c.get("/tour/as/doctor"); ck("demo role switcher cannot make a doctor", not inside(c))
c = A.app.test_client(); c.get("/demo/start"); ck("demo start cannot make a nurse", c.get("/demo").status_code != 200)

# --- lock after repeated failures
for i in range(5): web(DOC2, "doc123", "SGMH-DR-0012-WRONGWRONG")
c, r = web(DOC2, "doc123", doc2_card); ck("locked after 5 failures, even with the right card", not inside(c))
A.q("DELETE FROM staff_authfail", commit=True)
c, r = web(DOC2, "doc123", doc2_card); ck("works again after the lock is cleared", inside(c))

# --- admin: issue, replace, revoke
cd, _ = web(DOC, "doc123", doc_card)
ca, _ = web(ADM, "admin123", adm_card); ck("admin signs in with admin card", inside(ca, "/admin/cards"))
ck("doctor cannot open the card admin page", cd.get("/admin/cards").status_code == 403)
with ca.session_transaction() as s: s["csrf"] = "t"
r = ca.post(f"/admin/cards/issue/{uid(DOC)}", data={"csrf": "t"}); ck("admin replaces doctor card; printable card shown", r.status_code == 200 and b"SGMH-DR-" in r.data and b"data:image/png" in r.data)
ck("doctor already signed in is signed out when the card is replaced", not inside(cd))
c, r = web(DOC, "doc123", doc_card); ck("OLD card no longer works", not inside(c))
new_card = A.issue_card(uid(DOC), "test"); c, r = web(DOC, "doc123", new_card); ck("NEW card works", inside(c))
with ca.session_transaction() as s: s["csrf"] = "t"
ca.post(f"/admin/cards/revoke/{uid(DOC)}", data={"csrf": "t"})
ck("revoked: signed-in doctor is cut off at once", not inside(c)); c2, r = web(DOC, "doc123", new_card); ck("revoked card cannot sign in", not inside(c2))
try: A.issue_card(uid(PAT), "test"); ck("cannot issue a staff card to a patient", False)
except ValueError: ck("cannot issue a staff card to a patient", True)

# --- REST API (used by the React staff page) follows the same rule
A.q("DELETE FROM staff_authfail", commit=True); A.issue_card(uid(DOC), "test"); k = A.issue_card(uid(DOC), "test"); cl = A.app.test_client()
r = cl.post("/api/v1/login", json={"phone": DOC, "password": "doc123"}); ck("API: no card -> 401", r.status_code == 401)
r = cl.post("/api/v1/login", json={"phone": DOC, "password": "doc123", "card": doc2_card}); ck("API: another person's card -> 401", r.status_code == 401)
r = cl.post("/api/v1/login", json={"phone": DOC, "password": "doc123", "card": k}); ck("API: own card -> 200 + token", r.status_code == 200 and "token" in r.json)
tk = r.json["token"]; ck("API: token works", cl.get("/api/v1/beds").status_code == 200)
r = cl.post("/api/v1/login", json={"phone": PAT, "password": "pat123", "card": k}); ck("API: patient refused", r.status_code == 403)
ra = cl.post("/api/v1/login", json={"phone": ADM, "password": "admin123", "card": A.issue_card(uid(ADM), "test")}); atk = {"Authorization": "Bearer " + ra.json["token"]}
ck("API: admin token works before revoke", A.app.test_client().get("/api/v1/admin/stats", headers=atk).status_code != 401)
A.revoke_card(uid(ADM), "test")
r = A.app.test_client().get("/api/v1/admin/stats", headers=atk); ck("API: token of a revoked card stops working", r.status_code == 401, r.status_code)
ck("session key is not the old public default", A.app.secret_key != "dev-only-change-me" and len(A.app.secret_key) >= 32)
from itsdangerous import URLSafeTimedSerializer  # a cookie forged with the old public key must not be accepted
from flask.sessions import SecureCookieSessionInterface
forged = SecureCookieSessionInterface().get_signing_serializer(type("X", (), {"secret_key": "dev-only-change-me", "config": A.app.config, "permanent_session_lifetime": A.app.permanent_session_lifetime})()).dumps({"uid": uid(DOC), "role": "doctor", "name": "x", "card": "SGMH-DR-%04d" % uid(DOC), "cv": 1})
fc = A.app.test_client(); fc.set_cookie("session", forged); ck("forged session cookie (old public key) gets no access", fc.get("/doctor").status_code != 200)
print(f"{passed} passed, {failed} failed"); raise SystemExit(1 if failed else 0)
