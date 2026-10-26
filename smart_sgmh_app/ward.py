"""Blood-bank stock (/blood-bank), IPD care team (/ward/<code>) and death record + signed certificate (/death/<code>).
All numbers shipped with the demo are SAMPLE until staff enter real ones.

DEATH CERTIFICATE - read this: what this makes is the hospital's DIGITALLY SIGNED DEATH SUMMARY / cause-of-death certificate for the family's use and for the hospital's record.
It is NOT the statutory death certificate. In India the legal certificate is issued by the Registrar of Births and Deaths after the death is registered (Registration of
Births and Deaths Act, 1969; the hospital doctor gives the Medical Certificate of Cause of Death). The hospital must confirm current rules/forms before real use.
The signature is an HMAC-SHA256 by this server (key = SECRET_KEY): it proves the text was not changed after signing. It is not a legal Digital Signature Certificate / Aadhaar eSign.
SET A STRONG SECRET_KEY in production, otherwise anyone can forge signatures."""
import os, re, io, json, hmac, hashlib, secrets
from datetime import datetime, timedelta
from flask import request, session, render_template, redirect, flash, abort, send_file, jsonify

GROUPS = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]
SAMPLE_UNITS = {"A+": 14, "A-": 2, "B+": 22, "B-": 0, "O+": 31, "O-": 3, "AB+": 8, "AB-": 0}   # SAMPLE
LOW, STALE_H = 10, 12
MANNER = ["Natural", "Accident", "Suicide", "Homicide", "Pending investigation", "Could not be determined"]
def level(u): return "ok" if u >= LOW else ("low" if u > 0 else "none")

