"""Ward duty: who is on duty in which ward, and what that means for alerts, the care team and the ward view.

1. WARD DUTY ROSTER (/admin/ward-duty, admin): every nurse and doctor can be given one or more wards and a shift.
2. WARD-WISE ALERTS: an alert about an admitted patient goes to
      - the patient's treating doctor and the duty doctor on the care team,
      - every doctor and nurse on duty in that ward,
      - everybody (doctors, nurses) once it is ESCALATED because nobody acknowledged it in time (the "supervisor" step),
   and NOT to staff of other wards. Admin sees all. A nurse who has no ward yet still sees everything (fail-safe: no alert may get lost
   just because the roster is empty). Alerts about OPD visits go to the treating doctor and to all nurses, as before.
   Each alert also shows "Sent to: ..." so everybody can see who was told.
3. AUTO CARE TEAM: when a patient is admitted (reception bed, emergency admit, doctor referral + bed) the care team card is filled from the
   ward roster (duty doctor, duty nurses, shift) and from the attendant given at admission. Staff can still edit it afterwards.
4. WARD LIVE VIEW (/wardview): one ward at a time: duty staff, every admitted patient with bed, diagnosis, treating doctor, latest vitals,
   open alerts and "doctor review pending". Doctors and nurses use it; reception and patients do not see clinical columns.
Sample roster is created on first start (only if the roster is empty). The hospital must enter its real duty roster."""
import json, os, re
from flask import request, session, render_template, redirect, flash, abort, jsonify
from werkzeug.security import generate_password_hash as gph

SHIFTS = ["Morning (8-2)", "Evening (2-8)", "Night (8-8)", "All day"]
# SAMPLE roster: (phone of staff, ward, shift). Nurses with phone 9000000061..63 are created as sample accounts.
SAMPLE_NURSES = [("Nurse Sunita (ICU)", "9000000061"), ("Nurse Rekha (Maternity)", "9000000062"), ("Nurse Meena (Paediatric)", "9000000063")]
SAMPLE_DUTY = [("9000000060", "General ward", "Morning (8-2)"), ("9000000060", "Private room", "Morning (8-2)"),
               ("9000000061", "ICU / HDU", "All day"), ("9000000062", "Maternity ward", "All day"), ("9000000063", "Paediatric ward", "All day"),
               ("9000000041", "General ward", "All day"), ("9000000045", "ICU / HDU", "All day"), ("9000000044", "Maternity ward", "All day"),
               ("9000000043", "Paediatric ward", "All day")]


