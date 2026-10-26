"""Checks for the SMS gateway (sms_gateway.py) and OTP delivery in OTP_MODE=sms. No real SMS is sent: the HTTP call is replaced.
Run:  python tests_sms.py   (throw-away database)"""
import os
os.environ.setdefault("STAFF_ID_CARD_REQUIRED","0")
import os, re, sys, tempfile, json, urllib.parse
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db"); os.environ["UPLOAD_DIR"] = tempfile.mkdtemp()
os.environ.update(SMS_PROVIDER="msg91", MSG91_AUTHKEY="KEY123", MSG91_TEMPLATE_ID="TPL9", OTP_PER_HOUR="3", OTP_COOLDOWN_SEC="30", OTP_PER_IP_HOUR="50")
os.environ.pop("OTP_MODE", None)
import sms_gateway as G
import app as A
app = A.app; P = F = 0
def ck(n, c, x=""):
    global P, F
    if c: P += 1
    else: F += 1; print("FAIL:", n, x)

CALLS = []; REPLY = [200, {"type": "success", "message": "ok"}]
def fake(url, data=None, headers=None, method=None):
    CALLS.append(dict(url=url, data=data, headers=headers or {}, method=method)); 
    if isinstance(REPLY[0], Exception): raise REPLY[0]
    return REPLY[0], REPLY[1]
G._request = fake

def cl():
    c = app.test_client()
    with c.session_transaction() as s: s["csrf"] = "t"; s["lang"] = "en"
    return c
def post(c, url, d=None, **kw): return c.post(url, data={"csrf": "t", **(d or {})}, **kw)
txt = lambda r: r.get_data(as_text=True)
def last_otp():
    q = urllib.parse.parse_qs(urllib.parse.urlparse(CALLS[-1]["url"]).query); return q["otp"][0]
def age_log():  # pretend the earlier OTPs were sent 5 minutes ago (skips the 30 s wait, still inside the 1 hour window)
    from datetime import timedelta
    A.q("UPDATE otp_log SET ts=?", ((A.now() - timedelta(minutes=5)).strftime(A.FMT),), commit=True)
def reset(): A.q("DELETE FROM otp_log", commit=True); CALLS.clear(); REPLY[:] = [200, {"type": "success", "message": "ok"}]

# ---------------------------------------------------------------- mode selection
import registration as R
ck("gateway configured", G.configured() and G.missing_settings() == [])
ck("mode becomes sms automatically", R.OTP_MODE == "sms", R.OTP_MODE)

# ---------------------------------------------------------------- provider calls (no network)
reset(); ok, err = G.send_otp("9811100001", "123456")
u = urllib.parse.urlparse(CALLS[0]["url"]); qs = urllib.parse.parse_qs(u.query)
ck("msg91 url", u.netloc == "control.msg91.com" and u.path == "/api/v5/otp", CALLS[0]["url"])
ck("msg91 params", qs["mobile"] == ["919811100001"] and qs["otp"] == ["123456"] and qs["template_id"] == ["TPL9"] and qs["authkey"] == ["KEY123"], qs)
ck("msg91 ok", ok is True and err == "")
reset(); REPLY[:] = [200, {"type": "error", "message": "IPBlocked"}]; ok, err = G.send_otp("9811100001", "123456")
ck("msg91 error -> False + reason", ok is False and "IPBlocked" in err and "123456" not in err and "9811100001" not in err, err)
reset(); REPLY[:] = [OSError("boom"), None]; ok, err = G.send_otp("9811100001", "123456")
ck("network error -> False, no crash", ok is False and "OSError" in err, err)