def register(ns):
    app, q, db, ts, now, who, need, audit, FMT, cph, event, appt_row, can_view = (ns[k] for k in ("app", "q", "db", "ts", "now", "who", "need", "audit", "FMT", "cph", "event", "appt_row", "can_view"))
    c = db(); c.executescript("""
    CREATE TABLE IF NOT EXISTS bloodbank(grp TEXT PRIMARY KEY, units INT, updated TEXT, by TEXT);
    CREATE TABLE IF NOT EXISTS careteam(appt_id INTEGER PRIMARY KEY, duty_doctor TEXT, nurse TEXT, attendant TEXT, shift TEXT, fam_name TEXT, fam_rel TEXT, fam_phone TEXT, updated TEXT, by TEXT);
    CREATE TABLE IF NOT EXISTS deaths(id INTEGER PRIMARY KEY, appt_id INTEGER UNIQUE, cert_no TEXT UNIQUE, token TEXT UNIQUE, payload TEXT, sig TEXT, declared_by TEXT, created TEXT);""")
    if not c.execute("SELECT 1 FROM bloodbank").fetchone():
        for g in GROUPS: c.execute("INSERT INTO bloodbank VALUES(?,?,?,?)", (g, SAMPLE_UNITS[g], ts(), "sample data"))
    c.commit(); c.close()
    from i18n import HI; from i18n_care import CARE_HI, PATTERNS
    for _k, _v in CARE_HI.items(): HI.setdefault(_k, _v)
    ns["PAT"].extend(PATTERNS)
    clip = lambda s, n=200: (s or "").strip()[:n]
    KEY = lambda: (app.secret_key if isinstance(app.secret_key, bytes) else str(app.secret_key).encode())
    sign = lambda payload: hmac.new(KEY(), payload.encode(), hashlib.sha256).hexdigest()
    careteam = lambda aid: q("SELECT * FROM careteam WHERE appt_id=?", (aid,), one=True)
    def death_of(aid):
        r = q("SELECT * FROM deaths WHERE appt_id=?", (aid,), one=True)
        return dict(r, d=json.loads(r["payload"])) if r else None
    app.context_processor(lambda: dict(careteam=careteam, death_of=death_of))

    # ---------- blood bank ----------
    def stock():
        out = []
        for r in q("SELECT * FROM bloodbank"):
            try: h = (now() - datetime.strptime(r["updated"], FMT)).total_seconds() / 3600
            except Exception: h = 999
            out.append(dict(grp=r["grp"], units=r["units"], level=level(r["units"]), updated=r["updated"], by=r["by"], stale=h > STALE_H, hours=int(h)))
        return sorted(out, key=lambda x: GROUPS.index(x["grp"]) if x["grp"] in GROUPS else 99)
    @app.route("/blood-bank")
    def blood_bank(): return render_template("blood_bank.html", rows=stock(), can_edit=session.get("role") in ("lab", "admin"), low=LOW, sample=bool(q("SELECT 1 FROM bloodbank WHERE by='sample data'", one=True)))
    @app.route("/api/blood-bank")
    def api_blood_bank(): return jsonify(stock=[{k: r[k] for k in ("grp", "units", "level", "updated", "stale")} for r in stock()], low_below=LOW)
    @app.route("/blood-bank/update", methods=["POST"])
    @need("lab")
    def blood_update():
        g, u = request.form.get("grp", ""), request.form.get("units", "")
        if g not in GROUPS or not u.isdigit() or int(u) > 999: flash("Choose a blood group and enter units (0 to 999)."); return redirect("/blood-bank")
        q("UPDATE bloodbank SET units=?,updated=?,by=? WHERE grp=?", (int(u), ts(), who(), g), commit=True); audit(who(), "BLOOD_STOCK", f"{g}={u}"); flash(f"{g} updated to {u} units."); return redirect("/blood-bank")

    # ---------- care team ----------
    def ipd(code): return q(f"SELECT a.*,{ns['PCOLS']},d.name doctor FROM appts a {ns['PJOIN']} JOIN users d ON d.id=a.doctor_id WHERE a.code=? AND a.kind='IPD'", (code,), one=True)
    @app.route("/ward/<code>", methods=["GET", "POST"])
    @need("reception", "nurse", "doctor")
    def ward(code):
        a = ipd(code)
        if not a: abort(404)
        if a["status"] == "deceased": flash("Patient is recorded as deceased. The care team is frozen in the certificate."); return redirect(f"/death/{code}/certificate")
        if request.method == "POST":
            f = request.form; ph = re.sub(r"\D", "", f.get("fam_phone", ""))
            if ph and len(ph) != 10: flash("Family phone must be 10 digits."); return redirect(f"/ward/{code}")
            q("INSERT INTO careteam(appt_id,duty_doctor,nurse,attendant,shift,fam_name,fam_rel,fam_phone,updated,by) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(appt_id) DO UPDATE SET duty_doctor=excluded.duty_doctor,nurse=excluded.nurse,attendant=excluded.attendant,shift=excluded.shift,fam_name=excluded.fam_name,fam_rel=excluded.fam_rel,fam_phone=excluded.fam_phone,updated=excluded.updated,by=excluded.by",
              (a["id"], clip(f.get("duty_doctor"), 80), clip(f.get("nurse"), 80), clip(f.get("attendant"), 80), clip(f.get("shift"), 40), clip(f.get("fam_name"), 80), clip(f.get("fam_rel"), 30), ph, ts(), who()), commit=True)
            audit(who(), "CARE_TEAM", code); flash("Care team saved."); return redirect(f"/ward/{code}")
        return render_template("ward.html", a=a, t=careteam(a["id"]))

    # ---------- death record + certificate ----------
    def admitted_ts(a):
        r = q("SELECT ts FROM events WHERE appt_id=? AND cp='Ward' ORDER BY id DESC LIMIT 1", (a["id"],), one=True)
        return r["ts"] if r else a["created"]
    def stay(a, dt):
        adm = datetime.strptime(admitted_ts(a), FMT); secs = max(0, (dt - adm).total_seconds())
        return int(secs // 86400), int((secs % 86400) // 3600), adm
    @app.route("/death/<code>", methods=["GET", "POST"])
    @need("doctor")
    def death_declare(code):
        a = ipd(code)
        if not a: abort(404)
        if session.get("role") != "doctor": abort(403)
        if a["status"] == "deceased": return redirect(f"/death/{code}/certificate")
        if a["status"] != "admitted": flash("Death can be recorded only for a patient who is currently admitted."); return redirect("/doctor")
        t = careteam(a["id"]); adm = admitted_ts(a)
        if request.method == "POST":
            f = request.form
            def back(m): flash(m); return redirect(f"/death/{code}")
            try: dt = datetime.strptime(f.get("death_ts", ""), "%Y-%m-%dT%H:%M")
            except ValueError: return back("Enter the date and time of death.")
            if dt > now() + timedelta(minutes=5): return back("Time of death cannot be in the future.")
            if dt < datetime.strptime(adm, FMT).replace(second=0): return back("Time of death cannot be before the admission time (" + adm[:16] + ").")
            ci, cu, mn, reg = clip(f.get("cause_immediate"), 200), clip(f.get("cause_underlying"), 200), f.get("manner", ""), clip(f.get("regno"), 40)
            if not ci or not reg or mn not in MANNER: return back("Immediate cause of death, manner and your medical registration number are required.")
            if not f.get("certify"): return back("Please tick the certification box.")
            me = q("SELECT pw,name FROM users WHERE id=?", (session["uid"],), one=True)
            if not cph(me["pw"], f.get("password", "")): audit(who(), "DEATH_SIGN_BAD_PASSWORD", code); return back("Password is wrong. The signature was not applied.")
            days, hrs, admdt = stay(a, dt); cal = (dt.date() - admdt.date()).days + 1
            no = f"SGMH-D-{dt.year}-{secrets.token_hex(3).upper()}"
            sex = a["pgender"] or ""; age = a["page"]
            payload = dict(cert_no=no, hospital="Sanjay Gandhi Memorial Hospital, Rewa (M.P.)", issued_ts=ts(), uhid=a["uhid"] or "", patient_name=a["pname"], age_sex=(f"{age} yrs" if age not in (None, "") else "") + (" / " + sex if sex else ""),
                           ward=a["ward"] if "ward" in a.keys() else "", bed=a["bed"] or "", admitted_ts=adm, death_ts=dt.strftime(FMT), stay_days=days, stay_hours=hrs, calendar_days=cal,
                           cause_immediate=ci, cause_underlying=cu, manner=mn, mlc=0 if mn == "Natural" else 1, declared_by=me["name"], regno=reg, treating_doctor=a["doctor"],
                           duty_doctor=(t["duty_doctor"] if t else "") or "", nurse=(t["nurse"] if t else "") or "", attendant=(t["attendant"] if t else "") or "", shift=(t["shift"] if t else "") or "",
                           family_attendant=(t["fam_name"] if t else "") or "", family_relation=(t["fam_rel"] if t else "") or "")
            js = json.dumps(payload, sort_keys=True, ensure_ascii=False)
            q("INSERT INTO deaths(appt_id,cert_no,token,payload,sig,declared_by,created) VALUES(?,?,?,?,?,?,?)", (a["id"], no, secrets.token_urlsafe(12), js, sign(js), who(), ts()), commit=True)
            q("UPDATE appts SET status='deceased' WHERE id=?", (a["id"],), commit=True); event(a["id"], "Death"); audit(who(), "DEATH_DECLARED", f"{code} {no} at {payload['death_ts']}")
            try: q("INSERT INTO notifications(user_id,appt_code,phone,ts,text,channel) VALUES(?,?,?,?,?,'SMS')", (a["patient_id"], code, a["pphone"], ts(), f"SGMH: we are deeply sorry. The hospital death summary {no} is ready. Please contact the IPD desk. Open the Visit page to view it.", ), commit=True)
            except Exception: pass
            flash("Death recorded and the certificate was digitally signed. This cannot be edited."); return redirect(f"/death/{code}/certificate")
        return render_template("death_form.html", a=a, t=t, adm=adm, manners=MANNER, now=now().strftime("%Y-%m-%dT%H:%M"), already=0)

    @app.route("/death/<code>/certificate")
    def death_cert(code):
        a = ipd(code)
        if not a or not can_view(a, code): abort(404)
        d = death_of(a["id"])
        if not d: abort(404)
        ok = hmac.compare_digest(sign(d["payload"]), d["sig"]); audit(who() if session.get("role") else "family", "DEATH_CERT_VIEW", code)
        return render_template("death_cert.html", a=a, d=d["d"], rec=d, ok=ok, verify_url=request.host_url.rstrip("/") + "/death/verify/" + d["token"])
    @app.route("/death/verify/<token>")
    def death_verify(token):
        r = q("SELECT * FROM deaths WHERE token=?", (token,), one=True)
        if not r: return render_template("death_verify.html", r=None), 404
        return render_template("death_verify.html", r=r, d=json.loads(r["payload"]), ok=hmac.compare_digest(sign(r["payload"]), r["sig"]))
    @app.route("/death/qr/<token>.png")
    def death_qr(token):
        if not q("SELECT 1 FROM deaths WHERE token=?", (token,), one=True): abort(404)
        import qrcode; b = io.BytesIO(); qrcode.make(request.host_url.rstrip("/") + "/death/verify/" + token).save(b, "PNG"); b.seek(0); return send_file(b, mimetype="image/png")