def register(ns):
    app, q, db, ts, now, who, need, audit, appt_row = (ns[k] for k in ("app", "q", "db", "ts", "now", "who", "need", "audit", "appt_row"))
    WARDS = ns["WARDS"]; esc_min = lambda: int(os.environ.get("ESCALATE_MIN", 10))

    c = db()
    c.executescript("CREATE TABLE IF NOT EXISTS ward_duty(user_id INTEGER, ward TEXT, shift TEXT, updated TEXT, by TEXT, PRIMARY KEY(user_id, ward));")
    if os.environ.get("DEMO_MODE", "1") == "1" and not c.execute("SELECT 1 FROM ward_duty LIMIT 1").fetchone():  # first start only, demo mode only: sample nurses + roster (DEMO_MODE=0 in production creates nothing)
        for nm, ph in SAMPLE_NURSES:
            if not c.execute("SELECT 1 FROM users WHERE phone=?", (ph,)).fetchone():
                c.execute("INSERT INTO users(name,phone,role,pw,dept) VALUES(?,?,'nurse',?,NULL)", (nm, ph, gph("nurse123")))
        for ph, ward, sh in SAMPLE_DUTY:
            u = c.execute("SELECT id FROM users WHERE phone=?", (ph,)).fetchone()
            if u: c.execute("INSERT OR IGNORE INTO ward_duty(user_id,ward,shift,updated,by) VALUES(?,?,?,?,?)", (u["id"], ward, sh, ts(), "sample roster"))
    c.commit(); c.close()

    def my_wards(uid): return [r["ward"] for r in q("SELECT ward FROM ward_duty WHERE user_id=? ORDER BY ward", (uid,))]
    def shift_on(shift, at=None):
        """Is this roster shift running right now? Morning 8-14, Evening 14-20, Night 20-8, All day always."""
        h = (at or now()).hour
        return {"Morning (8-2)": 8 <= h < 14, "Evening (2-8)": 14 <= h < 20, "Night (8-8)": h >= 20 or h < 8}.get(shift, True)
    def duty_staff(ward, role=None):
        rows = q("SELECT u.id,u.name,u.role,u.dept,d.shift FROM ward_duty d JOIN users u ON u.id=d.user_id WHERE d.ward=?" + (" AND u.role=?" if role else "") + " ORDER BY u.role,u.name",
                 (ward, role) if role else (ward,))
        return [dict(r, on=shift_on(r["shift"])) for r in rows]
    def duty_live(ward):
        """Who is on duty in this ward RIGHT NOW (shift-aware). Used for the care-team card, alerts and the family view."""
        on = [s for s in duty_staff(ward) if s["on"]] if ward else []
        return dict(doctors=[s["name"] for s in on if s["role"] == "doctor"], nurses=[s["name"] for s in on if s["role"] == "nurse"], shift=(on[0]["shift"] if on else ""), rostered=bool(on))

    # ------------------------------------------------------------------ who may see which alert
    def scope(role=None, uid=None, name=None):
        """SQL (on alias al = alerts, a = appts) + args for the alerts this staff member should see."""
        role = role or session.get("role"); uid = uid or session.get("uid"); name = name or session.get("name")
        if role == "admin": return "1=1", ()
        wards = my_wards(uid); ph = ",".join("?" * len(wards))
        if role == "nurse":
            if not wards: return "1=1", ()  # roster not set for this nurse: show everything rather than hide a critical alert
            return f"(al.status='escalated' OR a.kind!='IPD' OR a.ward IN ({ph}))", tuple(wards)
        parts, args = ["al.status='escalated'", "a.doctor_id=?", "EXISTS(SELECT 1 FROM careteam ct WHERE ct.appt_id=a.id AND ct.duty_doctor=?)"], [uid, name]
        if wards: parts.append(f"(a.kind='IPD' AND a.ward IN ({ph}))"); args += wards
        return "(" + " OR ".join(parts) + ")", tuple(args)

    def recipients(appt_id):
        """Names shown as 'Sent to' on an alert."""
        a = q("SELECT a.*,d.name dname FROM appts a JOIN users d ON d.id=a.doctor_id WHERE a.id=?", (appt_id,), one=True)
        if not a: return []
        out = [f"{a['dname']} (treating doctor)"]
        ct = q("SELECT duty_doctor FROM careteam WHERE appt_id=?", (appt_id,), one=True)
        if ct and ct["duty_doctor"] and ct["duty_doctor"] != a["dname"]: out.append(f"{ct['duty_doctor']} (duty doctor)")
        if a["kind"] == "IPD" and a["ward"]:
            allst = duty_staff(a["ward"]); live = [s for s in allst if s["on"]]
            for s in (live or allst):
                lab = ("duty doctor" if s["role"] == "doctor" else "duty nurse") + ("" if s["on"] else ", off shift now")
                if s["name"] not in (a["dname"], (ct or {"duty_doctor": None})["duty_doctor"]): out.append(f"{s['name']} ({lab}, {a['ward']}, {s['shift']})")
        elif a["kind"] != "IPD": out.append("Nursing station")
        return out

    def visible(aid):
        sql, args = scope()
        return bool(q(f"SELECT 1 FROM alerts al JOIN appts a ON a.id=al.appt_id WHERE al.id=? AND {sql}", (aid,) + args, one=True))

    @need("doctor", "nurse")
    def alerts_page():
        ns["escalate_overdue"](); sql, args = scope()
        rows = q(f"SELECT al.*,a.code,a.ward,a.bed,COALESCE(pt.name,p.name) pname FROM alerts al JOIN appts a ON a.id=al.appt_id LEFT JOIN users p ON p.id=a.patient_id LEFT JOIN patients pt ON pt.id=a.pid "
                 f"WHERE {sql} ORDER BY (al.status IN ('open','escalated')) DESC, al.id DESC LIMIT 60", args)
        mine = my_wards(session["uid"])
        return render_template("alerts.html", rows=[dict(r, steps=json.loads(r["trace"] or "[]"), sent_to=recipients(r["appt_id"])) for r in rows], esc=esc_min(), my_wards=mine, role=session.get("role"))

    def alerts_count():
        if session.get("role") not in ("doctor", "nurse", "admin"): return jsonify(error="forbidden"), 403
        ns["escalate_overdue"](); sql, args = scope()
        r = q(f"SELECT COALESCE(SUM(al.status='open'),0) o, COALESCE(SUM(al.status='escalated'),0) e FROM alerts al JOIN appts a ON a.id=al.appt_id WHERE {sql}", args, one=True)
        return jsonify(open=r["o"], escalated=r["e"])

    def alerts_latest():
        if session.get("role") not in ("doctor", "nurse", "admin"): return jsonify(error="forbidden"), 403
        ns["escalate_overdue"](); sql, args = scope()
        rows = q(f"SELECT al.id,al.level,al.kind,al.message,al.status,a.code FROM alerts al JOIN appts a ON a.id=al.appt_id WHERE al.status IN ('open','escalated') AND {sql} ORDER BY al.id DESC LIMIT 5", args)
        return jsonify(alerts=[dict(r, kind=r["kind"].replace("_", " ")) for r in rows])

    old_act = app.view_functions["alert_act"]
    def alert_act(aid, act):
        if session.get("role") in ("doctor", "nurse") and not visible(aid): abort(403)  # cannot act on another ward's alert
        return old_act(aid, act)

    app.view_functions["alerts_page"] = alerts_page
    app.view_functions["alerts_count"] = alerts_count
    app.view_functions["alerts_latest"] = alerts_latest
    app.view_functions["alert_act"] = alert_act

    # ------------------------------------------------------------------ auto care team
    def auto_team(code):
        a = q("SELECT a.*,d.name dname FROM appts a JOIN users d ON d.id=a.doctor_id WHERE a.code=? AND a.kind='IPD' AND a.status='admitted'", (code,), one=True)
        if not a or q("SELECT 1 FROM careteam WHERE appt_id=?", (a["id"],), one=True): return False
        docs = [s for s in duty_staff(a["ward"], "doctor") if s["on"]] if a["ward"] else []  # only those whose shift is running now
        nurses = [s for s in duty_staff(a["ward"], "nurse") if s["on"]] if a["ward"] else []
        on_leave = {r["doctor_id"] for r in q("SELECT doctor_id FROM doctor_avail WHERE status='leave'")}
        duty = next((s["name"] for s in docs if s["id"] not in on_leave), None) or a["dname"]
        shift = (nurses or docs or [{"shift": ""}])[0]["shift"]
        q("INSERT OR IGNORE INTO careteam(appt_id,duty_doctor,nurse,attendant,shift,fam_name,fam_rel,fam_phone,updated,by) VALUES(?,?,?,?,?,?,?,?,?,?)",
          (a["id"], duty, ", ".join(s["name"] for s in nurses), "", shift, a["att_name"] or "", a["att_rel"] or "", re.sub(r"\D", "", a["att_phone"] or ""), ts(), "auto: ward duty roster"), commit=True)
        audit(who(), "CARE_TEAM_AUTO", f"{code} {a['ward']}"); return True

    orig_bed = ns["_ipd_bed_transition"]
    def bed_transition(appt_code, new_status, bed_number=None, actor="system"):
        r = orig_bed(appt_code, new_status, bed_number, actor)
        if r[0] and new_status == "admitted":
            try: auto_team(appt_code)
            except Exception as e: print("auto care team failed:", e)
        return r
    ns["_ipd_bed_transition"] = bed_transition

    @app.before_request
    def _fill_team():  # also covers an emergency admission whose bed count could not be confirmed
        m = re.match(r"^/(?:ward|ipd|visit|patient)/(IP-[A-Z0-9]+)", request.path)
        if m and session.get("uid"):
            try: auto_team(m.group(1))
            except Exception: pass

    # ------------------------------------------------------------------ admin: roster
    @app.route("/admin/ward-duty", methods=["GET", "POST"])
    @need("admin")
    def ward_duty_admin():
        if request.method == "POST":
            uid = request.form.get("user_id", type=int); u = q("SELECT * FROM users WHERE id=? AND role IN ('nurse','doctor')", (uid,), one=True)
            if not u: abort(404)
            chosen = [w for w in request.form.getlist("ward") if w in WARDS]; sh = request.form.get("shift") if request.form.get("shift") in SHIFTS else SHIFTS[3]
            q("DELETE FROM ward_duty WHERE user_id=?", (uid,), commit=True)
            for w in chosen: q("INSERT INTO ward_duty(user_id,ward,shift,updated,by) VALUES(?,?,?,?,?)", (uid, w, sh, ts(), who()), commit=True)
            audit(who(), "WARD_DUTY", f"{u['name']}: {', '.join(chosen) or 'none'} / {sh}"); flash(f"{u['name']}: duty saved."); return redirect("/admin/ward-duty")
        staff = []
        for u in q("SELECT id,name,role,dept FROM users WHERE role IN ('nurse','doctor') ORDER BY role DESC,name"):
            d = q("SELECT ward,shift FROM ward_duty WHERE user_id=?", (u["id"],)); staff.append(dict(u=u, wards=[x["ward"] for x in d], shift=(d[0]["shift"] if d else SHIFTS[3])))
        staff.sort(key=lambda x: (not x["wards"], x["u"]["role"] != "nurse", x["u"]["name"]))
        return render_template("ward_duty_admin.html", staff=staff[:150], wards=WARDS, shifts=SHIFTS, total=len(staff))

    # ------------------------------------------------------------------ ward live view
    @app.route("/wardview")
    @need("doctor", "nurse", "admin")
    def wardview():
        mine = my_wards(session["uid"]); ward = request.args.get("ward")
        if ward not in WARDS: ward = mine[0] if mine else WARDS[0]
        rows = q(f"SELECT a.id,a.code,a.bed,a.adm_type,a.dept,a.date,a.doctor_id,{ns['PCOLS']},d.name doctor FROM appts a {ns['PJOIN']} JOIN users d ON d.id=a.doctor_id "
                 "WHERE a.kind='IPD' AND a.status='admitted' AND a.ward=? ORDER BY a.bed", (ward,))
        pts = []
        for r in rows:
            auto_team(r["code"])
            v = q("SELECT level,score,ts,pulse,spo2,bp_sys,bp_dia,temp FROM vitals WHERE appt_id=? ORDER BY id DESC LIMIT 1", (r["id"],), one=True)
            i = q("SELECT * FROM ipd_info WHERE appt_id=?", (r["id"],), one=True)
            dx = q("SELECT diagnosis FROM ipd_notes WHERE appt_id=? AND diagnosis!='' ORDER BY COALESCE(event_ts,ts) DESC,id DESC LIMIT 1", (r["id"],), one=True)
            al = q("SELECT level,status FROM alerts WHERE appt_id=? AND status IN ('open','escalated')", (r["id"],))
            sev = 3 if any(x["level"] == "critical" for x in al) or (v and v["level"] == "critical") else 2 if al or (v and v["level"] == "warning") or (i and i["review_pending"]) else 1 if v else 0
            pts.append(dict(r=r, v=v, i=i, dx=(dx["diagnosis"] if dx else "") or "", al=al, sev=sev, team=q("SELECT * FROM careteam WHERE appt_id=?", (r["id"],), one=True), mine=(r["doctor_id"] == session["uid"])))
        pts.sort(key=lambda x: (-x["sev"], x["r"]["bed"] or ""))
        counts = {w: q("SELECT COUNT(*) n FROM appts WHERE kind='IPD' AND status='admitted' AND ward=?", (w,), one=True)["n"] for w in WARDS}
        crit = {w: q("SELECT COUNT(*) n FROM alerts al JOIN appts a ON a.id=al.appt_id WHERE a.kind='IPD' AND a.ward=? AND al.status IN ('open','escalated') AND al.level='critical'", (w,), one=True)["n"] for w in WARDS}
        return render_template("wardview.html", ward=ward, wards=WARDS, pts=pts, counts=counts, crit=crit, mine=mine,
                               nurses=duty_staff(ward, "nurse"), doctors=duty_staff(ward, "doctor"), role=session["role"])

    app.context_processor(lambda: dict(duty_live=duty_live))
    ns.update(duty_live=duty_live, ward_shift_on=shift_on, ward_scope=scope, ward_recipients=recipients, ward_auto_team=auto_team, ward_my_wards=my_wards)
