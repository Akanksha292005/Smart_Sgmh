"""Live safety demo console for judges (/demo) + global alert feed (/api/alerts/latest).
One screen shows: nurse enters vitals / lab and pharmacy make a mistake -> the SAME safety checks as the real screens run -> alert appears for the doctor.
Uses two clearly-marked DEMO patients (AP-DEMO1, AP-DEMO2). Reset button restores them. All data is SAMPLE."""
import re
from datetime import datetime, timedelta
import os
from flask import request, session, render_template, jsonify, abort, redirect
from werkzeug.security import generate_password_hash as gph

A, B = "AP-DEMO1", "AP-DEMO2"
PRESETS = {  # SAMPLE readings chosen to trigger each early-warning level in safety.score()
    "normal":   dict(bp_sys=120, bp_dia=80, pulse=78,  spo2=98, temp=36.8),
    "warning":  dict(bp_sys=100, bp_dia=66, pulse=112, spo2=94, temp=38.4),
    "critical": dict(bp_sys=86,  bp_dia=54, pulse=134, spo2=88, temp=39.4),
}

def register(ns):
    app, q, db, now, ts, FMT, who, need, audit, appt_row = (ns[k] for k in ("app", "q", "db", "now", "ts", "FMT", "who", "need", "audit", "appt_row"))
    S = lambda k: ns[k]  # safety functions are added to ns after safety.register()

    def user_id(phone, name, role, dept=None):
        r = q("SELECT id FROM users WHERE phone=?", (phone,), one=True)
        return r["id"] if r else q("INSERT INTO users(name,phone,role,pw,dept) VALUES(?,?,?,?,?)", (name, phone, role, gph("pat123"), dept), commit=True)

    def ensure_demo(reset=False):
        c = db()
        pa = user_id("9000000091", "Ramesh Kumar (DEMO)", "patient"); pb = user_id("9000000092", "Sunita Devi (DEMO)", "patient")
        doc = c.execute("SELECT id FROM users WHERE role='doctor' AND dept='Medicine' ORDER BY id LIMIT 1").fetchone()["id"]
        today = now().date().isoformat()
        for code, pid, tok in ((A, pa, "D1"), (B, pb, "D2")):
            if not c.execute("SELECT 1 FROM appts WHERE code=?", (code,)).fetchone():
                aid = c.execute("INSERT INTO appts(code,patient_id,doctor_id,dept,date,slot,reason,status,token,created,kind) VALUES(?,?,?,?,?,?,?,?,?,?,'OPD')",
                                (code, pid, doc, "Medicine", today, "Walk-in", "Fever and chest infection (demo)", "arrived", tok, ts())).lastrowid
                c.execute("INSERT INTO events(appt_id,cp,ts,staff) VALUES(?,?,?,?)", (aid, "Registered", ts(), "demo")); c.execute("INSERT INTO events(appt_id,cp,ts,staff) VALUES(?,?,?,?)", (aid, "OPD", ts(), "demo"))
        ids = {r["code"]: r["id"] for r in c.execute("SELECT id,code FROM appts WHERE code IN (?,?)", (A, B))}
        c.execute("UPDATE appts SET status='arrived',date=? WHERE code IN (?,?)", (today, A, B))
        c.execute("INSERT OR REPLACE INTO notes(appt_id,diagnosis,meds,do_text,avoid_text,care,followup,simplified,approved) VALUES(?,?,?,?,?,?,?,?,1)",
                  (ids[A], "Viral fever with chest infection", "Paracetamol 500 mg tablet, Amoxicillin 500 mg capsule", "Rest, fluids", "Cold drinks", "", "", "", ))
        c.execute("UPDATE users SET allergies='amoxicillin' WHERE id=?", (pa,))
        for bc, aid, test in (("DEMO-S1", ids[A], "Complete Blood Count (CBC)"), ("DEMO-S2", ids[B], "Blood Sugar (Fasting)")):
            if not c.execute("SELECT 1 FROM samples WHERE barcode=?", (bc,)).fetchone():
                c.execute("INSERT INTO samples(appt_id,barcode,test,status,ts,category) VALUES(?,?,?,?,?,?)", (aid, bc, test, "Processing", ts(), "Blood Tests"))
        t0 = now().date()
        for b, n, d, st in (("DEMO-PCM", "Paracetamol 500 mg tablet", 300, 500), ("DEMO-EXP", "Paracetamol 500 mg tablet", -5, 500), ("DEMO-PAN", "Pantoprazole 40 mg tablet", 300, 500), ("DEMO-AMX", "Amoxicillin 500 mg capsule", 300, 500)):
            c.execute("INSERT OR IGNORE INTO meds(batch,name,expiry,stock,category) VALUES(?,?,?,?,?)", (b, n, str(t0 + timedelta(days=d)), st, "Demo"))
        if reset:
            for code in (A, B):
                i = ids[code]; c.execute("DELETE FROM alerts WHERE appt_id=?", (i,)); c.execute("DELETE FROM vitals WHERE appt_id=?", (i,)); c.execute("DELETE FROM dispensed WHERE appt_id=?", (i,))
                c.execute("UPDATE samples SET status='Processing',report=NULL WHERE appt_id=?", (i,))
            c.execute("UPDATE meds SET stock=500 WHERE batch LIKE 'DEMO-%'")
        c.commit(); c.close()
        return ids

    @app.route("/demo/start")  # one click for judges: signs in as the demo nurse, then opens the console. Set DEMO_MODE=0 to switch off.
    def demo_start():
        u = q("SELECT * FROM users WHERE phone='9000000060'", one=True)
        if os.environ.get("DEMO_MODE", "1") != "1" or not u: abort(404)
        lang = session.get("lang"); session.clear(); session.update(uid=u["id"], role=u["role"], name=u["name"], dept=u["dept"], lang=lang or "en")
        return redirect("/demo")

    @app.route("/demo")
    @need("nurse", "doctor")
    def demo_page():
        ensure_demo(); return render_template("demo.html", A=A, B=B, presets=PRESETS)

    @app.route("/demo/state")
    @need("nurse", "doctor")
    def demo_state():
        ids = ensure_demo(); S("escalate_overdue")(); a = appt_row(A); i = ids[A]
        al = q("SELECT * FROM alerts WHERE appt_id=? ORDER BY id DESC LIMIT 30", (i,))
        import json
        return jsonify(
            patient=dict(name=a["pname"], code=A, doctor=a["doctor"], dept=a["dept"], allergies=a["pallergy"]),
            vitals=[dict(ts=v["ts"][11:19], bp=f"{v['bp_sys']}/{v['bp_dia']}", pulse=v["pulse"], spo2=v["spo2"], temp=v["temp"], score=v["score"], level=v["level"]) for v in q("SELECT * FROM vitals WHERE appt_id=? ORDER BY id DESC LIMIT 6", (i,))],
            alerts=[dict(id=r["id"], kind=r["kind"].replace("_", " "), level=r["level"], status=r["status"], message=r["message"], ts=r["ts"][11:19], steps=[[t[11:19], s] for t, s in json.loads(r["trace"] or "[]")]) for r in al],
            dispensed=[d["name"] for d in q("SELECT name FROM dispensed WHERE appt_id=?", (i,))], esc=S("esc_min")())

    @app.route("/demo/act", methods=["POST"])
    @need("nurse", "doctor")
    def demo_act():
        f = request.form; act = f.get("action", ""); ids = ensure_demo(); a = appt_row(A); b = appt_row(B)
        if act.startswith("vitals_") and act[7:] in PRESETS:
            msg = S("record_vitals")(a, PRESETS[act[7:]]); return jsonify(ok=act != "vitals_critical" and act != "vitals_warning", msg=msg)
        if act == "vitals_custom":
            try: v = dict(bp_sys=int(f["bp_sys"]), bp_dia=int(f["bp_dia"]), pulse=int(f["pulse"]), spo2=int(f["spo2"]), temp=float(f["temp"]))
            except (ValueError, KeyError): return jsonify(ok=False, msg="Enter all readings as numbers.")
            if not (50 <= v["bp_sys"] <= 300 and 30 <= v["bp_dia"] <= 200 and 20 <= v["pulse"] <= 250 and 50 <= v["spo2"] <= 100 and 30 <= v["temp"] <= 45): return jsonify(ok=False, msg="A reading is outside the possible range. Please re-measure.")
            msg = S("record_vitals")(a, v); return jsonify(ok=msg.startswith("Saved"), msg=msg)
        if act in ("report_right", "report_wrong"):  # lab technician attaches a result to AP-DEMO1: own sample vs another patient's sample
            s = q("SELECT * FROM samples WHERE barcode=?", ("DEMO-S1" if act == "report_right" else "DEMO-S2",), one=True)
            ok, msg = S("do_report")(a, s, "Hb 13.2 g/dL (demo result)"); return jsonify(ok=ok, msg=msg)
        if act in ("med_ok", "med_expired", "med_wrong", "med_allergy"):
            batch = dict(med_ok="DEMO-PCM", med_expired="DEMO-EXP", med_wrong="DEMO-PAN", med_allergy="DEMO-AMX")[act]
            ok, msg = S("do_dispense")(a, batch); return jsonify(ok=ok, msg=msg)
        if act == "escalate_now":  # time-travel: pretend nobody acknowledged for ESCALATE_MIN minutes
            if not q("SELECT 1 FROM alerts WHERE appt_id=? AND status='open' AND kind='DETERIORATION'", (ids[A],), one=True):
                return jsonify(ok=False, msg="No open patient-deterioration alert to escalate. Press 'Critical patient' first and do NOT acknowledge it.")
            old = (now() - timedelta(minutes=S("esc_min")() + 1)).strftime(FMT)
            q("UPDATE alerts SET ts=? WHERE appt_id=? AND status='open' AND kind='DETERIORATION'", (old, ids[A]), commit=True); S("escalate_overdue")()
            return jsonify(ok=True, msg="Simulated: no one acknowledged in time, so the alert was escalated to the supervisor.")
        if act == "reset": ensure_demo(reset=True); return jsonify(ok=True, msg="Demo reset. Patient is stable again, alerts cleared.")
        abort(400)

    @app.route("/demo/ack", methods=["POST"])
    @need("nurse", "doctor")
    def demo_ack():
        aid = request.form.get("id", type=int)
        if not aid or not q("SELECT 1 FROM alerts WHERE id=?", (aid,), one=True): abort(404)
        q("UPDATE alerts SET status='acknowledged',ack_by=?,ack_ts=? WHERE id=?", (who(), ts(), aid), commit=True); S("trace_add")(aid, f"Acknowledged by {who()}"); audit(who(), "ALERT_ACK", str(aid))
        return jsonify(ok=True)

    @app.route("/api/alerts/latest")  # feed for the pop-up banner on every staff page
    def alerts_latest():
        if session.get("role") not in ("doctor", "nurse", "admin"): return jsonify(error="forbidden"), 403
        S("escalate_overdue")()
        rows = q("SELECT al.id,al.level,al.kind,al.message,al.status,a.code FROM alerts al JOIN appts a ON a.id=al.appt_id WHERE al.status IN ('open','escalated') ORDER BY al.id DESC LIMIT 5")
        return jsonify(alerts=[dict(r, kind=r["kind"].replace("_", " ")) for r in rows])
