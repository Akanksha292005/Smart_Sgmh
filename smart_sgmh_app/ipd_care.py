"""IPD care: doctor referral to admission, emergency direct admit, the IPD clinical chart and the discharge summary.

1. REFER TO ADMIT (/doctor/<code>/refer-admit): an OPD doctor sends the patient to IPD. An admission request is created at once, linked to the OPD visit,
   with the diagnosis and OPD advice copied into the first chart entry. Reception only has to give a bed.
2. EMERGENCY ADMIT (/emergency): reception / nurse / doctor admit a patient WITHOUT waiting for a doctor and without a booking. Unknown patients get a temporary
   UHID ("Unknown male ~40 yrs"), can be identified later (/ipd/<code>/identify) and merged into an existing record. The duty doctor gets a CRITICAL/WARNING
   alert, the patient shows as "doctor review pending" and cannot be discharged until a doctor has filed the first assessment. Nothing is blocked by a full ward:
   an emergency never waits for a bed count.
3. CHART (/ipd/<code>/chart): admission note, daily rounds, procedure notes (doctor), nursing notes (nurse), medicine orders (go to the pharmacy queue with the same
   safety checks as OPD), lab orders, vitals. "Time of event" lets staff record treatment that was given earlier (casualty) so nothing is lost.
4. DISCHARGE SUMMARY (/ipd/<code>/summary): doctor writes + approves; the patient/family then see it. IPD_SUMMARY_REQUIRED=1 makes it mandatory before discharge.
5. BOARD (/ipd/board): all admitted patients, who is waiting for a doctor, latest vitals, open alerts.
Wards, triage levels and thresholds are SAMPLE until the hospital confirms them. Tests: python tests_ipd_care.py"""
import os, re
from datetime import datetime, timedelta
from flask import request, session, render_template, redirect, flash, abort

TRIAGE = [("Red", "Immediate: life-threatening"), ("Orange", "Very urgent"), ("Yellow", "Urgent")]
DOC_KINDS = [("admission", "Admission / first assessment"), ("round", "Daily round / progress"), ("procedure", "Procedure / surgery note")]
KIND_LABEL = dict(DOC_KINDS, nursing="Nursing note", casualty="Casualty entry (emergency)")
CONDITIONS = ["Improved", "Stable", "Not improved", "Referred to another hospital", "Left against medical advice"]
MOBILE = re.compile(r"^[6-9]\d{9}$")
EMERG_WAIT_WARN_MIN = int(os.environ.get("EMERG_WAIT_WARN_MIN", 15))  # minutes after which "doctor review pending" turns red


