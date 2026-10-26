"""SMS gateway for Smart SGMH: real OTP and (optional) notification SMS.

Only the Python standard library is used (no new pip package).

Choose ONE provider with environment variables:

  SMS_PROVIDER=msg91      MSG91_AUTHKEY, MSG91_TEMPLATE_ID  (OTP template approved on DLT)
  SMS_PROVIDER=fast2sms   FAST2SMS_KEY
                          FAST2SMS_ROUTE=otp (default, no DLT work on your side)  or  dlt
                          for route=dlt also: FAST2SMS_SENDER_ID, FAST2SMS_MESSAGE_ID (DLT template ID of the OTP message)
  SMS_PROVIDER=twilio     TWILIO_SID, TWILIO_TOKEN, and TWILIO_FROM (number)  or  TWILIO_MSG_SERVICE (MG...)
  (empty)                 no gateway: OTP_MODE=demo shows the OTP on screen (testing only)

India: every OTP / transactional SMS must use a DLT-registered sender ID and template (TRAI rule). MSG91 and
Fast2SMS explain the DLT steps in their dashboards; Twilio needs its own India approval.

Optional:
  SMS_OTP_TEXT   text sent by providers that send free text (Twilio). {otp} is replaced. Default below.
  SMS_NOTIFY=1   also send booking / registration messages by SMS (Twilio, or Fast2SMS route dlt_manual with
                 FAST2SMS_SENDER_ID + FAST2SMS_TEMPLATE_ID + FAST2SMS_ENTITY_ID). They are always saved in the
                 notifications table either way.
  SMS_TIMEOUT    seconds to wait for the gateway (default 10)

Nothing here ever logs an OTP or a full phone number.
"""
import os, json, base64, logging, threading
import urllib.request, urllib.parse, urllib.error

log = logging.getLogger("sms_gateway")

DEFAULT_OTP_TEXT = "{otp} is your OTP for SGMH Rewa Smart Hospital. It is valid for 10 minutes. Do not share it with anyone."


def provider():
    return (os.environ.get("SMS_PROVIDER") or "").strip().lower()


def _env(k):
    return (os.environ.get(k) or "").strip()


def _timeout():
    try: return max(3, int(os.environ.get("SMS_TIMEOUT", "10")))
    except ValueError: return 10


def missing_settings():
    """Names of the environment variables the chosen provider still needs (empty list = ready)."""
    p = provider()
    if p == "msg91": need = ["MSG91_AUTHKEY", "MSG91_TEMPLATE_ID"]
    elif p == "fast2sms":
        need = ["FAST2SMS_KEY"]
        if _env("FAST2SMS_ROUTE").lower() == "dlt": need += ["FAST2SMS_SENDER_ID", "FAST2SMS_MESSAGE_ID"]
    elif p == "twilio":
        need = ["TWILIO_SID", "TWILIO_TOKEN"]
        if not (_env("TWILIO_FROM") or _env("TWILIO_MSG_SERVICE")): need.append("TWILIO_FROM or TWILIO_MSG_SERVICE")
    else: return ["SMS_PROVIDER (msg91 | fast2sms | twilio)"]
    return [k for k in need if " or " in k or not _env(k)]


def configured():
    return provider() in ("msg91", "fast2sms", "twilio") and not missing_settings()


def _mask(phone):
    return phone[:2] + "XXXXXX" + phone[-2:] if len(phone or "") == 10 else "XXXX"


def _request(url, data=None, headers=None, method=None):
    """One HTTP call. Returns (status, parsed_json_or_text). Network errors raise OSError."""
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_timeout()) as r:
            body = r.read().decode("utf-8", "replace"); status = r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace"); status = e.code
    try: return status, json.loads(body)
    except ValueError: return status, body