os.environ.update(SMS_PROVIDER="fast2sms", FAST2SMS_KEY="FK1")
reset(); REPLY[:] = [200, {"return": True, "request_id": "x", "message": ["sent"]}]; ok, err = G.send_otp("9811100001", "654321")
body = json.loads(CALLS[0]["data"])
ck("fast2sms otp route", ok and body == {"route": "otp", "variables_values": "654321", "numbers": "9811100001", "flash": 0} and CALLS[0]["headers"]["authorization"] == "FK1", body)
REPLY[:] = [200, {"return": False, "message": "Invalid Authentication"}]; ok, err = G.send_otp("9811100001", "1")
ck("fast2sms return=false -> fail", ok is False and "Invalid Authentication" in err)
os.environ.update(FAST2SMS_ROUTE="dlt")
ck("fast2sms dlt needs ids", set(G.missing_settings()) == {"FAST2SMS_SENDER_ID", "FAST2SMS_MESSAGE_ID"} and not G.configured())
os.environ.update(FAST2SMS_SENDER_ID="SGMHRW", FAST2SMS_MESSAGE_ID="1707"); reset(); REPLY[:] = [200, {"return": True}]; G.send_otp("9811100001", "111222")
body = json.loads(CALLS[0]["data"]); ck("fast2sms dlt payload", body["route"] == "dlt" and body["sender_id"] == "SGMHRW" and body["message"] == "1707" and body["variables_values"] == "111222", body)
os.environ.pop("FAST2SMS_ROUTE")

os.environ.update(SMS_PROVIDER="twilio", TWILIO_SID="ACabc", TWILIO_TOKEN="tok")
ck("twilio needs a sender", not G.configured() and any("TWILIO_FROM" in m for m in G.missing_settings()))
os.environ.update(TWILIO_FROM="+15005550006"); reset(); REPLY[:] = [201, {"sid": "SM1"}]; ok, err = G.send_otp("9811100001", "222333")
f = urllib.parse.parse_qs(CALLS[0]["data"].decode())
ck("twilio request", ok and "Accounts/ACabc/Messages.json" in CALLS[0]["url"] and f["To"] == ["+919811100001"] and "222333" in f["Body"][0] and f["From"] == ["+15005550006"] and CALLS[0]["headers"]["Authorization"].startswith("Basic "), f)
REPLY[:] = [400, {"message": "Invalid To"}]; ok, err = G.send_otp("9811100001", "1"); ck("twilio error", ok is False and "Invalid To" in err)
ck("notifications off by default", not G.notify_enabled() and G.send_text("9811100001", "hi")[0] is False)
os.environ["SMS_NOTIFY"] = "1"; ck("notifications on for twilio", G.notify_enabled()); os.environ.pop("SMS_NOTIFY")

# back to msg91 for the web tests
for k in ("TWILIO_SID", "TWILIO_TOKEN", "TWILIO_FROM", "FAST2SMS_KEY", "FAST2SMS_SENDER_ID", "FAST2SMS_MESSAGE_ID"): os.environ.pop(k, None)
os.environ["SMS_PROVIDER"] = "msg91"
os.environ["SMS_PROVIDER"] = ""; ck("no provider -> not configured", not G.configured() and G.send_otp("9811100001", "1")[0] is False)
os.environ["SMS_PROVIDER"] = "msg91"

# ---------------------------------------------------------------- login by SMS OTP (web)
reset(); c = cl()
r = post(c, "/start", dict(name="Asha Verma", phone="9811100001")); ck("start accepted", r.status_code == 302 and r.headers["Location"].endswith("/start/verify"), r.status_code)
ck("exactly one SMS sent to the right number", len(CALLS) == 1 and "mobile=919811100001" in CALLS[0]["url"])
otp = last_otp(); page = txt(c.get("/start/verify"))
ck("OTP is NOT shown on the page in sms mode", otp not in page and "Demo mode" not in page)
ck("page tells the patient SMS may take time", "SMS can take up to a minute" in page)
ck("OTP not stored in plain text", not any(otp == str(v) for row in A.q("SELECT * FROM otps") for v in tuple(row)))
r = post(c, "/start/verify", dict(otp="000000"), follow_redirects=True); ck("wrong OTP refused", "Wrong OTP" in txt(r) or "not correct" in txt(r))
r = post(c, "/start/verify", dict(otp=otp)); ck("right OTP logs in", r.status_code == 302 and c.get("/home").status_code == 200)

