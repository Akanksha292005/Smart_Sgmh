"""Patient registration + smart booking for a GOVERNMENT hospital (SGMH Rewa).

What this module adds (modelled on the registration / booking flow of large private hospitals, but kept public-sector friendly):
  - Patient PROFILE with a Unique Health ID (UHID). One login can hold several profiles (self + family), so a son can book for his mother.
  - Registration with mobile OTP, full demographics, address, category (General / BPL / Ayushman PM-JAY ...), optional ABHA number, emergency contact, consent.
  - Smart booking: department hint from symptoms + age/sex, priority queue (senior citizen, pregnant, differently-abled, infant), busy-day indicator,
    duplicate-booking guard, documents-to-bring checklist, printable OPD slip, calendar (.ics), reschedule, cancel, feedback.
  - Walk-in registration at the reception counter (most government OPD patients do not book online) with duplicate-record warning.
  - Privacy: DPDP-style consent, need-to-know views per staff role, every staff view of a profile is written to the tamper-evident audit log,
    Aadhaar is NEVER stored (optional last 4 digits only).
SAMPLE / SIMULATED: SMS (kept in a notifications table; plug a real SMS gateway into sms() and deliver_otp()), fees (hospital decides at the counter).
"""
import os, re, hmac, hashlib, random, string, sqlite3
from datetime import datetime, timedelta, date
from urllib.parse import urlencode
from flask import request, session, flash, redirect, render_template, abort, Response, jsonify
from werkzeug.security import generate_password_hash as gph
from i18n import HI
import sms_gateway

CATEGORIES = ["General", "BPL", "Ayushman Bharat (PM-JAY)", "Other government scheme"]
CONDS = ["Diabetes", "High blood pressure", "Heart disease", "Asthma / COPD", "Kidney disease", "Epilepsy", "TB (past or current)", "Thyroid", "Cancer"]
BLOOD = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
ID_TYPES = ["Aadhaar", "Voter ID", "Driving licence", "Ration card", "PAN", "Other"]
RELATIONS = ["Father", "Mother", "Spouse", "Son", "Daughter", "Brother", "Sister", "Other"]
DISTRICTS = ["Rewa", "Satna", "Sidhi", "Singrauli", "Mauganj", "Maihar", "Shahdol", "Umaria", "Anuppur", "Katni", "Panna", "Chhatarpur", "Damoh", "Sagar", "Jabalpur", "Prayagraj", "Chitrakoot", "Banda"]
NAME_RE = re.compile(r"^[^\d<>{}\[\]@#$%^&*=+|\\/~`_;:!?\"]{2,60}$")
MOBILE_RE = re.compile(r"^[6-9]\d{9}$")
# sms: OTP is sent by SMS through sms_gateway.py (set SMS_PROVIDER + keys) | demo: OTP is shown on screen, testing only | off: no OTP step.
# If OTP_MODE is not set, it becomes "sms" when a gateway is configured and "demo" otherwise.
OTP_MODE = os.environ.get("OTP_MODE") or ("sms" if sms_gateway.configured() else "demo")
OTP_COOLDOWN_SEC = int(os.environ.get("OTP_COOLDOWN_SEC", "30"))   # minimum gap between two OTPs to the same number
OTP_PER_HOUR = int(os.environ.get("OTP_PER_HOUR", "5"))            # OTPs per mobile number per hour
OTP_PER_IP_HOUR = int(os.environ.get("OTP_PER_IP_HOUR", "30"))     # OTPs per device address per hour (stops SMS bombing)
if OTP_MODE == "sms" and not sms_gateway.configured():
    print("WARNING: OTP_MODE=sms but the SMS gateway is not ready. Missing:", ", ".join(sms_gateway.missing_settings()))
MAX_FAMILY = 8
MAX_UPCOMING = 10
FEE_NOTE = os.environ.get("OPD_FEE_NOTE", "OPD registration fee, if any, is paid at the hospital counter as per hospital rules. No online payment is taken here.")