# ---------------------------------------------------------------- providers
def _msg91_otp(phone, otp):
    q = urllib.parse.urlencode({"template_id": _env("MSG91_TEMPLATE_ID"), "mobile": "91" + phone, "authkey": _env("MSG91_AUTHKEY"), "otp": otp, "otp_expiry": 10})
    st, js = _request("https://control.msg91.com/api/v5/otp?" + q, data=b"{}", headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    ok = st == 200 and isinstance(js, dict) and js.get("type") == "success"
    return ok, "" if ok else f"msg91 {st} {(js.get('message') if isinstance(js, dict) else str(js))[:120]}"


def _fast2sms_call(payload):
    st, js = _request("https://www.fast2sms.com/dev/bulkV2", data=json.dumps(payload).encode(), headers={"authorization": _env("FAST2SMS_KEY"), "Content-Type": "application/json", "Cache-Control": "no-cache"}, method="POST")
    ok = st == 200 and isinstance(js, dict) and js.get("return") is True
    msg = js.get("message") if isinstance(js, dict) else str(js)
    return ok, "" if ok else f"fast2sms {st} {str(msg)[:120]}"


def _fast2sms_otp(phone, otp):
    if _env("FAST2SMS_ROUTE").lower() == "dlt":
        return _fast2sms_call({"route": "dlt", "sender_id": _env("FAST2SMS_SENDER_ID"), "message": _env("FAST2SMS_MESSAGE_ID"), "variables_values": otp, "numbers": phone, "flash": 0})
    return _fast2sms_call({"route": "otp", "variables_values": otp, "numbers": phone, "flash": 0})


def _twilio_text(phone, text):
    sid, tok = _env("TWILIO_SID"), _env("TWILIO_TOKEN")
    form = {"To": "+91" + phone, "Body": text}
    if _env("TWILIO_MSG_SERVICE"): form["MessagingServiceSid"] = _env("TWILIO_MSG_SERVICE")
    else: form["From"] = _env("TWILIO_FROM")
    auth = base64.b64encode(f"{sid}:{tok}".encode()).decode()
    st, js = _request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data=urllib.parse.urlencode(form).encode(), headers={"Authorization": "Basic " + auth, "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    ok = st in (200, 201) and isinstance(js, dict) and bool(js.get("sid"))
    return ok, "" if ok else f"twilio {st} {(js.get('message') if isinstance(js, dict) else str(js))[:120]}"


# ---------------------------------------------------------------- public API
def send_otp(phone, otp):
    """Send an OTP to a 10-digit Indian mobile. Returns (ok, error_for_the_server_log)."""
    if not configured(): return False, "gateway not configured: " + ", ".join(missing_settings())
    p = provider()
    try:
        if p == "msg91": ok, err = _msg91_otp(phone, otp)
        elif p == "fast2sms": ok, err = _fast2sms_otp(phone, otp)
        else: ok, err = _twilio_text(phone, (os.environ.get("SMS_OTP_TEXT") or DEFAULT_OTP_TEXT).replace("{otp}", otp))
    except (OSError, ValueError) as e:  # timeout, DNS, TLS, refused ...
        ok, err = False, f"{p} network error: {type(e).__name__}"
    if not ok: log.warning("OTP SMS to %s failed: %s", _mask(phone), err)
    return ok, err


def notify_enabled():
    return os.environ.get("SMS_NOTIFY", "0") == "1" and configured() and (provider() == "twilio" or (provider() == "fast2sms" and all(_env(k) for k in ("FAST2SMS_SENDER_ID", "FAST2SMS_TEMPLATE_ID", "FAST2SMS_ENTITY_ID"))))


def send_text(phone, text):
    """Notification SMS (blocking). Returns (ok, error)."""
    if not notify_enabled(): return False, "notifications by SMS are off"
    try:
        if provider() == "twilio": return _twilio_text(phone, text)
        return _fast2sms_call({"route": "dlt_manual", "sender_id": _env("FAST2SMS_SENDER_ID"), "message": text, "template_id": _env("FAST2SMS_TEMPLATE_ID"), "entity_id": _env("FAST2SMS_ENTITY_ID"), "numbers": phone, "flash": 0})
    except (OSError, ValueError) as e:
        return False, f"network error: {type(e).__name__}"


def send_text_async(phone, text):
    """Fire and forget, so a slow gateway never slows a booking page."""
    if not notify_enabled(): return
    def run():
        ok, err = send_text(phone, text)
        if not ok: log.warning("SMS to %s failed: %s", _mask(phone), err)
    threading.Thread(target=run, daemon=True).start()
