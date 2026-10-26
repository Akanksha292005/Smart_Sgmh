"""Medicine administration record (MAR) and the family-facing treatment timeline for IPD. (The duty roster itself is wardduty.py.)

* MAR: every medicine a doctor orders on the IPD chart becomes an order. The nurse records each dose (given / held / refused) with her name and time. The frequency
  is read from the order text (OD, BD, TDS, QID, 'every 6 hours', SOS). A dose not recorded within MAR_GRACE_MIN of its due time raises an alert for doctor + nurse and
  is shown to the family as "delayed". Giving a dose much earlier than due asks for confirmation (duplicate-dose guard). Held / refused doses alert the doctor.
* FAMILY TIMELINE: shown on the Visit page of the PATIENT'S OWN account (or Track with code + last 4 digits). No separate family login. It shows everything about the
  stay from A to Z: patient and admission details, who is on duty now (shift-aware roster), doctor and nurse notes with names and times (plus the plain-language
  "Message for family" when the doctor/nurse wrote one), every medicine with each dose given (time, nurse) or delayed, tests, vitals in words, safety alerts and
  what staff did about them, and the discharge summary. The block refreshes by itself every 20 seconds.
The schedule is a simple rolling one (next dose = last recorded dose + interval). Hospital pharmacists/doctors must confirm the rules before real use. Tests: python tests_ipd_mar.py"""
import os, re
from datetime import datetime, timedelta
from flask import request, session, render_template, redirect, flash, abort

GRACE_MIN = int(os.environ.get("MAR_GRACE_MIN", 30))        # minutes after the due time before a dose counts as overdue
FIRST_GRACE_MIN = int(os.environ.get("MAR_FIRST_GRACE_MIN", 60))  # first dose: pharmacy has to hand the medicine over first
EARLY_FRACTION = 0.5                                          # giving before half of the interval has passed needs a confirmation
LEVEL_WORDS = {"normal": "Normal", "watch": "Slightly off, being watched", "warning": "Abnormal: doctor informed", "critical": "Serious: doctor informed urgently"}


def interval_of(text):
    """(hours or None, prn) from the order text. None = no automatic schedule (one-off, STAT or not understood)."""
    t = " " + (text or "").lower() + " "
    if re.search(r"\b(sos|prn|if needed|as needed|when needed|if required)\b", t): return None, True
    m = re.search(r"(?:every|q)\s*(\d{1,2})\s*(?:h|hr|hrs|hours?|hourly)\b|\b(\d{1,2})\s*(?:h|hr|hrs)ly\b|\b(\d{1,2})\s*hourly\b", t)
    if m:
        n = int(next(g for g in m.groups() if g)); return (n, False) if 1 <= n <= 48 else (None, False)
    for rx, h in ((r"\b(qid|qds|four times|4 times|4x)\b", 6), (r"\b(tds|tid|thrice|three times|3 times|3x)\b", 8), (r"\b(bd|bid|twice|two times|2 times|2x)\b", 12),
                  (r"\b(od|qd|once|daily|1 time|1x|at night|hs|nocte|morning)\b", 24)):
        if re.search(rx, t): return h, False
    return None, False


