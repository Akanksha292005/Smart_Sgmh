"""Patient journey for Smart SGMH, in the order a patient meets it:
  1. /start        name + mobile + OTP (new patients get an account; registered patients also type their password, so nobody else can open it)
  2. /home         "Welcome, <name>": next step, journey, doctors already consulted, visit history, own records
  3. /book         choose department, doctor ... the FIRST time a doctor is chosen, /register/details asks for the full details + a password (UHID is issued there)
  4. visit day     QR, token, live tracking (existing pages), then advice and reports are saved in the history
  5. /history, /records   every visit (date, doctor, what was checked) and uploaded old prescriptions / reports
SAMPLE: OTP is shown on screen (OTP_MODE=demo) until an SMS gateway is plugged into registration.deliver_otp()."""
import os, re, secrets
from datetime import timedelta
from urllib.parse import urlparse, parse_qs
from flask import request, session, render_template, redirect, flash, abort, send_file
from werkzeug.security import check_password_hash as cph, generate_password_hash as gph

MAX_FILE = 5 * 1024 * 1024
MAGIC = {b"%PDF": ("pdf", "application/pdf"), b"\xff\xd8\xff": ("jpg", "image/jpeg"), b"\x89PNG": ("png", "image/png")}
LOCK_TRIES, LOCK_MIN = 5, 15
DONE = ("seen", "arrived", "admitted", "discharged", "deceased")