def register(ns):
    app, q, db, ts, now, who, need, audit, FMT, event, appt_row, can_view = (ns[k] for k in ("app", "q", "db", "ts", "now", "who", "need", "audit", "FMT", "event", "appt_row", "can_view"))
    code, WARDS, red_flag = ns["code"], ns["WARDS"], ns["red_flag"]
    clip = lambda s, n=400: " ".join((s or "").split())[:n]
    block = lambda s, n=3000: (s or "").strip()[:n]

    c = db(); c.executescript("""
    CREATE TABLE IF NOT EXISTS ipd_info(appt_id INTEGER PRIMARY KEY, emergency INT DEFAULT 0, triage TEXT, complaint TEXT, first_aid TEXT, id_pending INT DEFAULT 0,
        review_pending INT DEFAULT 0, reviewed_by TEXT, reviewed_ts TEXT, ref_from TEXT, ref_by TEXT, ref_note TEXT, entered_by TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS ipd_notes(id INTEGER PRIMARY KEY, appt_id INT, kind TEXT, ts TEXT, event_ts TEXT, author TEXT, role TEXT, diagnosis TEXT, findings TEXT, orders TEXT, plan TEXT);
    CREATE INDEX IF NOT EXISTS ix_ipdn ON ipd_notes(appt_id, id);
    CREATE TABLE IF NOT EXISTS ipd_summary(appt_id INTEGER PRIMARY KEY, final_dx TEXT, course TEXT, procedures TEXT, meds_home TEXT, advice TEXT, followup_date TEXT, cond TEXT,
        approved INT DEFAULT 0, by TEXT, ts TEXT, approved_ts TEXT);""")
    try: c.execute("ALTER TABLE ipd_notes ADD COLUMN family_text TEXT")
    except Exception: pass
    c.commit(); c.close()

    info = lambda aid: q("SELECT * FROM ipd_info WHERE appt_id=?", (aid,), one=True)
    ipd_row = lambda cd: q(f"SELECT a.*,{ns['PCOLS']},d.name doctor FROM appts a {ns['PJOIN']} JOIN users d ON d.id=a.doctor_id WHERE a.code=? AND a.kind='IPD'", (cd,), one=True)
    summary_of = lambda aid: q("SELECT * FROM ipd_summary WHERE appt_id=?", (aid,), one=True)
    def minutes_since(t):
        try: return int((now() - datetime.strptime(t, FMT)).total_seconds() // 60)
        except Exception: return 0
    def parse_dt(s):
        try: return datetime.strptime((s or "").strip(), "%Y-%m-%dT%H:%M")
        except ValueError: return None
    def add_note(aid, kind, role_by=None, **k):
        return q("INSERT INTO ipd_notes(appt_id,kind,ts,event_ts,author,role,diagnosis,findings,orders,plan,family_text) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                 (aid, kind, ts(), k.get("event_ts"), who(), session.get("role"), k.get("diagnosis", ""), k.get("findings", ""), k.get("orders", ""), k.get("plan", ""), k.get("family_text") or None), commit=True)
    def admitted_ts(a):
        r = q("SELECT ts FROM events WHERE appt_id=? AND cp='Ward' ORDER BY id DESC LIMIT 1", (a["id"],), one=True)
        return r["ts"] if r else a["created"]

    @app.context_processor
    def _ctx():
        return dict(ipd_meta=info, ipd_summary_ok=lambda aid: bool((summary_of(aid) or {"approved": 0})["approved"]),
                    ipd_from_opd=lambda cd: q("SELECT a.code,a.status,a.ward FROM ipd_info i JOIN appts a ON a.id=i.appt_id WHERE i.ref_from=? ORDER BY a.id DESC", (cd,), one=True),
                    ipd_wards=WARDS, ipd_waiting_n=lambda: q("SELECT COUNT(*) n FROM ipd_info i JOIN appts a ON a.id=i.appt_id WHERE i.review_pending=1 AND a.status='admitted'", one=True)["n"])

    # ------------------------------------------------------------------ 1. doctor refers an OPD patient for admission
    @app.route("/doctor/<c>/refer-admit", methods=["POST"])
    @need("doctor")
    def refer_admit(c):
        a = appt_row(c)
        if not a or a["doctor_id"] != session["uid"] or a["kind"] != "OPD": abort(404)
        f = request.form; back = redirect(f"/doctor/{c}")
        ward = f.get("ward"); typ = f.get("type"); reason = clip(f.get("reason"), 200)
        if a["status"] in ("cancelled", "deceased"): flash("This visit is closed. Admission cannot be requested from it."); return back
        if a["status"] == "booked": flash("This patient has not been checked in at reception yet. Admission can be sent only after the patient has come for the OPD visit."); return back
        if ward not in WARDS or typ not in ("Planned", "Urgent") or len(reason) < 3: flash("Choose the ward, how urgent it is, and write the reason for admission."); return back
        if not a["pid"]: flash("This older booking has no patient profile. Ask reception to register the patient first."); return back
        ex = q("SELECT code,status FROM appts WHERE pid=? AND kind='IPD' AND status IN ('booked','admitted')", (a["pid"],), one=True)
        if ex: flash(f"This patient already has an admission ({ex['code']}, {ex['status']})."); return back
        cd = code("IP-"); td = now().date().isoformat(); n = q("SELECT * FROM notes WHERE appt_id=?", (a["id"],), one=True)
        aid = q("INSERT INTO appts(code,patient_id,doctor_id,dept,date,slot,reason,created,kind,ward,pid,prio,prio_why,referred_by,src,adm_type) VALUES(?,?,?,?,?,'24x7',?,?,'IPD',?,?,?,?,?,'referral',?)",
                (cd, a["patient_id"], a["doctor_id"], a["dept"], td, reason, ts(), ward, a["pid"], max(a["prio"] or 0, 1 if typ == "Urgent" else 0),
                 ", ".join(x for x in [a["prio_why"], "Urgent admission" if typ == "Urgent" else None] if x) or None, f"{a['doctor']} (OPD {c})", typ), commit=True)
        q("INSERT INTO ipd_info(appt_id,ref_from,ref_by,ref_note,entered_by,created) VALUES(?,?,?,?,?,?)", (aid, c, a["doctor"], reason, who(), ts()), commit=True)
        dx = (n["diagnosis"] if n else "") or ""
        carried = [f"Referred from OPD visit {c} by {a['doctor']} ({a['dept']}). Reason: {reason}."]
        if a["reason"]: carried.append(f"Complaint at OPD: {a['reason']}.")
        if n and (n["meds"] or "").strip(): carried.append("OPD medicines: " + "; ".join(x.strip() for x in n["meds"].splitlines() if x.strip()) + ".")
        if n and (n["tests_advised"] or "").strip(): carried.append("OPD tests advised: " + ", ".join(n["tests_advised"].splitlines()) + ".")
        if a["pallergy"]: carried.append("ALLERGY: " + a["pallergy"] + ".")
        add_note(aid, "admission", diagnosis=dx, findings=" ".join(carried))
        event(aid, "Registered"); audit(who(), "ADMIT_REFERRED", f"{cd} from {c} {typ} {ward}")
        ns["patient_notice"](aid, f"{a['doctor']} has advised admission ({typ.lower()}, {ward}). Your admission code is {cd}. Go to the IPD admission desk with this code, a photo ID and one family attendant. Everything from your OPD visit is already with the ward.", "advice")
        flash(f"Admission request {cd} created and sent to reception. The patient was told."); return back

    # ------------------------------------------------------------------ 2. emergency direct admit
    def pick_doctor(dept, ward=None):
        if ward:  # the doctor on duty in that ward comes first (ward duty roster), unless on leave
            try:
                r = q("SELECT u.id,u.name FROM ward_duty w JOIN users u ON u.id=w.user_id LEFT JOIN doctor_avail da ON da.doctor_id=u.id WHERE w.ward=? AND u.role='doctor' AND COALESCE(da.status,'available')!='leave' ORDER BY (COALESCE(da.status,'available')='available') DESC,u.id LIMIT 1", (ward,), one=True)
                if r: return r
            except Exception: pass
        base = "SELECT u.id,u.name FROM users u LEFT JOIN doctor_avail da ON da.doctor_id=u.id WHERE u.role='doctor' AND COALESCE(da.status,'available')!='leave'"
        for sql, args in ((base + " AND u.dept=? ORDER BY (COALESCE(da.status,'available')='available') DESC,u.id LIMIT 1", (dept,)), (base + " ORDER BY u.id LIMIT 1", ())):
            r = q(sql, args, one=True)
            if r: return r
        return q("SELECT id,name FROM users WHERE role='doctor' ORDER BY id LIMIT 1", one=True)

    @app.route("/emergency", methods=["GET", "POST"])
    @need("reception", "nurse", "doctor", "admin")
    def emergency():
        depts = sorted({d["dept"] for d in ns["get_docs"]() if d["code"] != "leave"})
        if request.method == "POST":
            f = request.form; back = redirect("/emergency")
            def fail(m): flash(m); return render_template("emergency.html", f=f, triage=TRIAGE, wards=WARDS, depts=depts), 400
            tri = f.get("triage"); complaint = clip(f.get("complaint"), 300); ward = f.get("ward"); bed = clip(f.get("bed"), 20); dept = f.get("dept") if f.get("dept") in depts else "Medicine"
            bp = re.sub(r"\D", "", f.get("brought_phone", ""))
            if tri not in dict(TRIAGE): return fail("Choose the triage level (Red / Orange / Yellow).")
            if len(complaint) < 3: return fail("Write the main problem (for example: road accident, chest pain, snake bite).")
            if ward not in WARDS: return fail("Choose the ward / unit.")
            if not bed: return fail("Enter the bed or casualty trolley number.")
            if bp and not MOBILE.match(bp): return fail("Relative's phone must be 10 digits (or leave it empty).")
            uhid = clip(f.get("uhid"), 30).upper()
            if uhid:
                p = q("SELECT * FROM patients WHERE uhid=? AND active=1", (uhid,), one=True)
                if not p: return fail("No patient with this UHID. Clear it to admit as an unknown patient.")
                temp = 0
            else:
                gender = f.get("gender") if f.get("gender") in ("Male", "Female", "Other") else "Male"
                try: age = int(f.get("age_years")); assert 0 <= age <= 120
                except (TypeError, ValueError, AssertionError): age = None
                nm = clip(f.get("name"), 80) or "Unknown " + gender.lower() + (f" (~{age} yrs)" if age is not None else "")
                pid = ns["create_profile"](dict(name=nm, gender=gender, age_years=age, age_asof=now().date().isoformat(), phone=bp or None, allergies=clip(f.get("allergies"), 150) or None,
                                                state="Madhya Pradesh", category="General", lang="hi", sms_ok=1 if bp else 0), None, "Self", who(), "emergency")
                p = ns["get_profile"](pid); temp = 0 if f.get("name") and f.get("known_name") else 1
            ex = q("SELECT code,status FROM appts WHERE pid=? AND kind='IPD' AND status IN ('booked','admitted') ORDER BY id DESC", (p["id"],), one=True)
            if ex and ex["status"] == "admitted": flash(f"This patient is already admitted ({ex['code']})."); return redirect(f"/ipd/{ex['code']}/chart")
            doc = ({"id": session["uid"], "name": session["name"]} if session.get("role") == "doctor" else pick_doctor(dept, ward))
            if not doc: return fail("No doctor account exists in the system. Ask the admin.")
            if ex:  # a pending request for the same patient becomes the emergency admission instead of a duplicate
                cd = ex["code"]; aid = q("SELECT id FROM appts WHERE code=?", (cd,), one=True)["id"]
                q("UPDATE appts SET adm_type='Emergency',prio=1,prio_why=?,ward=?,reason=? WHERE id=?", (f"Emergency ({tri})", ward, complaint, aid), commit=True)
            else:
                cd = code("IP-")
                aid = q("INSERT INTO appts(code,patient_id,doctor_id,dept,date,slot,reason,created,kind,ward,pid,prio,prio_why,src,adm_type,att_name,att_phone,att_rel) VALUES(?,?,?,?,?,'24x7',?,?,'IPD',?,?,1,?,'emergency','Emergency',?,?,?)",
                        (cd, p["owner_id"], doc["id"], dept, now().date().isoformat(), complaint, ts(), ward, p["id"], f"Emergency ({tri})", clip(f.get("brought_by"), 60) or None, bp or None, clip(f.get("brought_rel"), 30) or None), commit=True)
            ok, detail = ns["_ipd_bed_transition"](cd, "admitted", bed, who())
            warn = ""
            if not ok:  # an emergency is never refused because of a bed count
                q("UPDATE appts SET status='admitted',bed=? WHERE id=?", (bed, aid), commit=True); warn = " Bed count could not be confirmed. Please update the bed inventory."
            for cp in ("Registered", "Reception", "Ward"): event(aid, cp)
            old = info(aid)
            vals = (aid, tri, complaint, block(f.get("first_aid"), 500), temp, who(), ts())
            if old: q("UPDATE ipd_info SET emergency=1,triage=?,complaint=?,first_aid=?,id_pending=?,review_pending=1,entered_by=?,created=? WHERE appt_id=?", (tri, complaint, block(f.get("first_aid"), 500), temp, who(), ts(), aid), commit=True)
            else: q("INSERT INTO ipd_info(appt_id,emergency,triage,complaint,first_aid,id_pending,review_pending,entered_by,created) VALUES(?,1,?,?,?,?,1,?,?)", (vals[0], tri, complaint, vals[3], temp, who(), ts()), commit=True)
            add_note(aid, "casualty", findings=f"Triage {tri}. Brought with: {complaint}." + (f" Brought by: {clip(f.get('brought_by'), 60)}." if f.get("brought_by") else ""), orders=block(f.get("first_aid"), 500), diagnosis="")
            audit(who(), "EMERGENCY_ADMIT", f"{cd} {p['uhid']} triage={tri} bed={bed} id_pending={temp}")
            lvl = "critical" if tri in ("Red", "Orange") else "warning"
            ns["new_alert"](aid, "EMERGENCY_ADMIT", lvl, f"{p['name']} ({cd}): EMERGENCY ADMISSION, triage {tri}, {complaint}. Bed {bed}, {ward}. No doctor has seen the patient yet.",
                            [f"{who()} admitted the patient directly (triage {tri})", f"Duty doctor {doc['name']} must examine and file the first assessment", "Patient cannot be discharged until a doctor reviews"])
            if bp: ns["sms"](bp, f"SGMH Rewa: {p['name']} has been admitted in emergency. Admission code {cd}, {ward}, bed {bed}. Please come to the IPD desk.", None, cd)
            flash(f"Emergency admission {cd} done. Doctor alerted." + (" Temporary UHID " + p["uhid"] + ": identify the patient when family arrives." if temp else "") + warn)
            return redirect(f"/ipd/{cd}/chart")
        return render_template("emergency.html", f={}, triage=TRIAGE, wards=WARDS, depts=depts)

    # identify an unknown patient later / merge into the real record
    @app.route("/ipd/<cd>/identify", methods=["GET", "POST"])
    @need("reception", "nurse", "doctor", "admin")
    def ipd_identify(cd):
        a = ipd_row(cd)
        if not a or not a["pid"]: abort(404)
        p = ns["get_profile"](a["pid"]); i = info(a["id"])
        if request.method == "POST":
            f = request.form; real = clip(f.get("real_uhid"), 30).upper(); back = redirect(f"/ipd/{cd}/identify")
            if real:
                r = q("SELECT * FROM patients WHERE uhid=? AND active=1", (real,), one=True)
                if not r or r["id"] == p["id"]: flash("No other patient with this UHID."); return back
                if p["src"] != "emergency": flash("Only a temporary emergency record can be merged."); return back
                if not f.get("id_ok"): flash("Tick 'photo ID checked' to link the real record."); return back
                if q("SELECT 1 FROM appts WHERE pid=? AND kind='IPD' AND status IN ('booked','admitted')", (r["id"],), one=True): flash("That patient already has an admission."); return back
                q("UPDATE appts SET pid=?,patient_id=? WHERE pid=?", (r["id"], r["owner_id"], p["id"]), commit=True)
                q("UPDATE patients SET active=0 WHERE id=?", (p["id"],), commit=True)
                q("UPDATE ipd_info SET id_pending=0 WHERE appt_id=?", (a["id"],), commit=True)
                audit(who(), "EMERGENCY_MERGED", f"{cd}: temporary {p['uhid']} -> {r['uhid']}"); flash(f"Linked to {r['name']} ({r['uhid']}). Treatment record kept."); return redirect(f"/ipd/{cd}/identify")
            nm = clip(f.get("name"), 80)
            if len(nm) < 2: flash("Enter the patient's name."); return back
            ph = re.sub(r"\D", "", f.get("phone", ""))
            if ph and not MOBILE.match(ph): flash("Phone must be 10 digits."); return back
            try: age = int(f.get("age_years")) if f.get("age_years") else p["age_years"]
            except ValueError: age = p["age_years"]
            q("UPDATE patients SET name=?,gender=?,age_years=?,age_asof=?,phone=COALESCE(?,phone),village_ward=COALESCE(?,village_ward),allergies=COALESCE(?,allergies),blood_group=COALESCE(?,blood_group) WHERE id=?",
              (nm, f.get("gender") if f.get("gender") in ("Male", "Female", "Other") else p["gender"], age, now().date().isoformat(), ph or None, clip(f.get("village_ward"), 80) or None, clip(f.get("allergies"), 150) or None, clip(f.get("blood_group"), 6) or None, p["id"]), commit=True)
            if f.get("id_ok"): q("UPDATE ipd_info SET id_pending=0 WHERE appt_id=?", (a["id"],), commit=True)
            audit(who(), "EMERGENCY_IDENTIFIED", f"{cd} {p['uhid']} id_checked={'yes' if f.get('id_ok') else 'no'}"); flash("Patient details saved."); return back
        return render_template("ipd_identify.html", a=a, p=p, i=i)

    # ------------------------------------------------------------------ 3. the clinical chart
    def chart_ctx(a):
        i = info(a["id"]); n = q("SELECT * FROM notes WHERE appt_id=?", (a["id"],), one=True)
        return dict(a=a, i=i, notes=q("SELECT * FROM ipd_notes WHERE appt_id=? ORDER BY COALESCE(event_ts,ts) DESC,id DESC", (a["id"],)), kinds=DOC_KINDS, klabel=KIND_LABEL,
                    vit=q("SELECT * FROM vitals WHERE appt_id=? ORDER BY id DESC LIMIT 6", (a["id"],)), meds=n, given=q("SELECT * FROM dispensed WHERE appt_id=? ORDER BY id DESC", (a["id"],)),
                    orders=q("SELECT * FROM samples WHERE appt_id=? ORDER BY id DESC", (a["id"],)), tests=q("SELECT name,category FROM lab_tests ORDER BY category,name"),
                    alerts=q("SELECT * FROM alerts WHERE appt_id=? AND status IN ('open','escalated') ORDER BY id DESC", (a["id"],)), mar=ns["mar_view"](a), duty=ns["duty_live"](a["ward"]) if a["ward"] else None, summ=summary_of(a["id"]),
                    wait=minutes_since(i["created"]) if i and i["review_pending"] else 0, warn_min=EMERG_WAIT_WARN_MIN, now_local=now().strftime("%Y-%m-%dT%H:%M"), stay_from=admitted_ts(a))

    @app.route("/ipd/<cd>/chart")
    @need("doctor", "nurse", "admin")
    def ipd_chart(cd):
        a = ipd_row(cd)
        if not a: abort(404)
        ns["mar_check_overdue"](); audit(who(), "IPD_CHART_VIEW", cd); return render_template("ipd_chart.html", **chart_ctx(a))

    @app.route("/ipd/<cd>/note", methods=["POST"])
    @need("doctor", "nurse")
    def ipd_note(cd):
        a = ipd_row(cd); back = redirect(f"/ipd/{cd}/chart")
        if not a: abort(404)
        if a["status"] != "admitted": flash("Notes can be added only while the patient is admitted."); return back
        f = request.form; role = session["role"]; kind = f.get("kind", "")
        if role == "nurse": kind = "nursing"
        elif kind not in dict(DOC_KINDS): flash("Choose the type of note."); return back
        dx, fin, plan = clip(f.get("diagnosis"), 200), block(f.get("findings")), block(f.get("plan"), 1500)
        meds = "\n".join(x.strip()[:200] for x in (f.get("meds", "") if role == "doctor" else "").splitlines() if x.strip())
        adv = [t for t in f.getlist("tests") if role == "doctor" and t in {r["name"] for r in q("SELECT name FROM lab_tests")}]
        fam = clip(f.get("family_text"), 400)
        if not (dx or fin or plan or meds or adv): flash("Write something first: findings, plan, medicines or tests."); return back
        et = parse_dt(f.get("event_ts"))
        if f.get("event_ts") and not et: flash("The time of event is not valid."); return back
        if et and (et > now() + timedelta(minutes=5)): flash("Time of event cannot be in the future."); return back
        if et and et < datetime.strptime(a["created"], FMT) - timedelta(days=1): flash("Time of event is too far before this admission."); return back
        add_note(a["id"], kind, event_ts=et.strftime(FMT) if et else None, diagnosis=dx, findings=fin, orders=meds + (("\nTests: " + ", ".join(adv)) if adv else ""), plan=plan, family_text=fam)
        if meds:  # medicine orders go to the pharmacy through the same notes row OPD uses, with the same safety checks
            old = q("SELECT * FROM notes WHERE appt_id=?", (a["id"],), one=True); have = [x.strip() for x in (old["meds"] if old else "").splitlines() if x.strip()]
            low = {x.lower() for x in have}; new = [m for m in meds.splitlines() if m.lower() not in low]; allm = "\n".join(have + new); dxx = dx or (old["diagnosis"] if old else "") or ""
            s = ns["simplify"](dict(diagnosis=dxx, meds=allm, do_text="", avoid_text="", care="", followup=""))
            q("INSERT INTO notes(appt_id,diagnosis,meds,simplified,approved,dispensed,recalled) VALUES(?,?,?,?,1,0,0) ON CONFLICT(appt_id) DO UPDATE SET diagnosis=excluded.diagnosis,meds=excluded.meds,simplified=excluded.simplified,approved=1,dispensed=0,recalled=0",
              (a["id"], dxx, allm, s), commit=True)
            for m_ in new: ns["ipd_new_order"](a, m_)  # every new medicine line becomes an order the nurse must record doses against
            for w in ns["rx_risks"](a, meds, dxx):
                flash("Medicine safety warning: " + w); ns["new_alert"](a["id"], "MED_RX_RISK", "warning", f"{a['pname']}: prescription safety note: {w}", [w, "Doctor and pharmacist to confirm before dispensing"])
        for t in adv:
            if q("SELECT 1 FROM samples WHERE appt_id=? AND test=? AND status!='Report ready'", (a["id"], t), one=True): continue
            tr = q("SELECT category FROM lab_tests WHERE name=?", (t,), one=True)
            q("INSERT INTO samples(appt_id,barcode,test,status,category,ts) VALUES(?,?,?,?,?,?)", (a["id"], code("SM-", 6), t, "Ordered", tr["category"] if tr else "Other", ts()), commit=True)
        i = info(a["id"])
        if role == "doctor" and i and i["review_pending"]:  # first doctor entry on an emergency patient closes the "waiting for doctor" state
            q("UPDATE ipd_info SET review_pending=0,reviewed_by=?,reviewed_ts=? WHERE appt_id=?", (who(), ts(), a["id"]), commit=True)
            q("UPDATE alerts SET status='acknowledged',ack_by=?,ack_ts=? WHERE appt_id=? AND kind='EMERGENCY_ADMIT' AND status IN ('open','escalated')", (who(), ts(), a["id"]), commit=True)
            audit(who(), "EMERGENCY_REVIEWED", f"{cd} after {minutes_since(i['created'])} min")
        if role == "doctor" and f.get("take_over") and a["doctor_id"] != session["uid"]:
            q("UPDATE appts SET doctor_id=? WHERE id=?", (session["uid"], a["id"]), commit=True); audit(who(), "TREATING_DOCTOR_CHANGED", f"{cd} {a['doctor']} -> {session['name']}")
        audit(who(), "IPD_NOTE", f"{cd} {kind}" + (" +meds" if meds else "") + (f" +{len(adv)} tests" if adv else "")); flash("Saved to the patient's chart." + (" Medicines sent to the pharmacy." if meds else "")); return back

    # ------------------------------------------------------------------ 4. discharge summary
    @app.route("/ipd/<cd>/summary/edit", methods=["GET", "POST"])
    @need("doctor")
    def summary_edit(cd):
        a = ipd_row(cd)
        if not a: abort(404)
        if a["status"] not in ("admitted", "discharged"): flash("A discharge summary can be written for an admitted or discharged patient."); return redirect("/doctor")
        s = summary_of(a["id"])
        if request.method == "POST":
            f = request.form; dx = clip(f.get("final_dx"), 250)
            if not dx: flash("Final diagnosis is required."); return redirect(f"/ipd/{cd}/summary/edit")
            fu = f.get("followup_date", "").strip()
            try: datetime.strptime(fu, "%Y-%m-%d")
            except ValueError: fu = ""
            cond = f.get("cond") if f.get("cond") in CONDITIONS else CONDITIONS[0]; ap = 1 if f.get("approve") else 0
            if ap and not block(f.get("course")): flash("Write the hospital course before approving."); return redirect(f"/ipd/{cd}/summary/edit")
            q("INSERT INTO ipd_summary(appt_id,final_dx,course,procedures,meds_home,advice,followup_date,cond,approved,by,ts,approved_ts) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(appt_id) DO UPDATE SET "
              "final_dx=excluded.final_dx,course=excluded.course,procedures=excluded.procedures,meds_home=excluded.meds_home,advice=excluded.advice,followup_date=excluded.followup_date,cond=excluded.cond,approved=excluded.approved,by=excluded.by,ts=excluded.ts,approved_ts=excluded.approved_ts",
              (a["id"], dx, block(f.get("course")), block(f.get("procedures"), 1500), block(f.get("meds_home"), 1500), block(f.get("advice"), 1500), fu or None, cond, ap, who(), ts(), ts() if ap else None), commit=True)
            audit(who(), "DISCHARGE_SUMMARY_" + ("APPROVED" if ap else "SAVED"), cd)
            if ap: ns["patient_notice"](a["id"], f"The discharge summary for {a['pname']} ({cd}) is ready. Open the Visit page to read or print it." + (f" Follow-up: {fu}." if fu else ""), "advice")
            flash("Approved. The patient and family can now see it." if ap else "Saved as a draft. The patient cannot see it yet."); return redirect(f"/ipd/{cd}/summary")
        if not s:  # first time: prefill from the chart so the doctor edits instead of retyping
            ns_ = q("SELECT * FROM ipd_notes WHERE appt_id=? ORDER BY COALESCE(event_ts,ts),id", (a["id"],)); n = q("SELECT meds,diagnosis FROM notes WHERE appt_id=?", (a["id"],), one=True)
            dxs = [x["diagnosis"] for x in ns_ if x["diagnosis"]]
            s = dict(final_dx=(dxs[-1] if dxs else (n["diagnosis"] if n else "")) or "", procedures="\n".join(f"{(x['event_ts'] or x['ts'])[:16]}: {x['findings']}" for x in ns_ if x["kind"] == "procedure"),
                     course="\n".join(f"{(x['event_ts'] or x['ts'])[:10]} ({KIND_LABEL.get(x['kind'])}): {x['findings']}" for x in ns_ if x["kind"] in ("admission", "round") and x["findings"]), meds_home=(n["meds"] if n else "") or "", advice="", followup_date="", cond=CONDITIONS[0], approved=0)
        return render_template("ipd_summary_edit.html", a=a, s=s, conds=CONDITIONS)

    @app.route("/ipd/<cd>/summary")
    def summary_view(cd):
        a = ipd_row(cd)
        if not a: abort(404)
        staff = session.get("role") in ("doctor", "nurse", "reception", "admin")
        s = summary_of(a["id"])
        if not staff and not can_view(a, cd): flash("Please log in or use Track patient."); return redirect("/track")
        if not s or (not s["approved"] and not staff): flash("The discharge summary is not ready yet."); return redirect(f"/visit/{cd}")
        dis = q("SELECT ts FROM events WHERE appt_id=? AND cp='Discharge' ORDER BY id DESC LIMIT 1", (a["id"],), one=True)
        return render_template("ipd_summary.html", a=a, s=s, adm=admitted_ts(a), dis=dis["ts"] if dis else None, i=info(a["id"]), staff=staff,
                               labs=q("SELECT test,status,report FROM samples WHERE appt_id=? ORDER BY id", (a["id"],)), is_doc=session.get("role") == "doctor")

    # ------------------------------------------------------------------ 5. board
    @app.route("/ipd/board")
    @need("doctor", "nurse", "reception", "admin")
    def ipd_board():
        ns["mar_check_overdue"]()
        rows = q(f"SELECT a.id,a.code,a.status,a.ward,a.bed,a.adm_type,a.dept,a.date,a.referred_by,{ns['PCOLS']},d.name doctor FROM appts a {ns['PJOIN']} JOIN users d ON d.id=a.doctor_id WHERE a.kind='IPD' AND a.status IN ('booked','admitted') ORDER BY a.id DESC")
        out = []
        for r in rows:
            i = info(r["id"]); v = q("SELECT level,score,ts FROM vitals WHERE appt_id=? ORDER BY id DESC LIMIT 1", (r["id"],), one=True)
            out.append(dict(r=r, i=i, v=v, wait=minutes_since(i["created"]) if i and i["review_pending"] else 0, summ=summary_of(r["id"]),
                            al=q("SELECT COUNT(*) n FROM alerts WHERE appt_id=? AND status IN ('open','escalated')", (r["id"],), one=True)["n"]))
        out.sort(key=lambda x: (not (x["i"] and x["i"]["review_pending"]), -(x["wait"]), x["r"]["status"] != "admitted", -x["r"]["id"]))
        return render_template("ipd_board.html", adm=[x for x in out if x["r"]["status"] == "admitted"], wait=[x for x in out if x["r"]["status"] == "booked"], clinical=session.get("role") != "reception", warn_min=EMERG_WAIT_WARN_MIN)

    # ------------------------------------------------------------------ discharge guards (called from app.ipd_discharge)
    def discharge_block(a):
        i = info(a["id"])
        if i and i["review_pending"]: return "This emergency patient has not been seen by a doctor yet. A doctor must file the first assessment before discharge."
        if os.environ.get("IPD_SUMMARY_REQUIRED") == "1" and not (summary_of(a["id"]) or {"approved": 0})["approved"]: return "The doctor must approve the discharge summary before discharge."
    def discharge_note(a):
        return None if (summary_of(a["id"]) or {"approved": 0})["approved"] else "Note: no approved discharge summary yet. Ask the doctor to complete it."
    ns.update(ipd_discharge_block=discharge_block, ipd_discharge_note=discharge_note)