def register(ns):
    app, q, db, now, ts, who, need, audit, code, event = (ns[k] for k in ("app", "q", "db", "now", "ts", "who", "need", "audit", "code", "event"))
    get_docs, slot_states, next_free, next_opd_day, default_date, red_flag, suggest, burl = (ns[k] for k in ("get_docs", "slot_states", "next_free", "next_opd_day", "default_date", "red_flag", "suggest", "burl"))
    appt_row, can_view, EMERG_MSG, opd_open = ns["appt_row"], ns["can_view"], ns["EMERG_MSG"], ns["opd_open"]
    from i18n_reg import REG_HI
    for k, v in REG_HI.items(): HI.setdefault(k, v)  # never overwrite an existing translation
    from i18n_ipd import IPD_HI
    for k, v in IPD_HI.items(): HI.setdefault(k, v)
    from i18n_admit import ADMIT_HI, PATTERNS as ADMIT_PAT
    for k, v in ADMIT_HI.items(): HI.setdefault(k, v)
    ns["PAT"].extend(ADMIT_PAT)

    from functools import wraps
    def pneed(f):  # logged-in PATIENT accounts only (admin may open staff pages, but has no patient profiles)
        @need("patient")
        @wraps(f)
        def w(*a, **k):
            if session.get("role") != "patient": abort(403)
            return f(*a, **k)
        return w

    # ------------------------------------------------------------------ small helpers
    def years_between(d0, d1): return d1.year - d0.year - ((d1.month, d1.day) < (d0.month, d0.day))

    def age_info(dob, age_years, asof):
        """(years, months) or (None, None). Works with exact DOB or with an approximate age typed by the patient."""
        t = now().date()
        try:
            if dob:
                d = date.fromisoformat(dob); return years_between(d, t), (t.year - d.year) * 12 + t.month - d.month - (t.day < d.day)
            if age_years is not None and str(age_years) != "":
                y = int(age_years) + (years_between(date.fromisoformat(asof), t) if asof else 0); return y, y * 12
        except (ValueError, TypeError): pass
        return None, None

    def keyget(r, *names):
        for n in names:
            try:
                if r[n] is not None: return r[n]
            except (KeyError, IndexError): pass
        return None

    def row_age(r): return age_info(keyget(r, "dob", "pdob"), keyget(r, "age_years", "page"), keyget(r, "age_asof", "pasof"))

    def pdesc(r):
        """'34 y · Male' from either a patients row or an appointment row."""
        y, m = row_age(r); g = keyget(r, "gender", "pgender") or ""
        a = "" if y is None else (f"{m} months" if y < 1 else f"{y} y")
        return " · ".join(x for x in (a, g) if x)

    def mask_phone(p): p = p or ""; return p[:2] + "XXXXXX" + p[-2:] if len(p) == 10 else ("-" if not p else "XXXX" + p[-4:])
    app.jinja_env.globals.update(pdesc=pdesc, mask_phone=mask_phone)

    def norm_phone(s):
        s = re.sub(r"\D", "", s or "")
        return s[2:] if len(s) == 12 and s.startswith("91") else s

    def prio_reasons(p, preg=False):
        y, m = row_age(p); out = []
        if y is not None and y >= 60: out.append("Senior citizen")
        if y is not None and y < 1: out.append("Infant (under 1 year)")
        if keyget(p, "disabled", "pdis"): out.append("Differently-abled")
        if preg: out.append("Pregnant woman")
        return out  # SAMPLE policy: the hospital decides the real priority rules

    def can_preg(p):
        y, _ = row_age(p); return (keyget(p, "gender", "pgender") == "Female") and y is not None and 12 <= y <= 55

    def docs_to_bring(p, referred=False, preg=False):
        y, _ = row_age(p); cat = keyget(p, "category", "pcat") or "General"
        L = ["Photo ID (Aadhaar, Voter ID, Driving licence or any government ID)", "Previous prescriptions, reports and X-rays, if any", "This slip or the QR code on your phone"]
        if cat.startswith("Ayushman"): L.insert(1, "Ayushman Bharat (PM-JAY) card or e-card")
        elif cat == "BPL": L.insert(1, "BPL card or ration card")
        elif cat.startswith("Other"): L.insert(1, "Scheme card (CGHS, ESI or other) with ID")
        if keyget(p, "abha"): L.append("ABHA number or ABHA card (optional)")
        if keyget(p, "disabled", "pdis"): L.append("Disability certificate or UDID card")
        if y is not None and y >= 60: L.append("Senior citizen: any age proof (you get priority in the queue)")
        if y is not None and y < 5: L.append("Child: immunisation (vaccination) card")
        if y is not None and y < 18: L.append("A parent or guardian must come with the child")
        if preg: L.append("Mother and Child Protection (MCP) card and earlier pregnancy reports")
        if referred: L.append("Referral slip from the referring hospital or health centre")
        return L
    def docs_to_bring_ipd(p, referred=False, preg=False):
        L = [x for x in docs_to_bring(p, referred, preg) if not x.startswith("This slip")]
        L.insert(1, "Doctor's admission advice or referral letter, if you have one")
        L += ["One attendant (family member) who stays with the patient, with the attendant's photo ID and mobile phone",
              "Regular medicines in their original strips, and a few clothes, a towel and toiletries", "Do not bring jewellery, cash or other valuables",
              "This request code or the QR code on your phone"]
        return L
    app.jinja_env.globals.update(docs_to_bring=docs_to_bring, docs_to_bring_ipd=docs_to_bring_ipd, prio_reasons=prio_reasons)

    # ------------------------------------------------------------------ SMS (simulated) and OTP
    def sms(phone, text, uid=None, appt_code=None):
        """Every message is saved in the notifications table (shown on /notifications). When SMS_NOTIFY=1 and a gateway is ready it is also sent by SMS."""
        if phone or uid: q("INSERT INTO notifications(user_id,appt_code,phone,ts,text) VALUES(?,?,?,?,?)", (uid, appt_code, phone, ts(), text), commit=True)
        if phone and MOBILE_RE.match(phone): sms_gateway.send_text_async(phone, text)

    def _h(phone, code_): return hmac.new(app.secret_key.encode(), f"{phone}|{code_}".encode(), hashlib.sha256).hexdigest()

    class OtpError(Exception):
        """Raised when an OTP could not be sent (too many requests, or the SMS gateway failed). str(e) is safe to show to the patient."""

    def deliver_otp(phone, otp):
        """demo: return the OTP so the page can show it (testing only). sms: send it through the gateway and return None. Raises OtpError if it could not be sent."""
        if OTP_MODE == "demo": return otp
        ok, err = sms_gateway.send_otp(phone, otp)
        if not ok:
            print("OTP SMS failed:", err)   # reason goes to the server log only
            raise OtpError("We could not send the SMS right now. Please try again in a minute, or ask the help desk.")
        return None

    def _otp_throttle(phone):
        """SMS costs money and can be abused, so limit how often OTPs are sent (applies in sms mode only)."""
        if OTP_MODE != "sms": return
        ip = (request.remote_addr or "")[:45]; n = now(); fmt = ns["FMT"]
        q("DELETE FROM otp_log WHERE ts < ?", ((n - timedelta(hours=2)).strftime(fmt),), commit=True)
        last = q("SELECT ts FROM otp_log WHERE phone=? ORDER BY id DESC LIMIT 1", (phone,), one=True)
        if last and last["ts"] > (n - timedelta(seconds=OTP_COOLDOWN_SEC)).strftime(fmt):
            raise OtpError("An OTP was just sent. Please wait a little before asking for another one.")
        since = (n - timedelta(hours=1)).strftime(fmt)
        if q("SELECT COUNT(*) c FROM otp_log WHERE phone=? AND ts>=?", (phone, since), one=True)["c"] >= OTP_PER_HOUR:
            raise OtpError("Too many OTP requests for this number. Please try again after an hour.")
        if ip and q("SELECT COUNT(*) c FROM otp_log WHERE ip=? AND ts>=?", (ip, since), one=True)["c"] >= OTP_PER_IP_HOUR:
            raise OtpError("Too many OTP requests from this device. Please try again later.")
        q("INSERT INTO otp_log(phone,ip,ts) VALUES(?,?,?)", (phone, ip, n.strftime(fmt)), commit=True)

    def otp_send(phone, purpose):
        """Make, store (hashed) and send an OTP. Returns the OTP only in demo mode, else None. Raises OtpError on throttle or gateway failure."""
        _otp_throttle(phone)
        otp = "".join(random.choices(string.digits, k=6))
        q("DELETE FROM otps WHERE phone=? AND purpose=?", (phone, purpose), commit=True)
        q("INSERT INTO otps(phone,purpose,code_hash,expires) VALUES(?,?,?,?)", (phone, purpose, _h(phone, otp), (now() + timedelta(minutes=10)).strftime(ns["FMT"])), commit=True)
        try: return deliver_otp(phone, otp)
        except OtpError:
            q("DELETE FROM otps WHERE phone=? AND purpose=?", (phone, purpose), commit=True); raise

    def otp_check(phone, purpose, otp):
        r = q("SELECT * FROM otps WHERE phone=? AND purpose=?", (phone, purpose), one=True)
        if not r: return False, "Please request a new OTP."
        if r["tries"] >= 5: return False, "Too many wrong attempts. Please request a new OTP."
        if r["expires"] < now().strftime(ns["FMT"]): return False, "This OTP has expired. Please request a new OTP."
        if not hmac.compare_digest(r["code_hash"], _h(phone, (otp or "").strip())):
            q("UPDATE otps SET tries=tries+1 WHERE id=?", (r["id"],), commit=True); return False, "Wrong OTP. Please try again."
        q("DELETE FROM otps WHERE id=?", (r["id"],), commit=True); return True, ""

    # ------------------------------------------------------------------ profile data layer
    FIELDS = ["name", "gender", "dob", "age_years", "age_asof", "guardian_name", "guardian_rel", "phone", "village_ward", "district", "state", "pin", "blood_group", "allergies", "conditions",
              "category", "disabled", "abha", "pmjay", "id_type", "id_last4", "em_name", "em_phone", "em_rel", "lang", "sms_ok"]

    def parse_patient(f, need_consent=True, phone_required=True):
        """Validate the registration / profile form. Returns (clean dict, list of error messages)."""
        def v(k, n=80): return (f.get(k) or "").strip()[:n]
        e, d = [], {}
        d["name"] = " ".join(v("name", 60).split())
        if not NAME_RE.match(d["name"]): e.append("Enter the patient's full name (letters only, no numbers).")
        d["gender"] = v("gender", 10)
        if d["gender"] not in ("Male", "Female", "Other"): e.append("Select gender.")
        d["dob"] = d["age_years"] = d["age_asof"] = None
        t = now().date()
        if v("dob", 10):
            try:
                x = date.fromisoformat(v("dob", 10))
                if x > t or years_between(x, t) > 120: raise ValueError
                d["dob"] = x.isoformat()
            except ValueError: e.append("Enter a valid date of birth, or leave it empty and type the age.")
        elif v("age_years", 3).isdigit() and 0 <= int(v("age_years", 3)) <= 120: d["age_years"], d["age_asof"] = int(v("age_years", 3)), t.isoformat()
        else: e.append("Enter the date of birth or the age in years.")
        y, _ = age_info(d["dob"], d["age_years"], d["age_asof"])
        d["guardian_name"], d["guardian_rel"] = v("guardian_name", 60), v("guardian_rel", 20)
        if d["guardian_name"] and not NAME_RE.match(d["guardian_name"]): e.append("Guardian name should have letters only.")
        if y is not None and y < 18 and not d["guardian_name"]: e.append("For a patient under 18, enter the parent or guardian's name.")
        d["phone"] = norm_phone(v("phone", 16))
        if d["phone"] and not MOBILE_RE.match(d["phone"]): e.append("Enter a valid 10-digit mobile number.")
        if phone_required and not d["phone"]: e.append("Enter a valid 10-digit mobile number.")
        d["village_ward"], d["district"], d["state"] = v("village_ward"), v("district", 40), v("state", 40) or "Madhya Pradesh"
        if not d["village_ward"] or not d["district"]: e.append("Enter village / ward and district.")
        d["pin"] = re.sub(r"\D", "", v("pin", 8))
        if d["pin"] and len(d["pin"]) != 6: e.append("PIN code must have 6 digits.")
        d["blood_group"] = v("blood_group", 4) if v("blood_group", 4) in BLOOD else ""
        d["allergies"] = v("allergies", 200)
        cs = [c for c in f.getlist("conditions") if c in CONDS]
        if v("cond_other", 60): cs.append(v("cond_other", 60))
        d["conditions"] = ", ".join(cs)
        d["category"] = v("category", 40) if v("category", 40) in CATEGORIES else "General"
        d["disabled"] = 1 if f.get("disabled") else 0
        ab = re.sub(r"[\s-]", "", v("abha", 20)); d["abha"] = ""
        if ab:
            if ab.isdigit() and len(ab) == 14: d["abha"] = f"{ab[:2]}-{ab[2:6]}-{ab[6:10]}-{ab[10:]}"
            else: e.append("ABHA number has 14 digits.")
        d["pmjay"] = v("pmjay", 25)
        if d["pmjay"] and not re.match(r"^[A-Za-z0-9\-]{6,25}$", d["pmjay"]): e.append("Ayushman card number: letters, digits and hyphen only.")
        d["id_type"] = v("id_type", 20) if v("id_type", 20) in ID_TYPES else ""
        d["id_last4"] = v("id_last4", 20)  # not cut to 4: a pasted full number must be rejected, never silently shortened
        if d["id_last4"] and not (d["id_last4"].isdigit() and len(d["id_last4"]) == 4): e.append("ID proof: enter only the LAST 4 digits.")
        d["em_name"], d["em_rel"] = v("em_name", 60), v("em_rel", 20)
        d["em_phone"] = norm_phone(v("em_phone", 16))
        if d["em_phone"] and not MOBILE_RE.match(d["em_phone"]): e.append("Emergency contact: enter a valid 10-digit mobile number.")
        d["lang"] = "en" if v("lang", 2) == "en" else "hi"
        d["sms_ok"] = 1 if f.get("sms_ok") else 0
        if need_consent and not f.get("consent"): e.append("Please accept the consent to continue.")
        return d, e

    def get_profile(pid): return q("SELECT * FROM patients WHERE id=? AND active=1", (pid,), one=True) if pid else None
    def my_profiles(uid): ensure_self(uid); return q("SELECT * FROM patients WHERE owner_id=? AND active=1 ORDER BY (relation='Self') DESC,id", (uid,))

    def ensure_self(uid):
        """Older accounts (created before profiles existed) get a minimal Self profile; booking then asks them to complete it."""
        if q("SELECT 1 FROM patients WHERE owner_id=? AND relation='Self'", (uid,), one=True): return
        u = q("SELECT name,phone,allergies FROM users WHERE id=? AND role='patient'", (uid,), one=True)
        if u: create_profile(dict(name=u["name"], phone=u["phone"], allergies=u["allergies"] or "", category="General", state="Madhya Pradesh", lang="hi", sms_ok=1), uid, "Self", "system", "legacy")

    def create_profile(d, owner, relation, by, src, assign=True):
        d = {k: d.get(k) for k in FIELDS if k in d}
        cols = list(d) + ["owner_id", "relation", "consent_ts", "created", "created_by", "src"]
        vals = list(d.values()) + [owner, relation, ts(), ts(), by, src]
        pid = q(f"INSERT INTO patients({','.join(cols)}) VALUES({','.join('?' * len(cols))})", vals, commit=True)
        if assign: q("UPDATE patients SET uhid=? WHERE id=?", (f"SGMH-{now().year % 100:02d}{pid:06d}", pid), commit=True)  # OTP-only accounts get the UHID at their first booking (see flow.py)
        return pid

    def missing(p):
        """What must be filled in before an appointment can be booked."""
        m = []
        if not p["gender"]: m.append("gender")
        if not p["dob"] and p["age_years"] is None: m.append("age or date of birth")
        if not p["village_ward"] or not p["district"]: m.append("address")
        y, _ = row_age(p)
        if y is not None and y < 18 and not p["guardian_name"]: m.append("parent / guardian name")
        return m

    def find_duplicates(d, owner=None):
        nm = " ".join(d["name"].lower().split()); out = []
        for r in q("SELECT * FROM patients WHERE active=1 AND (phone=? OR (dob IS NOT NULL AND dob=?))", (d.get("phone") or "-", d.get("dob") or "-")):
            same_name = " ".join((r["name"] or "").lower().split()) == nm
            if same_name and ((d.get("phone") and r["phone"] == d["phone"]) or (d.get("dob") and r["dob"] == d["dob"])) and (owner is None or r["owner_id"] == owner): out.append(r)
        return out

    def safe_next(n, default):
        return n if n and n.startswith("/") and not n.startswith("//") else default

    # ------------------------------------------------------------------ registration (self) with OTP
    @app.route("/register", methods=["GET", "POST"])
    def register_page():
        if session.get("role") == "patient": return redirect("/family")
        if request.method == "POST":
            d, e = parse_patient(request.form)
            pw = request.form.get("pw", ""); phone = d["phone"]
            if len(pw) < 8 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw): e.append("Password needs at least 8 characters with a letter and a digit.")
            if pw != request.form.get("pw2", ""): e.append("The two passwords do not match.")
            if phone and q("SELECT 1 FROM users WHERE phone=?", (phone,), one=True): e.append("This mobile number is already registered. Please log in.")
            if e:
                for x in e: flash(x)
                return render_template("register.html", p=request.form, getlist=request.form.getlist, cats=CATEGORIES, conds=CONDS, blood=BLOOD, idt=ID_TYPES, districts=DISTRICTS, rels=RELATIONS), 400
            session["reg"] = dict(d=d, pw=gph(pw), exp=(now() + timedelta(minutes=30)).strftime(ns["FMT"]), next=safe_next(request.form.get("next"), "/welcome"))
            if OTP_MODE == "off": return finish_registration()
            try: session["reg_otp"] = otp_send(phone, "register")
            except OtpError as ex:
                session.pop("reg", None); flash(str(ex)); return render_template("register.html", p=request.form, getlist=request.form.getlist, cats=CATEGORIES, conds=CONDS, blood=BLOOD, idt=ID_TYPES, districts=DISTRICTS, rels=RELATIONS), 503
            return redirect("/register/verify")
        return render_template("register.html", p={"state": "Madhya Pradesh", "lang": session.get("lang", "en"), "sms_ok": "1", "category": "General"}, getlist=lambda k: [], cats=CATEGORIES, conds=CONDS, blood=BLOOD, idt=ID_TYPES, districts=DISTRICTS, rels=RELATIONS)

    def finish_registration():
        r = session.pop("reg", None); session.pop("reg_otp", None)
        if not r or r["exp"] < now().strftime(ns["FMT"]): flash("Registration time ran out. Please fill the form again."); return redirect("/register")
        d = r["d"]
        if q("SELECT 1 FROM users WHERE phone=?", (d["phone"],), one=True): flash("This mobile number is already registered. Please log in."); return redirect("/login")
        uid = q("INSERT INTO users(name,phone,role,pw,allergies) VALUES(?,?,?,?,?)", (d["name"], d["phone"], "patient", r["pw"], d["allergies"] or None), commit=True)
        # a walk-in record made at the counter with the same mobile + name keeps its UHID and history
        nm = " ".join(d["name"].lower().split()); adopt = None
        for x in q("SELECT * FROM patients WHERE owner_id IS NULL AND active=1 AND phone=?", (d["phone"],)):
            if " ".join((x["name"] or "").lower().split()) == nm: adopt = x; break
        if adopt:
            sets = ",".join(f"{k}=?" for k in FIELDS); q(f"UPDATE patients SET {sets},owner_id=?,relation='Self',consent_ts=? WHERE id=?", [d.get(k) for k in FIELDS] + [uid, ts(), adopt["id"]], commit=True)
            q("UPDATE appts SET patient_id=? WHERE pid=? AND (patient_id IS NULL OR patient_id=0)", (uid, adopt["id"]), commit=True); pid = adopt["id"]
        else: pid = create_profile(d, uid, "Self", f"self:{d['name']}", "online")
        p = get_profile(pid)
        session.clear(); session.update(uid=uid, role="patient", name=d["name"], dept=None, lang="hi" if d["lang"] == "hi" else "en")
        audit(f"patient:{d['name']}", "REGISTER", p["uhid"] + (" (linked to counter record)" if adopt else ""))
        sms(d["phone"], f"SGMH Rewa: registration done. Your UHID is {p['uhid']}. Keep it for all future visits.", uid)
        if adopt: flash("Your earlier hospital record was found and linked. Your UHID is unchanged.")
        return redirect(r["next"])

    @app.route("/register/verify", methods=["GET", "POST"])
    def register_verify():
        r = session.get("reg")
        if not r: return redirect("/register")
        phone = r["d"]["phone"]
        if request.method == "POST":
            if request.form.get("resend"):
                try: session["reg_otp"] = otp_send(phone, "register"); flash("A new OTP has been sent." if OTP_MODE == "sms" else "A new OTP has been generated.")
                except OtpError as ex: flash(str(ex))
                return redirect("/register/verify")
            ok, msg = otp_check(phone, "register", request.form.get("otp", ""))
            if not ok: flash(msg); return redirect("/register/verify")
            return finish_registration()
        return render_template("register_verify.html", phone=mask_phone(phone), demo_otp=session.get("reg_otp") if OTP_MODE == "demo" else None)

    @app.route("/welcome")
    @pneed
    def welcome():
        pr = my_profiles(session["uid"]); me = next((x for x in pr if x["relation"] == "Self"), pr[0])
        return render_template("welcome.html", p=me)

    # ------------------------------------------------------------------ family / profiles
    def form_ctx(): return dict(cats=CATEGORIES, conds=CONDS, blood=BLOOD, idt=ID_TYPES, districts=DISTRICTS, rels=RELATIONS)

    def mine_only(pid):
        p = get_profile(pid)
        if not p or p["owner_id"] != session["uid"]: abort(404)
        return p

    @app.route("/family")
    @pneed
    def family():
        pr = my_profiles(session["uid"])
        return render_template("family.html", rows=[dict(r, miss=missing(r), pr=prio_reasons(r)) for r in pr], full=len(pr) >= MAX_FAMILY + 1)

    @app.route("/patients/new", methods=["GET", "POST"])
    @pneed
    def patient_new():
        nxt = safe_next(request.values.get("next"), "/family")
        if len(my_profiles(session["uid"])) >= MAX_FAMILY + 1: flash("You have reached the limit of family profiles."); return redirect("/family")
        if request.method == "POST":
            d, e = parse_patient(request.form, phone_required=False)
            rel = request.form.get("relation") if request.form.get("relation") in RELATIONS else "Other"
            if not d["phone"]: d["phone"] = q("SELECT phone FROM users WHERE id=?", (session["uid"],), one=True)["phone"]
            if find_duplicates(d, owner=session["uid"]): e.append("This family member is already in your list.")
            if e:
                for x in e: flash(x)
                return render_template("patient_form.html", p=request.form, getlist=request.form.getlist, mode="new", nxt=nxt, **form_ctx()), 400
            pid = create_profile(d, session["uid"], rel, who(), "online"); audit(who(), "PROFILE_ADD", get_profile(pid)["uhid"]); flash(f"Saved. UHID {get_profile(pid)['uhid']}.")
            if nxt.startswith("/book"): nxt += ("&" if "?" in nxt else "?") + urlencode({"pid": pid})
            return redirect(nxt)
        return render_template("patient_form.html", p={"state": "Madhya Pradesh", "lang": session.get("lang", "en"), "sms_ok": "1", "category": "General", "relation": "Spouse"}, getlist=lambda k: [], mode="new", nxt=nxt, **form_ctx())

    @app.route("/patients/<int:pid>/edit", methods=["GET", "POST"])
    @pneed
    def patient_edit(pid):
        p = mine_only(pid); nxt = safe_next(request.values.get("next"), "/family"); is_self = p["relation"] == "Self"
        if request.method == "POST":
            f = request.form.copy()
            if is_self: f = f.copy(); f["phone"] = p["phone"]  # the login number is changed only through the hospital
            d, e = parse_patient(f, need_consent=False, phone_required=is_self)
            if not d["phone"]: d["phone"] = p["phone"]
            if e:
                for x in e: flash(x)
                return render_template("patient_form.html", p=f, getlist=f.getlist, mode="edit", pid=pid, is_self=is_self, nxt=nxt, **form_ctx()), 400
            sets = ",".join(f"{k}=?" for k in FIELDS); q(f"UPDATE patients SET {sets} WHERE id=?", [d.get(k) for k in FIELDS] + [pid], commit=True)
            if is_self: q("UPDATE users SET name=?,allergies=? WHERE id=?", (d["name"], d["allergies"] or None, session["uid"]), commit=True); session["name"] = d["name"]
            audit(who(), "PROFILE_EDIT", p["uhid"]); flash("Details saved."); return redirect(nxt)
        cur = dict(p); cur["conditions_l"] = [c.strip() for c in (p["conditions"] or "").split(",")]
        return render_template("patient_form.html", p=cur, getlist=lambda k: cur["conditions_l"] if k == "conditions" else [], mode="edit", pid=pid, is_self=is_self, nxt=nxt, **form_ctx())

    @app.route("/patients/<int:pid>/remove", methods=["POST"])
    @pneed
    def patient_remove(pid):
        p = mine_only(pid)
        if p["relation"] == "Self": flash("Your own profile cannot be removed."); return redirect("/family")
        if q("SELECT 1 FROM appts WHERE pid=?", (pid,), one=True): q("UPDATE patients SET active=0 WHERE id=?", (pid,), commit=True)  # medical history is kept
        else: q("DELETE FROM patients WHERE id=?", (pid,), commit=True)
        audit(who(), "PROFILE_REMOVE", p["uhid"]); flash("Profile removed."); return redirect("/family")

    # ------------------------------------------------------------------ smart booking
    def smart_dept(reason, prof, preg, depts):
        import ml
        rk = ml.rank(reason); base = rk[0]["dept"] if rk and rk[0]["prob"] >= 0.3 else suggest(reason)
        y, _ = row_age(prof)
        if preg and "Gynaecology" in depts: return "Gynaecology", "Pregnancy"
        if y is not None and y < 12 and "Paediatrics" in depts and base in (None, "Medicine", "ENT"): return "Paediatrics", "Child under 12 years"
        return (base if base in depts else None), None

    @app.route("/book", methods=["GET", "POST"])
    @pneed
    def book():
        g = request.form if request.method == "POST" else request.args
        uid = session["uid"]; profs = my_profiles(uid)
        pid = g.get("pid", type=int)
        prof = next((x for x in profs if x["id"] == pid), None) or next((x for x in profs if x["relation"] == "Self"), profs[0])
        reason = g.get("reason", "")[:200]; depts = sorted({d["dept"] for d in get_docs()})
        preg = g.get("preg") == "1" and can_preg(prof)
        referred = g.get("referred") == "1"; ref_by = g.get("ref_by", "")[:60]; vtype = g.get("vt") if g.get("vt") in ("New", "Follow-up") else "New"
        did = g.get("doctor", type=int); dept = g.get("dept") if g.get("dept") in depts else None
        if did and not dept:
            r = q("SELECT dept FROM users WHERE id=? AND role='doctor'", (did,), one=True); dept = r["dept"] if r else None
        sug, sug_why = smart_dept(reason, prof, preg, depts)
        if not dept and sug in depts: dept = sug
        docs = get_docs(dept=dept) if dept else []
        doc = next((d for d in docs if d["id"] == did), None)
        try: dd = datetime.strptime(g.get("date", ""), "%Y-%m-%d").date()
        except ValueError: dd = None
        if not dd or dd < now().date():
            nf = next_free(did) if doc else None
            dd = datetime.strptime(nf["date"], "%Y-%m-%d").date() if nf else default_date()
        dd = next_opd_day(dd); iso = dd.isoformat()
        slots = slot_states(did, iso) if doc else []
        slot = g.get("slot") if g.get("slot") in [x["slot"] for x in slots if x["state"] == "free"] else None
        miss = missing(prof)
        cur = dict(reason=reason, dept=dept, doctor=did, date=iso, slot=slot, pid=prof["id"], preg="1" if preg else None, referred="1" if referred else None, ref_by=ref_by if referred else None, vt=vtype if vtype != "New" else None)
        if request.method == "GET" and doc and doc["code"] != "leave" and prof["relation"] == "Self" and (miss or not prof["uhid"]):  # first booking: registration details are asked here, once
            return redirect(burl("/register/details", pid=prof["id"], next=burl("/book", **cur)))
        if request.method == "POST":
            back = burl("/book", **{**cur, "slot": None})
            if red_flag(reason): flash(EMERG_MSG); return redirect(back)
            if miss: flash("Please complete the patient's details first."); return redirect(back)
            if not doc or doc["code"] == "leave": flash("Please choose an available doctor."); return redirect(back)
            if not slot: flash("That time is no longer free. Please pick another time."); return redirect(back)
            if q("SELECT 1 FROM appts WHERE pid=? AND doctor_id=? AND date=? AND status!='cancelled' AND kind='OPD'", (prof["id"], doc["id"], iso), one=True):
                flash("This patient already has an appointment with this doctor on this day."); return redirect(burl("/mine"))
            if q("SELECT COUNT(*) n FROM appts WHERE patient_id=? AND status='booked' AND date>=? AND kind='OPD'", (uid, now().date().isoformat()), one=True)["n"] >= MAX_UPCOMING:
                flash("You already have many upcoming appointments. Please cancel one you do not need."); return redirect("/mine")
            pr = prio_reasons(prof, preg); c = code("AP-")
            try:
                aid = q("INSERT INTO appts(code,patient_id,doctor_id,dept,date,slot,reason,created,kind,pid,prio,prio_why,referred_by,visit_type,src) VALUES(?,?,?,?,?,?,?,?,'OPD',?,?,?,?,?,'online')",
                        (c, uid, doc["id"], dept, iso, slot, reason, ts(), prof["id"], 1 if pr else 0, ", ".join(pr) or None, (ref_by or "Referred") if referred else None, vtype), commit=True)
            except sqlite3.IntegrityError: flash("That time was just booked by someone else. Please pick another time."); return redirect(back)
            event(aid, "Registered"); audit(who(), "BOOK", f"{c} {prof['uhid']}")
            sms(prof["phone"], f"SGMH Rewa: appointment {c} for {prof['name']} with {doc['name']} ({dept}) on {iso} at {slot}. Carry photo ID. Show the QR at reception.", uid, c) if prof["sms_ok"] else None
            return redirect(f"/appt/{c}")
        today = now().date(); days = []; d = default_date()
        while len(days) < 6:
            free = sum(x["state"] == "free" for x in slot_states(did, d.isoformat())) if doc else None
            days.append(dict(iso=d.isoformat(), wd=d.strftime("%a"), dm=d.strftime("%d/%m"), free=free, full=(free == 0), rel="Today" if d == today else "Tomorrow" if d == today + timedelta(days=1) else None)); d = next_opd_day(d + timedelta(days=1))
        nf = next_free(did) if doc else None
        return render_template("book.html", u=lambda **k: burl("/book", **{**cur, **k}), reason=reason, emergency=red_flag(reason), suggestion=sug, sug_why=sug_why, depts=depts, dept=dept, docs=docs, doc=doc,
                               days=days, date_iso=iso, slots=slots, slot=slot, free_n=sum(x["state"] == "free" for x in slots), profs=profs, prof=prof, miss=miss, preg=preg, preg_ok=can_preg(prof),
                               referred=referred, ref_by=ref_by, vtype=vtype, prio=prio_reasons(prof, preg), bring=docs_to_bring(prof, referred, preg), earliest=nf, fee_note=FEE_NOTE,
                               here=burl("/book", **cur), cur=cur, hist=(ns["visit_history"](uid, pid=prof["id"], doctor=doc["id"]) if doc and "visit_history" in ns else []))


    # ------------------------------------------------------------------ IPD: no patient self-request any more (doctor referral or emergency only)
    MOBILITY = ["Walks without help", "Needs a wheelchair", "Needs a stretcher"]
    ATT_RELS = RELATIONS + ["Friend / neighbour"]

    def ward_block(p, w, preg=False):
        """Why this ward does not suit the patient (None = fine). The hospital still confirms the bed."""
        y, _ = row_age(p); g = keyget(p, "gender", "pgender")
        if w == "Maternity ward" and g != "Female": return "For women only"
        if w == "Paediatric ward" and y is not None and y >= 18: return "For patients under 18"
        return None

    @app.route("/admit", methods=["GET", "POST"])
    def admit():
        """Patients can no longer ask for IPD admission themselves. Admission is decided by the DOCTOR (OPD referral) or by emergency staff.
        Old links and bookmarks land on the IPD information page."""
        flash("Admission to hospital (IPD) is decided by your doctor after the OPD visit, or by the emergency team. Book an OPD appointment, or go to the Emergency gate / call 112.")
        return redirect("/ipd")

    # ------------------------------------------------------------------ appointment page, slip, calendar, reschedule, feedback
    def my_appt(c):
        a = appt_row(c)
        if not a or a["patient_id"] != session["uid"]: abort(404)
        return a

    def prof_of(a): return q("SELECT * FROM patients WHERE id=?", (a["pid"],), one=True) if a["pid"] else None

    @app.route("/appt/<c>")
    @pneed
    def appt(c):
        a = my_appt(c); p = prof_of(a)
        pr = [x.strip() for x in (a["prio_why"] or "").split(",") if x.strip()]
        fb = q("SELECT * FROM feedback WHERE appt_id=?", (a["id"],), one=True)
        return render_template("appt.html", a=a, p=p, prio=pr, bring=(docs_to_bring_ipd if a["kind"] == "IPD" else docs_to_bring)(p, bool(a["referred_by"]), "Pregnant woman" in pr) if p else [], fee_note=FEE_NOTE, fb=fb,
                               today=now().date().isoformat(), can_cancel=(a["status"] == "booked"), can_resched=(a["status"] == "booked" and a["kind"] == "OPD" and a["slot"] != "Walk-in" and a["date"] >= now().date().isoformat() and (a["resched_n"] or 0) < 3))

    @app.route("/appt/<c>/slip")
    def slip(c):
        a = appt_row(c)
        if not a or not can_view(a, c): abort(403)
        p = prof_of(a); pr = [x.strip() for x in (a["prio_why"] or "").split(",") if x.strip()]
        if session.get("role") in ("reception", "admin", "doctor", "nurse"): audit(who(), "SLIP_VIEW", c)
        return render_template("slip.html", a=a, p=p, prio=pr, bring=docs_to_bring(p, bool(a["referred_by"]), "Pregnant woman" in pr) if p else [], fee_note=FEE_NOTE)

    @app.route("/appt/<c>.ics")
    @pneed
    def appt_ics(c):
        a = my_appt(c)
        if a["slot"] == "Walk-in" or a["kind"] != "OPD": abort(404)
        st = datetime.strptime(f"{a['date']} {a['slot']}", "%Y-%m-%d %H:%M") - timedelta(hours=5, minutes=30); en = st + timedelta(minutes=30); f = "%Y%m%dT%H%M%SZ"
        L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Smart SGMH//OPD//EN", "BEGIN:VEVENT", f"UID:{a['code']}@smart-sgmh", f"DTSTAMP:{datetime.utcnow().strftime(f)}", f"DTSTART:{st.strftime(f)}", f"DTEND:{en.strftime(f)}",
             f"SUMMARY:SGMH OPD - {a['doctor']} ({a['dept']})".replace(",", "\\,"), "LOCATION:Sanjay Gandhi Memorial Hospital\\, Rewa (M.P.) 486001",
             f"DESCRIPTION:Appointment {a['code']}. Carry photo ID. Arrive 15 minutes early and show the QR code at reception.", "BEGIN:VALARM", "TRIGGER:-PT60M", "ACTION:DISPLAY", "DESCRIPTION:SGMH appointment in 1 hour", "END:VALARM", "END:VEVENT", "END:VCALENDAR"]
        return Response("\r\n".join(L) + "\r\n", mimetype="text/calendar", headers={"Content-Disposition": f"attachment; filename={a['code']}.ics"})

    @app.route("/appt/<c>/reschedule", methods=["GET", "POST"])
    @pneed
    def reschedule(c):
        a = my_appt(c); t = now().date().isoformat()
        if a["status"] != "booked" or a["kind"] != "OPD" or a["slot"] == "Walk-in" or a["date"] < t or (a["resched_n"] or 0) >= 3:
            flash("This appointment cannot be rescheduled."); return redirect(f"/appt/{c}")
        g = request.form if request.method == "POST" else request.args
        try: dd = datetime.strptime(g.get("date", ""), "%Y-%m-%d").date()
        except ValueError: dd = datetime.strptime(a["date"], "%Y-%m-%d").date()
        if dd < now().date(): dd = default_date()
        iso = next_opd_day(dd).isoformat(); slots = slot_states(a["doctor_id"], iso)
        if request.method == "POST":
            sl = g.get("slot")
            if sl not in [x["slot"] for x in slots if x["state"] == "free"]: flash("That time is no longer free. Please pick another time."); return redirect(f"/appt/{c}/reschedule?date={iso}")
            try: q("UPDATE appts SET date=?,slot=?,resched_n=COALESCE(resched_n,0)+1 WHERE id=?", (iso, sl, a["id"]), commit=True)
            except sqlite3.IntegrityError: flash("That time was just booked by someone else. Please pick another time."); return redirect(f"/appt/{c}/reschedule?date={iso}")
            audit(who(), "RESCHEDULE", f"{c} {a['date']} {a['slot']} -> {iso} {sl}")
            sms(a["pphone"], f"SGMH Rewa: appointment {c} moved to {iso} at {sl} with {a['doctor']}.", session["uid"], c); flash("Appointment rescheduled."); return redirect(f"/appt/{c}")
        days = []; d = default_date()
        while len(days) < 6:
            free = sum(x["state"] == "free" for x in slot_states(a["doctor_id"], d.isoformat())); days.append(dict(iso=d.isoformat(), wd=d.strftime("%a"), dm=d.strftime("%d/%m"), free=free)); d = next_opd_day(d + timedelta(days=1))
        return render_template("reschedule.html", a=a, days=days, date_iso=iso, slots=slots, left=3 - (a["resched_n"] or 0))

    @app.route("/appt/<c>/feedback", methods=["POST"])
    @pneed
    def feedback(c):
        a = my_appt(c)
        try: r = int(request.form.get("rating", 0)); assert 1 <= r <= 5
        except (ValueError, AssertionError): flash("Please choose a rating from 1 to 5."); return redirect(f"/appt/{c}")
        if a["status"] not in ("seen", "discharged"): flash("You can give feedback after the visit."); return redirect(f"/appt/{c}")
        q("INSERT OR REPLACE INTO feedback(appt_id,rating,comment,ts) VALUES(?,?,?,?)", (a["id"], r, request.form.get("comment", "").strip()[:300], ts()), commit=True)
        audit(who(), "FEEDBACK", c); flash("Thank you for your feedback."); return redirect(f"/appt/{c}")

    @app.route("/notifications")
    @pneed
    def notifications():
        rows = q("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (session["uid"],))
        q("UPDATE notifications SET seen=1 WHERE user_id=?", (session["uid"],), commit=True)
        return render_template("notifications.html", rows=rows)

    @app.context_processor
    def _unseen():
        n = 0
        if session.get("role") == "patient":
            try: n = q("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND seen=0", (session["uid"],), one=True)["n"]
            except Exception: n = 0
        return dict(unseen_n=n)

    @app.route("/privacy")
    def privacy(): return render_template("privacy.html")

    # ------------------------------------------------------------------ staff: search, profile (need-to-know), walk-in
    STAFF_VIEW = ("reception", "doctor", "nurse", "admin")

    @app.route("/staff/patients")
    @need(*STAFF_VIEW)
    def staff_patients():
        s = request.args.get("q", "").strip(); rows = []
        if len(s) >= 3:
            dg = re.sub(r"\D", "", s)
            rows = q("SELECT * FROM patients WHERE active=1 AND (uhid LIKE ? OR name LIKE ? OR (?!='' AND phone LIKE ?)) ORDER BY id DESC LIMIT 25", (f"%{s.upper()}%", f"%{s}%", dg, f"%{dg}"))
            audit(who(), "PATIENT_SEARCH", f"{len(rows)} results")
        elif s: flash("Type at least 3 characters (UHID, mobile number or name).")
        return render_template("staff_patients.html", rows=rows, s=s, full=session.get("role") in ("reception", "admin"))

    def staff_profile(uhid):
        p = q("SELECT * FROM patients WHERE uhid=?", (uhid.upper(),), one=True)
        if not p: abort(404)
        if session["role"] == "doctor" and not q("SELECT 1 FROM appts WHERE pid=? AND doctor_id=?", (p["id"], session["uid"]), one=True): abort(403)  # need-to-know
        return p

    @app.route("/staff/patient/<uhid>")
    @need(*STAFF_VIEW)
    def staff_patient(uhid):
        p = staff_profile(uhid); full = session["role"] in ("reception", "admin")
        audit(who(), "PROFILE_VIEW", p["uhid"])
        visits = q("SELECT a.code,a.date,a.slot,a.dept,a.status,a.src,d.name doctor FROM appts a JOIN users d ON d.id=a.doctor_id WHERE a.pid=? ORDER BY a.id DESC LIMIT 15", (p["id"],))
        return render_template("staff_patient.html", p=p, full=full, visits=visits, pr=prio_reasons(p), miss=missing(p), can_walkin=full)

    @app.route("/staff/patients/new", methods=["GET", "POST"])
    @need("reception", "admin")
    def staff_new():
        if request.method == "POST":
            d, e = parse_patient(request.form, need_consent=True, phone_required=False)
            dups = find_duplicates(d)
            if dups and not request.form.get("confirm_dup"):
                e.append("A similar record already exists (see below). If this is a different person, tick the box and save again.")
            if e:
                for x in e: flash(x)
                return render_template("staff_new.html", p=request.form, getlist=request.form.getlist, dups=dups, **form_ctx()), 400
            pid = create_profile(d, None, "Self", who(), "walk-in"); u = get_profile(pid)["uhid"]; audit(who(), "PROFILE_ADD_COUNTER", u); flash(f"Registered. UHID {u}.")
            return redirect(f"/staff/walkin/{u}")
        return render_template("staff_new.html", p={"state": "Madhya Pradesh", "lang": "hi", "sms_ok": "1", "category": "General", "consent": "1"}, getlist=lambda k: [], dups=[], **form_ctx())

    @app.route("/staff/walkin/<uhid>", methods=["GET", "POST"])
    @need("reception", "admin")
    def walkin(uhid):
        p = staff_profile(uhid); docs = [d for d in get_docs() if d["code"] != "leave"]
        reason = request.values.get("reason", "")[:200]
        if request.method == "POST":
            preg = request.form.get("preg") == "1" and can_preg(p); d = next((x for x in docs if x["id"] == request.form.get("doctor", type=int)), None)
            if red_flag(reason): flash(EMERG_MSG + " Send the patient to the Emergency gate now."); return redirect(f"/staff/walkin/{uhid}")
            if not d: flash("Choose a doctor who is available."); return redirect(f"/staff/walkin/{uhid}")
            if missing(p) and request.form.get("force") != "1": flash("Patient details are incomplete (" + ", ".join(missing(p)) + "). Edit the record or tick 'register anyway'."); return redirect(f"/staff/walkin/{uhid}")
            pr = prio_reasons(p, preg); c = code("AP-"); t = now().date().isoformat()
            tok = q("SELECT COUNT(*) n FROM appts WHERE doctor_id=? AND date=? AND token IS NOT NULL", (d["id"], t), one=True)["n"] + 1
            aid = q("INSERT INTO appts(code,patient_id,doctor_id,dept,date,slot,reason,created,kind,pid,prio,prio_why,visit_type,src,status,token) VALUES(?,?,?,?,?,?,?,?,'OPD',?,?,?,?, 'walk-in','arrived',?)",
                    (c, p["owner_id"], d["id"], d["dept"], t, "Walk-in", reason, ts(), p["id"], 1 if pr else 0, ", ".join(pr) or None, request.form.get("vt") if request.form.get("vt") in ("New", "Follow-up") else "New", tok), commit=True)
            event(aid, "Registered"); event(aid, "Reception"); audit(who(), "WALKIN", f"{c} {p['uhid']} token {tok}")
            if p["phone"] and p["sms_ok"]: sms(p["phone"], f"SGMH Rewa: OPD registration {c}, token {tok}, {d['name']} ({d['dept']}). UHID {p['uhid']}.", p["owner_id"], c)
            flash(f"Token {tok} issued to {p['name']}."); return redirect(f"/reception?v={c}")
        return render_template("walkin.html", p=p, docs=docs, reason=reason, miss=missing(p), pr=prio_reasons(p), preg_ok=can_preg(p), opd_open=opd_open())

    # staff pages (reception verify panel / doctor / admin) use these
    @app.context_processor
    def _staff_helpers():
        return dict(prio_list=lambda s: [x.strip() for x in (s or "").split(",") if x.strip()], today=now().date().isoformat())

    ns["ensure_self"], ns["my_profiles"], ns["prio_reasons"], ns["sms"], ns["get_profile"], ns["row_age"], ns["docs_to_bring"] = ensure_self, my_profiles, prio_reasons, sms, get_profile, row_age, docs_to_bring
    ns.update(OtpError=OtpError, otp_send=otp_send, otp_check=otp_check, OTP_MODE=OTP_MODE, norm_phone=norm_phone, mask_phone=mask_phone, create_profile=create_profile, missing=missing, parse_patient=parse_patient,
              FIELDS=FIELDS, form_ctx=form_ctx, safe_next=safe_next, pneed=pneed, mine_only=mine_only, pdesc=pdesc, MAX_UPCOMING=MAX_UPCOMING)

    # ------------------------------------------------------------------ demo patient gets a complete sample profile
    try:
        u = q("SELECT id,name,phone FROM users WHERE phone='9000000001' AND role='patient'", one=True)
        if u and not q("SELECT 1 FROM patients WHERE owner_id=?", (u["id"],), one=True):
            create_profile(dict(name="Demo Patient", gender="Male", age_years=35, age_asof=now().date().isoformat(), phone=u["phone"], village_ward="Civil Lines (SAMPLE)", district="Rewa", state="Madhya Pradesh",
                                category="General", lang="en", sms_ok=1, allergies="", conditions="", em_name="Sample Contact", em_phone="9000000099", em_rel="Spouse"), u["id"], "Self", "seed", "online")
    except Exception: pass