def register(ns):
    app, q, db, ts, now, who, need, audit, FMT, appt_row, can_view = (ns[k] for k in ("app", "q", "db", "ts", "now", "who", "need", "audit", "FMT", "appt_row", "can_view"))
    clip = lambda s, n=200: " ".join((s or "").split())[:n]

    c = db(); c.executescript("""
    CREATE TABLE IF NOT EXISTS ipd_orders(id INTEGER PRIMARY KEY, appt_id INT, drug TEXT, ordered_ts TEXT, ordered_by TEXT, interval_h REAL, prn INT DEFAULT 0, active INT DEFAULT 1, stopped_by TEXT, stopped_ts TEXT);
    CREATE TABLE IF NOT EXISTS ipd_mar(id INTEGER PRIMARY KEY, order_id INT, appt_id INT, ts TEXT, by TEXT, status TEXT, note TEXT);
    CREATE INDEX IF NOT EXISTS ix_mar ON ipd_mar(order_id, id);""")
    c.commit(); c.close()
    pt = lambda s: datetime.strptime(s, FMT)
    person = lambda s: (s or "").split(":", 1)[-1]  # "nurse:Sister Rita" -> "Sister Rita"

    # ------------------------------------------------------------------ medicine orders + MAR
    def new_order(a, line, by=None):
        drug = clip(line, 200)
        if not drug or q("SELECT 1 FROM ipd_orders WHERE appt_id=? AND active=1 AND lower(drug)=?", (a["id"], drug.lower()), one=True): return None
        h, prn = interval_of(drug)
        return q("INSERT INTO ipd_orders(appt_id,drug,ordered_ts,ordered_by,interval_h,prn,active) VALUES(?,?,?,?,?,?,1)", (a["id"], drug, ts(), by or who(), h, 1 if prn else 0), commit=True)

    def order_state(o, last):
        if not o["active"]: return "stopped", None
        if o["prn"]: return "prn", None
        if not o["interval_h"]: return "nosched", None
        due = (pt(last["ts"]) + timedelta(hours=o["interval_h"])) if last else pt(o["ordered_ts"])
        late = timedelta(minutes=GRACE_MIN if last else FIRST_GRACE_MIN)
        n = now()
        return ("overdue" if n > due + late else "due" if n >= due else "ok"), due

    def mar_view(a):
        out = []
        for o in q("SELECT * FROM ipd_orders WHERE appt_id=? ORDER BY active DESC,id", (a["id"],)):
            recs = q("SELECT * FROM ipd_mar WHERE order_id=? ORDER BY id DESC LIMIT 6", (o["id"],)); last = recs[0] if recs else None
            st, due = order_state(o, last); lg = next((r for r in recs if r["status"] == "given"), None)
            freq = "as needed" if o["prn"] else (f"every {int(o['interval_h'])} h" if o["interval_h"] else "no fixed schedule")
            out.append(dict(o=o, st=st, due=due, last=last, last_given=lg, recs=recs, freq=freq, late_min=int((now() - due).total_seconds() // 60) if st == "overdue" else 0))
        return out

    def mar_overdue_n(aid):
        n = 0
        for o in q("SELECT * FROM ipd_orders WHERE appt_id=? AND active=1", (aid,)):
            last = q("SELECT ts FROM ipd_mar WHERE order_id=? ORDER BY id DESC LIMIT 1", (o["id"],), one=True)
            if order_state(o, last)[0] == "overdue": n += 1
        return n

    def check_overdue():
        """Raise one alert per overdue scheduled dose (idempotent). Called whenever staff screens load and by the alert-count poll."""
        for a in q("SELECT a.id,a.code,a.ward,COALESCE(pt.name,p.name) pname FROM appts a LEFT JOIN users p ON p.id=a.patient_id LEFT JOIN patients pt ON pt.id=a.pid WHERE a.kind='IPD' AND a.status='admitted'"):
            for o in q("SELECT * FROM ipd_orders WHERE appt_id=? AND active=1 AND prn=0 AND interval_h IS NOT NULL", (a["id"],)):
                last = q("SELECT ts FROM ipd_mar WHERE order_id=? ORDER BY id DESC LIMIT 1", (o["id"],), one=True)
                st, due = order_state(o, last)
                if st != "overdue" or q("SELECT 1 FROM alerts WHERE appt_id=? AND kind='MED_DOSE_OVERDUE' AND message LIKE ? AND status IN ('open','escalated','acknowledged')", (a["id"], f"%(order #{o['id']}, due {due:%d %H:%M})%"), one=True): continue
                dn = ns["duty_live"](a["ward"]); nm = ", ".join(dn["nurses"]) or "nobody rostered for this shift"
                ns["new_alert"](a["id"], "MED_DOSE_OVERDUE", "warning", f"{a['pname']} ({a['code']}): dose of '{o['drug']}' was due at {due:%H:%M} and is not recorded as given (order #{o['id']}, due {due:%d %H:%M}). Nurse on duty: {nm}.",
                                [f"Due {due:%H:%M}, not recorded after {GRACE_MIN if last else FIRST_GRACE_MIN} min", "Nurse to give the dose or record why it was held", "Doctor informed in the app"])

    @app.before_request
    def _poll_hook():
        if request.path == "/api/alerts/count" and session.get("role") in ("doctor", "nurse"):
            try: check_overdue()
            except Exception: pass

    @app.route("/ipd/<cd>/mar/<int:oid>", methods=["POST"])
    @need("nurse", "doctor")
    def mar_record(cd, oid):
        a = appt_row(cd); back = redirect(f"/ipd/{cd}/chart")
        o = q("SELECT * FROM ipd_orders WHERE id=?", (oid,), one=True)
        if not a or a["kind"] != "IPD" or not o or o["appt_id"] != a["id"]: abort(404)
        f = request.form; st = f.get("status"); note = clip(f.get("note"), 200)
        if a["status"] != "admitted": flash("Doses can be recorded only while the patient is admitted."); return back
        if not o["active"]: flash("This order was stopped by the doctor."); return back
        if st not in ("given", "held", "refused"): flash("Choose given, held or refused."); return back
        if st != "given" and len(note) < 3: flash("Write the reason (why the dose was held or refused)."); return back
        last = q("SELECT * FROM ipd_mar WHERE order_id=? ORDER BY id DESC LIMIT 1", (oid,), one=True)
        if st == "given" and last and last["status"] == "given" and not f.get("confirm_early"):
            gap = (now() - pt(last["ts"])).total_seconds() / 3600
            need_gap = 0.5 if o["prn"] else (o["interval_h"] or 0) * EARLY_FRACTION
            if gap < need_gap:
                flash(f"Last dose was given {int(gap * 60)} min ago by {person(last['by'])}. Giving again now may be a duplicate dose. Tick 'give anyway' only if the doctor has said so."); return back
        q("INSERT INTO ipd_mar(order_id,appt_id,ts,by,status,note) VALUES(?,?,?,?,?,?)", (oid, a["id"], ts(), who(), st, note or None), commit=True)
        q("UPDATE alerts SET status='closed' WHERE appt_id=? AND kind='MED_DOSE_OVERDUE' AND message LIKE ? AND status IN ('open','escalated','acknowledged')", (a["id"], f"%(order #{oid},%"), commit=True)
        audit(who(), "MAR_" + st.upper(), f"{cd} order {oid}: {o['drug'][:60]}" + (f" ({note})" if note else ""))
        if st != "given":
            ns["new_alert"](a["id"], "MED_NOT_GIVEN", "warning", f"{a['pname']} ({cd}): dose of '{o['drug']}' was {st.upper()} by {who()}. Reason: {note}. Doctor to review.", [f"{who()} recorded: {st}", f"Reason: {note}", "Doctor to decide whether to change or repeat the order"])
        flash("Recorded." if st == "given" else "Recorded. The doctor has been alerted."); return back

    @app.route("/ipd/<cd>/order/<int:oid>/stop", methods=["POST"])
    @need("doctor")
    def order_stop(cd, oid):
        a = appt_row(cd); o = q("SELECT * FROM ipd_orders WHERE id=?", (oid,), one=True)
        if not a or not o or o["appt_id"] != a["id"]: abort(404)
        q("UPDATE ipd_orders SET active=0,stopped_by=?,stopped_ts=? WHERE id=?", (who(), ts(), oid), commit=True)
        q("UPDATE alerts SET status='closed' WHERE appt_id=? AND kind='MED_DOSE_OVERDUE' AND message LIKE ? AND status IN ('open','escalated','acknowledged')", (a["id"], f"%(order #{oid},%"), commit=True)
        audit(who(), "ORDER_STOPPED", f"{cd} order {oid}: {o['drug'][:60]}"); flash("Order stopped. Nurses will not be asked to give it."); return redirect(f"/ipd/{cd}/chart")

    # ------------------------------------------------------------------ what the patient / family sees (A to Z)
    def family_view(a):
        info = q("SELECT * FROM ipd_info WHERE appt_id=?", (a["id"],), one=True); out = dict(info=info, person=person, updated=ts())
        out["p"] = q("SELECT * FROM patients WHERE id=?", (a["pid"],), one=True) if a["pid"] else None
        out["events"] = q("SELECT cp,ts FROM events WHERE appt_id=? ORDER BY id", (a["id"],))
        out["opd"] = q("SELECT code,date FROM appts WHERE code=?", (info["ref_from"],), one=True) if info and info["ref_from"] else None
        if info and info["emergency"]:
            out["seen_min"] = int((pt(info["reviewed_ts"]) - pt(info["created"])).total_seconds() // 60) if info["reviewed_ts"] else None
            out["wait_min"] = int((now() - pt(info["created"])).total_seconds() // 60) if info["review_pending"] else None
        out["notes"] = q("SELECT * FROM ipd_notes WHERE appt_id=? ORDER BY COALESCE(event_ts,ts) DESC,id DESC LIMIT 60", (a["id"],))
        out["dx"] = next((n["diagnosis"] for n in out["notes"] if n["diagnosis"]), "")
        out["meds"] = mar_view(a)
        out["tests"] = q("SELECT id,test,status,report,report_file,ts FROM samples WHERE appt_id=? ORDER BY id DESC", (a["id"],))
        out["vitals"] = [dict(ts=v["ts"], bp=f"{v['bp_sys']}/{v['bp_dia']}", pulse=v["pulse"], spo2=v["spo2"], temp=v["temp"], words=LEVEL_WORDS.get(v["level"], v["level"]), level=v["level"], by=person(v["staff"])) for v in q("SELECT * FROM vitals WHERE appt_id=? ORDER BY id DESC LIMIT 8", (a["id"],))]
        out["alerts"] = q("SELECT * FROM alerts WHERE appt_id=? ORDER BY id DESC LIMIT 15", (a["id"],))
        out["duty"] = ns["duty_live"](a["ward"]) if a["ward"] else None
        out["summary_ok"] = bool(q("SELECT 1 FROM ipd_summary WHERE appt_id=? AND approved=1", (a["id"],), one=True))
        return out

    @app.route("/ipd/<cd>/family")
    def ipd_family_fragment(cd):  # the live block of the Visit page, refreshed every 20 s; same access rule as /visit
        a = appt_row(cd)
        if not a or a["kind"] != "IPD": abort(404)
        if not can_view(a, cd): abort(403)
        check_overdue(); return render_template("_ipd_family.html", a=a)

    @app.context_processor
    def _c():
        return dict(ipd_family=family_view, mar_overdue_n=mar_overdue_n, person=person)

    ns.update(ipd_new_order=new_order, mar_view=mar_view, mar_overdue_n=mar_overdue_n, mar_check_overdue=check_overdue, interval_of=interval_of)