# ---------------------------------------------------------------- resend limits
reset(); c = cl(); post(c, "/start", dict(name="Ravi Kumar", phone="9811100002")); n = len(CALLS)
r = post(c, "/start/verify", dict(resend="1"), follow_redirects=True)
ck("resend inside 30 s is refused, no extra SMS", len(CALLS) == n and "wait" in txt(r).lower(), (len(CALLS), n))
age_log(); r = post(c, "/start/verify", dict(resend="1"), follow_redirects=True)
ck("resend after the wait sends a new SMS", len(CALLS) == n + 1 and "new OTP has been sent" in txt(r))
new = last_otp(); r = post(c, "/start/verify", dict(otp=new)); ck("the new OTP works", r.status_code == 302)
age_log(); c2 = cl(); post(c2, "/start", dict(name="Ravi Kumar", phone="9811100002"))   # 3rd OTP in the hour
age_log(); c3 = cl(); r = post(c3, "/start", dict(name="Ravi Kumar", phone="9811100002"), follow_redirects=True)
ck("4th OTP in an hour is refused", "Too many OTP requests" in txt(r) and len(CALLS) == n + 2, (len(CALLS), n))

# ---------------------------------------------------------------- gateway failure
reset(); REPLY[:] = [200, {"type": "error", "message": "no balance"}]; c = cl()
r = post(c, "/start", dict(name="Mohan Lal", phone="9811100003"), follow_redirects=True); t = txt(r)
ck("gateway failure: friendly message", "could not send the SMS" in t, t[:200])
ck("gateway failure: reason not shown to the patient", "no balance" not in t and "msg91" not in t.lower().replace("msg91_", ""))
ck("gateway failure: no OTP left in the database", A.q("SELECT COUNT(*) c FROM otps WHERE phone='9811100003'", one=True)["c"] == 0)
ck("gateway failure: patient stays on the first page", "Send OTP" in t)
ck("gateway failure: no account made", A.q("SELECT 1 FROM users WHERE phone='9811100003'", one=True) is None)

# ---------------------------------------------------------------- registration form uses the gateway too
reset(); GOOD = dict(name="Sita Devi", gender="Female", age_years="34", phone="9811100005", pw="Secret123", pw2="Secret123", village_ward="Ward 5, Rewa", district="Rewa", state="Madhya Pradesh",
                    category="BPL", sms_ok="1", consent="1", lang="en", em_name="Ram", em_phone="9811100006", em_rel="Spouse")
c = cl(); r = post(c, "/register", GOOD); ck("register -> verify page", r.status_code == 302 and r.headers["Location"].endswith("/register/verify"), r.status_code)
otp = last_otp(); ck("register: SMS sent to the mobile", "mobile=919811100005" in CALLS[0]["url"]); page = txt(c.get("/register/verify")); ck("register: OTP not shown", otp not in page)
r = post(c, "/register/verify", dict(otp=otp)); ck("register: right OTP finishes", r.status_code == 302 and A.q("SELECT 1 FROM users WHERE phone='9811100005'", one=True) is not None)
reset(); REPLY[:] = [200, {"type": "error", "message": "x"}]; c = cl(); r = post(c, "/register", {**GOOD, "phone": "9811100007"})
ck("register: gateway failure keeps the form, no crash", r.status_code == 503 and "could not send the SMS" in txt(r) and "Sita Devi" in txt(r), r.status_code)

# ---------------------------------------------------------------- Hindi messages
reset(); REPLY[:] = [200, {"type": "error", "message": "x"}]; c = cl()
with c.session_transaction() as s: s["lang"] = "hi"
r = post(c, "/start", dict(name="Mohan Lal", phone="9811100008"), follow_redirects=True)
ck("Hindi: failure message translated", "SMS नहीं भेजा जा सका" in txt(r), txt(r)[:100])

print(f"PASS {P} FAIL {F}"); sys.exit(1 if F else 0)