def register(ns):
    app, q, db, now, ts, audit, who, FMT, event = (ns[k] for k in ("app", "q", "db", "now", "ts", "audit", "who", "FMT", "event"))
    otp_send, otp_check, OTP_MODE, norm_phone, mask_phone, OtpError = (ns[k] for k in ("otp_send", "otp_check", "OTP_MODE", "norm_phone", "mask_phone", "OtpError"))
    my_profiles, get_profile, create_profile, missing, parse_patient, FIELDS, form_ctx, safe_next, sms, pneed, mine_only, pdesc = (
        ns[k] for k in ("my_profiles", "get_profile", "create_profile", "missing", "parse_patient", "FIELDS", "form_ctx", "safe_next", "sms", "pneed", "mine_only", "pdesc"))
    from i18n import HI
    from i18n_flow import FLOW_HI, FLOW_PAT
    for k, v in FLOW_HI.items(): HI.setdefault(k, v)
    ns["PAT"].extend(FLOW_PAT)
    _depts = [r["dept"] for r in q("SELECT DISTINCT dept FROM users WHERE dept IS NOT NULL")] + ["Medicine", "Orthopaedics", "Paediatrics", "Gynaecology", "Cardiology", "ENT"]
    _depts = sorted({d for d in _depts if d in HI}, key=len, reverse=True)
    if _depts: ns["PAT"].append((re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(d) for d in _depts) + r")(?![A-Za-z])"), lambda m: HI[m.group(1)]))
    UPLOADS = os.environ.get("UPLOAD_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads"))
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

    c = db()
    c.executescript("""CREATE TABLE IF NOT EXISTS authfail(phone TEXT PRIMARY KEY, n INTEGER DEFAULT 0, until TEXT);
CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY, owner_id INTEGER, pid INTEGER, title TEXT, rec_date TEXT, note TEXT, fname TEXT, orig TEXT, mime TEXT, size INTEGER, ts TEXT);""")
    c.commit(); c.close()
    clip = lambda s, n=200: re.sub(r"[<>]", "", (s or "").strip())[:n]
    has_pw = lambda u: bool(u and u["pw"] and u["pw"] != "!")

    # ------------------------------------------------------------ wrong-attempt lock (per mobile number)
    def locked(phone):
        r = q("SELECT until FROM authfail WHERE phone=?", (phone,), one=True)
        return bool(r and r["until"] and r["until"] > ts())
    def failed(phone):
        r = q("SELECT n FROM authfail WHERE phone=?", (phone,), one=True); n = (r["n"] if r else 0) + 1
        until = (now() + timedelta(minutes=LOCK_MIN)).strftime(FMT) if n >= LOCK_TRIES else None
        q("INSERT INTO authfail(phone,n,until) VALUES(?,?,?) ON CONFLICT(phone) DO UPDATE SET n=excluded.n,until=excluded.until", (phone, 0 if until else n, until), commit=True)
        if until: audit(f"phone:{phone}", "LOGIN_LOCKED", f"{LOCK_MIN} min")
    def cleared(phone): q("DELETE FROM authfail WHERE phone=?", (phone,), commit=True)

    def sign_in(u):
        lang = session.get("lang"); nxt = session.get("next")
        session.clear(); session.update(uid=u["id"], role=u["role"], name=u["name"], dept=u["dept"], lang=lang or "en")
        return nxt

    # ------------------------------------------------------------ 1. start: name + mobile + OTP
    @app.route("/start", methods=["GET", "POST"])
    def start():
        if session.get("role") in ns["HOME_OF"]: return redirect(ns["HOME_OF"][session["role"]])
        if request.method == "POST":
            phone = norm_phone(request.form.get("phone", "")); name = clip(request.form.get("name"), 80)
            if not re.fullmatch(r"[6-9]\d{9}", phone): flash("Enter a valid 10-digit mobile number."); return redirect("/start")
            u = q("SELECT * FROM users WHERE phone=?", (phone,), one=True)
            if u and u["role"] != "patient": flash("This number belongs to hospital staff. Please use Staff login."); return redirect("/start")
            if not u and (len(name) < 2 or not re.fullmatch(r"[A-Za-z\u0900-\u097F .'-]{2,80}", name)): flash("Please enter your name (letters only)."); return redirect("/start")
            if locked(phone): flash(f"Too many wrong attempts. Please try again after {LOCK_MIN} minutes."); return redirect("/start")
            session["gate"] = dict(phone=phone, name=name, exp=(now() + timedelta(minutes=15)).strftime(FMT))
            try: session["gate_otp"] = otp_send(phone, "login") if OTP_MODE != "off" else None
            except OtpError as ex: session.pop("gate", None); flash(str(ex)); return redirect("/start")
            return redirect("/start/verify")
        return render_template("start.html")

    @app.route("/start/verify", methods=["GET", "POST"])
    def start_verify():
        g = session.get("gate")
        if not g or g["exp"] < ts(): session.pop("gate", None); flash("Please enter your name and mobile number again."); return redirect("/start")
        phone = g["phone"]; u = q("SELECT * FROM users WHERE phone=?", (phone,), one=True); protected = has_pw(u)
        if request.method == "POST":
            if request.form.get("resend"):
                try: session["gate_otp"] = otp_send(phone, "login") if OTP_MODE != "off" else None; flash("A new OTP has been sent." if OTP_MODE == "sms" else "A new OTP has been generated.")
                except OtpError as ex: flash(str(ex))
                return redirect("/start/verify")
            if locked(phone): flash(f"Too many wrong attempts. Please try again after {LOCK_MIN} minutes."); return redirect("/start")
            pw_ok = (not protected) or cph(u["pw"], request.form.get("pw", ""))
            ok, msg = (True, "") if OTP_MODE == "off" else (otp_check(phone, "login", request.form.get("otp", "")) if pw_ok else (False, ""))
            if not (pw_ok and ok):
                failed(phone); audit(f"phone:{phone}", "LOGIN_FAIL", "otp/password")
                flash(msg if (ok is False and pw_ok and msg) else "The OTP or password is not correct."); return redirect("/start/verify")
            cleared(phone); new = u is None
            if new:
                uid = q("INSERT INTO users(name,phone,role,pw) VALUES(?,?,?,?)", (g["name"], phone, "patient", "!"), commit=True)
                create_profile(dict(name=g["name"], phone=phone, category="General", state="Madhya Pradesh", lang="hi" if session.get("lang") == "hi" else "en", sms_ok=1), uid, "Self", f"self:{g['name']}", "otp", assign=False)
                u = q("SELECT * FROM users WHERE id=?", (uid,), one=True); audit(f"patient:{g['name']}", "SIGNUP_OTP", phone[-4:])
            nxt = sign_in(u); audit(f"patient:{u['name']}", "LOGIN_OTP", "new" if new else "returning")
            session["welcome"] = 1
            return redirect(safe_next(nxt, "/app/"))
        return render_template("start_verify.html", phone=mask_phone(phone), protected=protected, new=u is None, demo_otp=session.get("gate_otp") if OTP_MODE == "demo" else None, off=(OTP_MODE == "off"))

    # ------------------------------------------------------------ history data
    def tests_of(aid): return [dict(r) for r in q("SELECT test,status FROM samples WHERE appt_id=? ORDER BY id", (aid,))]
    def visit_history(uid, pid=None, doctor=None, limit=60):
        rows = q("SELECT a.id,a.code,a.date,a.slot,a.kind,a.dept,a.status,a.reason,a.doctor_id,a.visit_type,COALESCE(pt.name,p.name) pname,pt.uhid,d.name doctor,d.designation,n.diagnosis,n.meds,n.followup,n.approved "
                 "FROM appts a LEFT JOIN users p ON p.id=a.patient_id LEFT JOIN patients pt ON pt.id=a.pid JOIN users d ON d.id=a.doctor_id LEFT JOIN notes n ON n.appt_id=a.id "
                 f"WHERE a.patient_id=? AND a.status IN ({','.join('?' * len(DONE))}) AND (? IS NULL OR a.pid=?) AND (? IS NULL OR a.doctor_id=?) ORDER BY a.date DESC,a.id DESC LIMIT ?",
                 (uid, *DONE, pid, pid, doctor, doctor, limit))
        out = []
        for r in rows:
            d = dict(r); ok = bool(d["approved"]); d["diagnosis"] = d["diagnosis"] if ok else None; d["meds"] = d["meds"] if ok else None; d["followup"] = d["followup"] if ok else None
            d["tests"] = tests_of(d["id"]); out.append(d)
        return out
    ns["visit_history"] = visit_history
    def doctors_seen(uid):
        return [dict(r) for r in q("SELECT a.doctor_id did,d.name doctor,d.designation,a.dept,COUNT(*) n,MAX(a.date) last FROM appts a JOIN users d ON d.id=a.doctor_id "
                                  f"WHERE a.patient_id=? AND a.status IN ({','.join('?' * len(DONE))}) GROUP BY a.doctor_id ORDER BY last DESC", (uid, *DONE))]
    def records_of(uid=None, pid=None):
        return [dict(r) for r in q("SELECT r.*,COALESCE(pt.name,'') pname FROM records r LEFT JOIN patients pt ON pt.id=r.pid WHERE (? IS NULL OR r.owner_id=?) AND (? IS NULL OR r.pid=?) ORDER BY r.id DESC", (uid, uid, pid, pid))]
    app.context_processor(lambda: dict(records_of=records_of))

    def journey(uid):
        today = now().date().isoformat(); me = next((x for x in my_profiles(uid) if x["relation"] == "Self"), None)
        u = q("SELECT pw FROM users WHERE id=?", (uid,), one=True)
        up = q("SELECT a.code,a.date,a.slot,a.status,d.name doctor FROM appts a JOIN users d ON d.id=a.doctor_id WHERE a.patient_id=? AND a.kind='OPD' AND ((a.status='booked' AND a.date>=?) OR (a.status='arrived' AND a.date=?)) ORDER BY a.date,a.slot", (uid, today, today))
        hist = visit_history(uid, limit=8); anyappt = q("SELECT 1 FROM appts WHERE patient_id=? AND status!='cancelled'", (uid,), one=True)
        registered = bool(me and me["uhid"] and not missing(me) and has_pw(u))
        arrived = next((x for x in up if x["status"] == "arrived"), None)
        if arrived: nxt = dict(k="arrived", href=f"/visit/{arrived['code']}", who=arrived["doctor"], when="")
        elif up: nxt = dict(k="upcoming", href=f"/appt/{up[0]['code']}", who=up[0]["doctor"], when=f"{up[0]['date']} {up[0]['slot']}")
        elif hist: nxt = dict(k="again", href="/book", who=hist[0]["doctor"], when=hist[0]["date"])
        else: nxt = dict(k="first", href="/book", who="", when="")
        steps = [("Log in with OTP", "ok", None), ("Choose a doctor and a time", "ok" if anyappt else "cur", "/book"),
                 ("Registration: your details and password (asked once, when you choose a doctor)", "ok" if registered else ("cur" if anyappt else "todo"), None),
                 ("Visit day: show the QR at reception, wait for your token, see the doctor, tests, medicines", "ok" if hist else ("cur" if up else "todo"), None),
                 ("History is saved: date, doctor, advice and reports are here the next time", "ok" if any(h["diagnosis"] or h["tests"] for h in hist) else "todo", "/history")]
        return dict(next=nxt, steps=steps, upcoming=[dict(x) for x in up], registered=registered, me=me)

    @app.route("/home")
    @pneed
    def home():
        uid = session["uid"]; j = journey(uid); w = session.pop("welcome", None)
        return render_template("home.html", j=j, hist=visit_history(uid, limit=6), docs_seen=doctors_seen(uid), recs=records_of(uid)[:4], first_visit=bool(w), pname=session.get("name"))

    @app.route("/history")
    @pneed
    def history(): return render_template("history.html", hist=visit_history(session["uid"], limit=300), docs_seen=doctors_seen(session["uid"]))

    # ------------------------------------------------------------ 3. registration details, asked when the first doctor is chosen
    @app.route("/register/details", methods=["GET", "POST"])
    @pneed
    def reg_details():
        uid = session["uid"]; pid = request.values.get("pid", type=int)
        p = mine_only(pid) if pid else next((x for x in my_profiles(uid) if x["relation"] == "Self"), None)
        if not p: abort(404)
        nxt = safe_next(request.values.get("next"), "/book"); is_self = p["relation"] == "Self"
        u = q("SELECT * FROM users WHERE id=?", (uid,), one=True); need_pw = is_self and not has_pw(u)
        qs = parse_qs(urlparse(nxt).query); doc = None
        try: doc = q("SELECT name,dept,designation FROM users WHERE id=? AND role='doctor'", (int(qs.get("doctor", [""])[0]),), one=True)
        except (ValueError, TypeError): pass
        if not missing(p) and p["uhid"] and not need_pw: return redirect(nxt)
        def page(vals, getl, code=200):
            return render_template("reg_details.html", p=vals, getlist=getl, pid=p["id"], is_self=is_self, nxt=nxt, doc=doc, need_pw=need_pw, mode="edit", **form_ctx()), code
        if request.method == "POST":
            f = request.form.copy()
            if is_self: f["phone"] = p["phone"]  # the login number is changed only through the hospital
            d, e = parse_patient(f, need_consent=True, phone_required=is_self)
            if not d["phone"]: d["phone"] = p["phone"]
            pw = request.form.get("pw", "")
            if need_pw:
                if len(pw) < 8 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw): e.append("Password needs at least 8 characters with a letter and a digit.")
                if pw != request.form.get("pw2", ""): e.append("The two passwords do not match.")
            if e:
                for x in e: flash(x)
                return page(f, f.getlist, 400)
            sets = ",".join(f"{k}=?" for k in FIELDS); q(f"UPDATE patients SET {sets},consent_ts=? WHERE id=?", [d.get(k) for k in FIELDS] + [ts(), p["id"]], commit=True)
            uhid = p["uhid"] or f"SGMH-{now().year % 100:02d}{p['id']:06d}"; q("UPDATE patients SET uhid=? WHERE id=?", (uhid, p["id"]), commit=True)
            if is_self:
                q("UPDATE users SET name=?,allergies=? WHERE id=?", (d["name"], d["allergies"] or None, uid), commit=True); session["name"] = d["name"]
                if need_pw: q("UPDATE users SET pw=? WHERE id=?", (gph(pw), uid), commit=True)
            audit(who(), "REGISTER_DETAILS", uhid + (" +password" if need_pw else ""))
            if not p["uhid"]: sms(d["phone"], f"SGMH Rewa: registration done. Your UHID is {uhid}. Keep it for all future visits.", uid)
            session["reg_done"] = uhid; flash("Registration complete. Now continue with the admission request." if nxt.startswith("/admit") else "Registration complete. Now choose a time for your appointment."); return redirect(nxt)
        cur = dict(p); cur["conditions_l"] = [x.strip() for x in (p["conditions"] or "").split(",")]
        return page(cur, lambda k: cur["conditions_l"] if k == "conditions" else [])

    # ------------------------------------------------------------ 5. own records (old prescriptions / reports)
    def can_open_record(r):
        if not r: return False
        return (session.get("role") == "patient" and r["owner_id"] == session.get("uid")) or session.get("role") in ("doctor", "reception", "nurse", "admin")

    @app.route("/records", methods=["GET", "POST"])
    @pneed
    def records():
        uid = session["uid"]; profs = my_profiles(uid)
        if request.method == "POST":
            f = request.files.get("file"); pid = request.form.get("pid", type=int)
            if pid not in [x["id"] for x in profs]: pid = profs[0]["id"]
            title = clip(request.form.get("title"), 80); rd = clip(request.form.get("rec_date"), 10); note = clip(request.form.get("note"), 300)
            if not title: flash("Give the record a short name, for example Old prescription."); return redirect("/records")
            if rd and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", rd): flash("Enter the date of the record."); return redirect("/records")
            if not f or not f.filename: flash("Choose a PDF, JPG or PNG file."); return redirect("/records")
            data = f.read(MAX_FILE + 1)
            if len(data) > MAX_FILE: flash("The file is larger than 5 MB."); return redirect("/records")
            kind = next((v for k, v in MAGIC.items() if data.startswith(k)), None)
            if not kind: flash("Only PDF, JPG or PNG files are allowed."); return redirect("/records")
            os.makedirs(UPLOADS, exist_ok=True); fname = secrets.token_hex(12) + "." + kind[0]
            with open(os.path.join(UPLOADS, fname), "wb") as fh: fh.write(data)
            q("INSERT INTO records(owner_id,pid,title,rec_date,note,fname,orig,mime,size,ts) VALUES(?,?,?,?,?,?,?,?,?,?)", (uid, pid, title, rd or None, note, fname, clip(f.filename, 80), kind[1], len(data), ts()), commit=True)
            audit(who(), "RECORD_UPLOAD", f"{title} ({len(data) // 1024} KB)"); flash("Saved. Your doctor can see this record at your next visit."); return redirect("/records")
        return render_template("records.html", recs=records_of(uid), profs=profs, today=now().date().isoformat())

    @app.route("/records/<int:rid>/file")
    def record_file(rid):
        r = q("SELECT * FROM records WHERE id=?", (rid,), one=True)
        if "uid" not in session: session["next"] = request.path; return redirect("/start")
        if not can_open_record(r): abort(404)
        audit(who(), "RECORD_VIEW", f"#{rid}"); return send_file(os.path.join(UPLOADS, r["fname"]), mimetype=r["mime"], download_name=r["orig"] or r["fname"], as_attachment=False)

    @app.route("/records/<int:rid>/delete", methods=["POST"])
    @pneed
    def record_delete(rid):
        r = q("SELECT * FROM records WHERE id=? AND owner_id=?", (rid, session["uid"]), one=True)
        if not r: abort(404)
        try: os.remove(os.path.join(UPLOADS, r["fname"]))
        except OSError: pass
        q("DELETE FROM records WHERE id=?", (rid,), commit=True); audit(who(), "RECORD_DELETE", f"#{rid}"); flash("Record deleted."); return redirect("/records")
