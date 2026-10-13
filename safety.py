"""Patient-safety layer for Smart SGMH: vitals + early-warning alerts with escalation, verified lab report entry,
verified medicine dispensing (prescription/expiry/allergy/duplicate), patient summary, diet draft with doctor approval.
SAMPLE thresholds and diet sheets: doctors must set/approve them before any real use. Alerts support staff; they never order treatment."""
import os, json, re, sqlite3
from datetime import timedelta
from flask import request, redirect, session, flash, render_template, jsonify, abort
from werkzeug.security import generate_password_hash as gph

DIET = {  # SAMPLE guidance for drafts only; doctor reviews and approves
    ("diabet", "sugar"): (["Vegetables, dal and whole grains in measured portions", "Small regular meals"], ["Sugar, sweets and sugary drinks", "Fried and packaged snacks"]),
    ("hypertension", "blood pressure", " bp"): (["Fresh fruits and vegetables", "Home-cooked low-salt food"], ["Extra salt, pickles, papad", "Processed and packaged food"]),
    ("fever", "viral"): (["Plenty of fluids: water, ORS, soups", "Light food such as khichdi, dal, rice"], ["Oily and spicy food", "Outside and street food"]),
    ("anaemia", "anemia"): (["Green leafy vegetables, dals, fruits", "Iron-rich home food"], ["Tea or coffee straight after meals"]),
    ("diarrhoea", "diarrhea", "dehydration"): (["ORS and boiled or clean water", "Banana, rice, curd if the doctor allows"], ["Raw salads and outside food", "Very oily or spicy food"]),
}
DIET_NOTE = "Sample guidance. Doctor must review: kidney disease, pregnancy, allergies and fasting before surgery need personal advice."

def diet_draft(dx):
    t = " " + (dx or "").lower(); eat, avoid = [], []
    for keys, (e, a) in DIET.items():
        if any(k in t for k in keys): eat += e; avoid += a
    if not eat: return "Doctor to add diet advice for this patient."
    return "Eat:\n" + "\n".join("- " + x for x in eat) + "\n\nAvoid:\n" + "\n".join("- " + x for x in avoid) + "\n\n" + DIET_NOTE

def score(v):  # SAMPLE early-warning points (to be set by doctors); returns total, level, flags
    p = dict(spo2=3 if v["spo2"] <= 91 else 2 if v["spo2"] <= 93 else 1 if v["spo2"] <= 95 else 0,
             pulse=3 if v["pulse"] <= 40 or v["pulse"] >= 131 else 2 if v["pulse"] >= 111 else 1 if v["pulse"] <= 50 or v["pulse"] >= 91 else 0,
             bp=3 if v["bp_sys"] <= 90 or v["bp_sys"] >= 220 else 2 if v["bp_sys"] <= 100 else 1 if v["bp_sys"] <= 110 else 0,
             temp=3 if v["temp"] <= 35.0 else 2 if v["temp"] >= 39.1 else 1 if v["temp"] <= 36.0 or v["temp"] >= 38.1 else 0)
    tot, mx = sum(p.values()), max(p.values())
    lv = "critical" if mx == 3 or tot >= 7 else "warning" if tot >= 5 else "watch" if tot >= 3 else "normal"
    names = dict(spo2=f"SpO2 {v['spo2']}%", pulse=f"Pulse {v['pulse']}", bp=f"BP {v['bp_sys']}/{v['bp_dia']}", temp=f"Temp {v['temp']} C")
    return tot, lv, [f"{names[k]} (+{x})" for k, x in p.items() if x]

def register(ns):
    app, q, db, audit, who, need, now, ts, FMT, appt_row, can_view = (ns[k] for k in ("app", "q", "db", "audit", "who", "need", "now", "ts", "FMT", "appt_row", "can_view"))
    esc_min = lambda: int(os.environ.get("ESCALATE_MIN", 10))

    c = db()
    c.executescript("""CREATE TABLE IF NOT EXISTS vitals(id INTEGER PRIMARY KEY,appt_id,ts,staff,bp_sys,bp_dia,pulse,spo2,temp,score,level);
CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY,appt_id,ts,kind,level,message,status DEFAULT 'open',ack_by,ack_ts,esc_ts,trace);
CREATE TABLE IF NOT EXISTS dispensed(id INTEGER PRIMARY KEY,appt_id,batch,name,ts,staff);
CREATE TABLE IF NOT EXISTS diet(appt_id INTEGER PRIMARY KEY,draft,approved,approved_by,ts);""")
    try: c.execute("ALTER TABLE users ADD COLUMN allergies TEXT")
    except sqlite3.OperationalError: pass
    if not c.execute("SELECT 1 FROM users WHERE phone='9000000060'").fetchone():
        c.execute("INSERT INTO users(name,phone,role,pw) VALUES('Nurse Station','9000000060','nurse',?)", (gph("nurse123"),))
    c.commit(); c.close()

    def trace_add(aid, text):
        r = q("SELECT trace FROM alerts WHERE id=?", (aid,), one=True); t = json.loads(r["trace"] or "[]"); t.append([ts(), text])
        q("UPDATE alerts SET trace=? WHERE id=?", (json.dumps(t), aid), commit=True)

    def new_alert(appt_id, kind, level, msg, steps):
        a = q("SELECT id FROM alerts WHERE appt_id=? AND kind=? AND status IN ('open','escalated')", (appt_id, kind), one=True) if kind == "DETERIORATION" else None
        if a:
            q("UPDATE alerts SET level=?,message=? WHERE id=?", (level, msg, a["id"]), commit=True); trace_add(a["id"], "New reading still abnormal: " + msg); return a["id"]
        aid = q("INSERT INTO alerts(appt_id,ts,kind,level,message,trace) VALUES(?,?,?,?,?,?)", (appt_id, ts(), kind, level, msg, json.dumps([[ts(), s] for s in steps])), commit=True)
        audit(who(), "ALERT_" + kind, f"{appt_id}:{level}"); return aid

    def escalate_overdue():
        cut = (now() - timedelta(minutes=esc_min())).strftime(FMT)
        for r in q("SELECT id FROM alerts WHERE status='open' AND kind='DETERIORATION' AND ts<=?", (cut,)):
            q("UPDATE alerts SET status='escalated',esc_ts=? WHERE id=?", (ts(), r["id"]), commit=True)
            trace_add(r["id"], f"No acknowledgement in {esc_min()} min: escalated to supervisor"); audit("agent", "ALERT_ESCALATED", str(r["id"]))

    def record_vitals(a, v):  # save + score + raise alert if needed (shared by the nurse form and the /demo console). returns a message
        tot, lv, flags = score(v)
        q("INSERT INTO vitals(appt_id,ts,staff,bp_sys,bp_dia,pulse,spo2,temp,score,level) VALUES(?,?,?,?,?,?,?,?,?,?)", (a["id"], ts(), who(), v["bp_sys"], v["bp_dia"], v["pulse"], v["spo2"], v["temp"], tot, lv), commit=True)
        audit(who(), "VITALS", f"{a['code']}:{tot}:{lv}")
        if lv in ("warning", "critical"):
            act = "Urgent doctor review recommended; consider referral or higher care as per hospital protocol." if lv == "critical" else "Doctor review recommended."
            new_alert(a["id"], "DETERIORATION", lv, f"{a['pname']}: early-warning score {tot} ({lv}). {', '.join(flags)}. {act}",
                      [f"Observed vitals: {', '.join(flags) or 'normal'}", f"Scored {tot}: {lv}", f"Notified {a['doctor']} in the app", f"Waiting for acknowledgement ({esc_min()} min), then escalate"])
            return f"ALERT raised ({lv}). Doctor notified."
        return f"Saved. Score {tot} ({lv})."

    @app.route("/vitals")
    @need("nurse", "doctor")
    def vitals_home():
        rows = q("SELECT a.code,a.dept,a.status,p.name pname FROM appts a JOIN users p ON p.id=a.patient_id WHERE a.status IN ('arrived','seen','admitted') ORDER BY a.id DESC LIMIT 30")
        return render_template("vitals.html", rows=rows)

    @app.route("/vitals/<c>", methods=["GET", "POST"])
    @need("nurse", "doctor")
    def vitals_entry(c):
        a = appt_row(c)
        if not a: abort(404)
        if request.method == "POST":
            try:
                v = dict(bp_sys=int(request.form["bp_sys"]), bp_dia=int(request.form["bp_dia"]), pulse=int(request.form["pulse"]), spo2=int(request.form["spo2"]), temp=float(request.form["temp"]))
            except (ValueError, KeyError): flash("Enter all readings as numbers."); return redirect(f"/vitals/{c}")
            if not (50 <= v["bp_sys"] <= 300 and 30 <= v["bp_dia"] <= 200 and 20 <= v["pulse"] <= 250 and 50 <= v["spo2"] <= 100 and 30 <= v["temp"] <= 45):
                flash("A reading is outside the possible range. Please re-measure."); return redirect(f"/vitals/{c}")
            msg = record_vitals(a, v); flash(msg)
            return redirect(f"/patient/{c}")
        return render_template("vitals_form.html", a=a, hist=q("SELECT * FROM vitals WHERE appt_id=? ORDER BY id DESC LIMIT 6", (a["id"],)))

    @app.route("/alerts")
    @need("doctor", "nurse")
    def alerts_page():
        escalate_overdue()
        rows = q("SELECT al.*,a.code,p.name pname FROM alerts al JOIN appts a ON a.id=al.appt_id JOIN users p ON p.id=a.patient_id ORDER BY (al.status IN ('open','escalated')) DESC, al.id DESC LIMIT 60")
        return render_template("alerts.html", rows=[dict(r, steps=json.loads(r["trace"] or "[]")) for r in rows], esc=esc_min())

    @app.route("/api/alerts/count")
    def alerts_count():
        if session.get("role") not in ("doctor", "nurse", "admin"): return jsonify(error="forbidden"), 403
        escalate_overdue()
        r = q("SELECT COALESCE(SUM(status='open'),0) o, COALESCE(SUM(status='escalated'),0) e FROM alerts", one=True)
        return jsonify(open=r["o"], escalated=r["e"])

    @app.route("/alerts/<int:aid>/<act>", methods=["POST"])
    @need("doctor", "nurse")
    def alert_act(aid, act):
        if act not in ("ack", "close") or not q("SELECT 1 FROM alerts WHERE id=?", (aid,), one=True): abort(404)
        note = request.form.get("note", "").strip()
        if act == "ack": q("UPDATE alerts SET status='acknowledged',ack_by=?,ack_ts=? WHERE id=?", (who(), ts(), aid), commit=True); trace_add(aid, f"Acknowledged by {who()}" + (f": {note}" if note else ""))
        else: q("UPDATE alerts SET status='closed' WHERE id=?", (aid,), commit=True); trace_add(aid, f"Closed by {who()}" + (f": {note}" if note else ""))
        audit(who(), "ALERT_" + act.upper(), str(aid)); return redirect("/alerts")

    @app.route("/patient/<c>")
    def summary(c):
        a = appt_row(c)
        if not a: abort(404)
        staff = session.get("role") in ("doctor", "nurse", "reception", "lab", "pharmacy", "admin")
        if not (staff or can_view(a, c)): flash("Please log in or use Track patient."); return redirect("/track")
        escalate_overdue(); i = a["id"]
        note = q("SELECT * FROM notes WHERE appt_id=?", (i,), one=True)
        if not staff and not (note and note["approved"]): note = None  # family sees the note only after doctor approval
        d = q("SELECT * FROM diet WHERE appt_id=?", (i,), one=True)
        vit = list(reversed(q("SELECT * FROM vitals WHERE appt_id=? ORDER BY id DESC LIMIT 12", (i,))))
        draft = (d["draft"] if d and d["draft"] else diet_draft(note["diagnosis"] if note else ""))
        al = q("SELECT allergies FROM users WHERE id=?", (a["patient_id"],), one=True)["allergies"]
        return render_template("summary.html", a=a, staff=staff, note=note, vit=[dict(v) for v in vit], diet=d, draft=draft, allergies=al, role=session.get("role"),
            events=q("SELECT * FROM events WHERE appt_id=? ORDER BY id", (i,)), samples=q("SELECT * FROM samples WHERE appt_id=?", (i,)),
            given=q("SELECT * FROM dispensed WHERE appt_id=? ORDER BY id", (i,)), alerts=q("SELECT * FROM alerts WHERE appt_id=? ORDER BY id DESC", (i,)) if staff else [])

    @app.route("/patient/<c>/diet", methods=["POST"])
    @need("doctor")
    def diet_save(c):
        a = appt_row(c)
        if not a: abort(404)
        text = request.form.get("diet_text", "").strip()
        if request.form.get("act") == "approve":
            if not text: flash("Write or generate the diet advice first."); return redirect(f"/patient/{c}")
            q("INSERT INTO diet(appt_id,draft,approved,approved_by,ts) VALUES(?,?,?,?,?) ON CONFLICT(appt_id) DO UPDATE SET draft=excluded.draft,approved=excluded.approved,approved_by=excluded.approved_by,ts=excluded.ts", (a["id"], text, text, who(), ts()), commit=True)
            audit(who(), "DIET_APPROVED", c); flash("Diet advice approved and visible to the patient.")
        else:
            q("INSERT INTO diet(appt_id,draft,ts) VALUES(?,?,?) ON CONFLICT(appt_id) DO UPDATE SET draft=excluded.draft,approved=NULL,ts=excluded.ts", (a["id"], text, ts()), commit=True); flash("Draft saved (not visible to patient).")
        return redirect(f"/patient/{c}")

    @app.route("/patient/<c>/allergy", methods=["POST"])
    @need("doctor", "nurse", "reception")
    def allergy_save(c):
        a = appt_row(c)
        if not a: abort(404)
        q("UPDATE users SET allergies=? WHERE id=?", (request.form.get("allergies", "").strip()[:200] or None, a["patient_id"]), commit=True); audit(who(), "ALLERGY_SET", c); flash("Allergies saved."); return redirect(f"/patient/{c}")

    def do_report(a, s, res):  # core check, shared by the lab screen and the /demo console. returns (ok, message)
        if s["appt_id"] != a["id"]:
            owner = q("SELECT a.code FROM appts a WHERE a.id=?", (s["appt_id"],), one=True)["code"]
            new_alert(a["id"], "REPORT_MISMATCH", "critical", f"Report BLOCKED: sample {s['barcode']} belongs to {owner}, not {a['code']} ({a['pname']}).", [f"Lab tried to attach sample {s['barcode']} to {a['code']}", "Sample belongs to a different patient: report blocked"])
            return False, "BLOCKED: this sample belongs to a different patient. Alert raised."
        q("UPDATE samples SET status='Report ready',report=?,ts=? WHERE id=?", (res, ts(), s["id"]), commit=True); audit(who(), "REPORT_VERIFIED", f"{s['barcode']}->{a['code']}")
        return True, "Report matched to the right patient and saved."

    @app.route("/lab/report", methods=["POST"])
    @need("lab")
    def lab_report():
        a = appt_row(request.form.get("code", "").strip().upper()); s = q("SELECT * FROM samples WHERE barcode=?", (request.form.get("barcode", "").strip().upper(),), one=True)
        res = request.form.get("result", "").strip()
        if not a or not s or not res: flash("Enter patient code, sample barcode and result."); return redirect("/lab")
        flash(do_report(a, s, res)[1]); return redirect("/lab")

    def do_dispense(a, batch):  # core check, shared by the pharmacy screen and the /demo console. returns (ok, message)
        def block(kind, level, msg): new_alert(a["id"], kind, level, f"{a['pname']}: {msg}", [msg, "Dispensing blocked, pharmacist to review"]); return False, "BLOCKED: " + msg
        m = q("SELECT * FROM meds WHERE batch=?", (batch,), one=True)
        n = q("SELECT meds FROM notes WHERE appt_id=? AND approved=1", (a["id"],), one=True)
        if not n: return block("MED_NO_RX", "warning", "no doctor-approved prescription for this patient")
        if not m: return block("MED_UNKNOWN", "warning", "batch not found in the system")
        if m["expiry"] < now().date().isoformat(): return block("MED_EXPIRED", "critical", f"{m['name']} batch {m['batch']} is EXPIRED ({m['expiry']})")
        first = re.findall(r"[a-z]+", m["name"].lower())[0]; words = [w for w in re.findall(r"[a-z]+", (n["meds"] or "").lower()) if len(w) >= 4]
        if not any(first.startswith(w) or w.startswith(first) for w in words): return block("MED_MISMATCH", "critical", f"{m['name']} is NOT on this patient's prescription")
        al = (q("SELECT allergies FROM users WHERE id=?", (a["patient_id"],), one=True)["allergies"] or "").lower()
        if any(len(x) >= 4 and (x in m["name"].lower() or first.startswith(x)) for x in re.findall(r"[a-z]+", al)): return block("MED_ALLERGY", "critical", f"possible ALLERGY: patient allergic to '{al}', medicine is {m['name']}")
        if any(re.findall(r"[a-z]+", d["name"].lower())[0] == first for d in q("SELECT name FROM dispensed WHERE appt_id=?", (a["id"],))): return block("MED_DUPLICATE", "warning", f"{m['name']} was already dispensed to this patient")
        if (m["stock"] or 0) < 1: return block("MED_STOCK", "warning", f"{m['name']} is out of stock")
        q("UPDATE meds SET stock=stock-1 WHERE id=?", (m["id"],), commit=True); q("INSERT INTO dispensed(appt_id,batch,name,ts,staff) VALUES(?,?,?,?,?)", (a["id"], m["batch"], m["name"], ts(), who()), commit=True)
        audit(who(), "DISPENSE_VERIFIED", f"{a['code']}:{m['batch']}"); return True, f"OK: {m['name']} matches the prescription, in date, no allergy conflict. Recorded."

    @app.route("/pharmacy/verify", methods=["POST"])
    @need("pharmacy")
    def pharmacy_verify():
        a = appt_row(request.form.get("code", "").strip().upper())
        if not a: flash("Appointment code not found."); return redirect("/pharmacy")
        flash(do_dispense(a, request.form.get("batch", "").strip().upper())[1]); return redirect("/pharmacy")

    # block the old unchecked report path
    old = app.view_functions["lab_update"]
    def guarded(sid):
        if request.form.get("status") == "Report ready": flash("Use 'Verified report entry' (patient code + sample barcode) to release a report."); return redirect("/lab")
        return old(sid)
    app.view_functions["lab_update"] = guarded
    ns.update(trace_add=trace_add, new_alert=new_alert, escalate_overdue=escalate_overdue, record_vitals=record_vitals, do_report=do_report, do_dispense=do_dispense, esc_min=esc_min)
