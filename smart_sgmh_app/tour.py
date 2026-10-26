"""One-system workflow for judges (v29).

/workflow   public page: the whole patient journey on one screen (OPD, tests, medicines, IPD, care team, death record, signed certificate, verify QR),
            who does each step and which safety check runs there.
/tour       5-minute guided demo. "Load story" creates ONE admitted patient (AP-TOUR1, 3 days in Medicine ward) so the IPD half of the journey can be
            shown without waiting. Every step has a button that signs in as the right role and opens the right screen; steps tick themselves when done.
/tour/go/<step>   switch role + open the screen.   A small "Judge tour" bar on every page shows the current role and lets you switch.
Only active while DEMO_MODE=1 (default). Set DEMO_MODE=0 in production: /tour and the role switcher then disappear. All data created here is DEMO."""
import os
from datetime import timedelta
from flask import render_template, request, session, redirect, flash, abort

CODE = "AP-TOUR1"
ROLES = {  # role -> (demo phone, label)
    "patient": ("9000000001", "Patient / family"), "reception": ("9000000010", "Reception"), "nurse": ("9000000060", "Nurse"),
    "doctor": ("9000000041", "Doctor (Dr. Manoj Indurkar)"), "lab": ("9000000020", "Lab / Blood bank"), "pharmacy": ("9000000030", "Pharmacy"), "admin": ("9000000000", "Admin")}
HOME = {"patient": "/home", "reception": "/reception", "doctor": "/doctor", "lab": "/lab", "pharmacy": "/pharmacy", "nurse": "/vitals", "admin": "/admin"}
SAMPLE_TEAM = dict(duty_doctor="Dr. Pradeep Nigam", nurse="Sister Meena Tiwari", attendant="Ramesh (ward boy)", shift="Night (8 PM - 8 AM)", fam_name="Suresh Prasad", fam_rel="Son", fam_phone="9876543210")

# (key, role, title, what to do, what the judge sees, screen)   screen may contain {code}
STEPS = [
 ("start", None, "Patient starts with a mobile number", "Open the start page. No app, no account form: name + mobile + OTP.", "Hindi first, big buttons, voice input, 'all services free' notice.", "/start"),
 ("doctors", None, "Find the right doctor and room", "Open Doctors. Pick any department.", "Doctors sit only on their roster days, room and floor are shown, and the map gives directions.", "/doctors"),
 ("book", "patient", "Book a slot", "Sign in as the patient, choose doctor, day and time.", "Only free slots on that doctor's working days. Priority for senior citizens, pregnant women, infants.", "/book"),
 ("reception", "reception", "Reception: arrival and IPD desk", "Open Reception. See the OPD queue and the IPD list with the admitted demo patient.", "Verify panel, token, priority; the IPD row has a Care team button.", "/reception"),
 ("care", "nurse", "Care team: who is on duty and who is the family attendant", "Open the care team of the admitted patient. It is filled from the ward duty roster; press 'Fill sample' or edit: duty doctor, nurse, shift, family attendant.", "Everyone involved in the stay on one card. The family sees the same card on their Visit page.", "/ward/{code}"),
 ("safety", "nurse", "Safety net: critical vitals and wrong medicine", "Open the Live Safety Demo and press any preset (critical vitals, expired medicine, allergy, wrong lab sample).", "A red alert appears for the doctor; acknowledge or escalate. Every action goes into a tamper-proof audit log.", "/demo"),
 ("blood", "lab", "Blood bank stock", "Open the Blood Bank page. Lab staff can change units; everyone else sees Available / Low / Not available.", "Live strip on the home page; 'may be outdated' warning after 12 hours.", "/blood-bank"),
 ("death", "doctor", "Doctor records the death and signs", "Open Record death. Enter time, cause, registration number, tick the box, type your password.", "Stay length (days + hours) is computed from the admission event, the care team is copied into the certificate, record is locked.", "/death/{code}"),
 ("verify", None, "Anyone verifies the certificate by QR", "Open the certificate, then scan the QR or open the verify link.", "'Genuine' with a masked name. If the database is edited it shows NOT genuine.", "/death/{code}/certificate"),
 ("admin", "admin", "Admin: audit chain and reports", "Open the Admin dashboard.", "Hash-chained audit log (who viewed or changed what), queue time, bottlenecks.", "/admin"),
]
PHASES = [  # workflow page: (title, [(node title, who, line, link)])
 ("1. Patient journey: OPD", [("Start", "Patient", "Name + mobile + OTP, UHID on first registration", "/start"), ("Book", "Patient", "Doctor, day, time on roster days; slip + QR", "/book"),
                  ("Arrive", "Reception", "ID and allergy check, token, priority queue", "/reception"), ("Vitals", "Nurse", "Critical value raises an alert", "/vitals"),
                  ("Consult", "Doctor", "Diagnosis, medicines, tests; allergy warning", "/doctor"), ("Tests", "Lab / X-ray", "Sample barcode must match the patient", "/lab"),
                  ("Medicines", "Pharmacy", "Batch, expiry and allergy check", "/pharmacy")]),
 ("2. Doctor admits: IPD (patients do not request it)", [("Admit", "Doctor", "Admit to IPD: ward + urgency. OPD details go with the patient", "/doctor"), ("Bed", "Reception", "Admission code, photo ID, bed", "/reception"),
                  ("Ward + care team", "System", "Ward, bed, duty doctor, duty nurse filled from the ward duty roster", "/ward/{code}"), ("Ward view", "Doctor / duty nurse", "All patients of the ward, vitals, alerts", "/wardview"),
                  ("Alert", "System", "Serious condition: alert to the doctor and that ward's duty staff", "/alerts"), ("Chart", "Doctor / nurse", "Rounds, orders, discharge summary", "/ipd/board"),
                  ("Outcome", "Doctor", "Discharge, or record death", "/death/{code}"), ("Certificate", "System", "Signed summary with days stayed and care team", "/death/{code}/certificate"),
                  ("Verify", "Anyone", "QR opens the check page", "/death/{code}/certificate")]),
 ("3. OPD closed: emergency", [("Emergency gate", "Patient / family", "Go to the gate or call 112 / 108", "/ipd"), ("Triage + admit", "Emergency staff", "Red / Orange / Yellow, bed, no booking needed", "/emergency"),
                  ("Duty doctor alert", "System", "Critical alert to the ward's duty doctor and nurses", "/alerts"), ("Ward", "Duty staff", "Same ward view, chart and care team as any admission", "/wardview"),
                  ("Identify later", "Reception", "Family arrives: real name or UHID is linked, notes are kept", "/ipd/board")]),
]
SAFETY = [("Wrong patient", "UHID, name, age shown at every desk"), ("Allergy", "Pharmacy and doctor see the patient's allergy"), ("Expired medicine", "Blocked at dispensing"),
          ("Wrong lab sample", "Barcode must match the order"), ("Critical vitals", "Red alert to the patient's doctor and the ward's duty staff, escalates to everyone if ignored"), ("After death", "Orders, vitals and dispensing are blocked"),
          ("Tampering", "Hash-chained audit log, signed certificate")]
WHO = [("Patient / family", "Own visits, reports, ward, bed and care team, certificate of own patient"), ("Reception", "Identity, scheme, queue, admission, care team"), ("Nurse", "Vitals, alerts and patients of the ward on duty, care team"),
       ("Doctor", "Own patients and the wards on duty; admits patients to IPD"), ("Lab / Pharmacy", "Only the order in front of them, never the profile"), ("Admin", "Audit log, reports, staff")]

def on(): return os.environ.get("DEMO_MODE", "1") == "1"

def register(ns):
    app, q, db, ts, now, event, audit, who, need, gph = (ns[k] for k in ("app", "q", "db", "ts", "now", "event", "audit", "who", "need", "gph"))
    from i18n import HI
    try:
        from i18n_tour import TOUR_HI
        for k, v in TOUR_HI.items(): HI.setdefault(k, v)
    except ImportError: pass

    def story():
        return q(f"SELECT a.*,{ns['PCOLS']},d.name doctor FROM appts a {ns['PJOIN']} JOIN users d ON d.id=a.doctor_id WHERE a.code=?", (CODE,), one=True)

    def seed():
        c = db()
        old = c.execute("SELECT id,pid FROM appts WHERE code=?", (CODE,)).fetchone()
        if old:
            for t in ("events", "careteam", "deaths", "notifications"):
                col = {"events": "appt_id", "careteam": "appt_id", "deaths": "appt_id", "notifications": "appt_code"}[t]
                try: c.execute(f"DELETE FROM {t} WHERE {col}=?", (old[0] if col == "appt_id" else CODE,))
                except Exception: pass
            c.execute("DELETE FROM appts WHERE id=?", (old[0],))
            if old[1]: c.execute("DELETE FROM patients WHERE id=? AND uhid LIKE 'TOUR%'", (old[1],))
        owner = c.execute("SELECT id FROM users WHERE phone='9000000001'").fetchone()[0]
        doc = c.execute("SELECT id FROM users WHERE name='Dr. Manoj Indurkar'").fetchone()
        doc = doc[0] if doc else c.execute("SELECT id FROM users WHERE role='doctor' AND dept='Medicine' LIMIT 1").fetchone()[0]
        adm = now() - timedelta(days=3, hours=4)
        pid = c.execute("INSERT INTO patients(uhid,owner_id,name,gender,age_years,age_asof,guardian_name,phone,village_ward,district,state,category,allergies,created,src) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        ("TOUR-0001", owner, "Ram Prasad Tiwari (DEMO)", "Male", 64, adm.strftime("%Y-%m-%d"), "Late Shri Lal Tiwari", "9000000001", "Ward 5, Rewa", "Rewa", "Madhya Pradesh", "Ayushman Bharat PM-JAY", "None known", ts(), "demo")).lastrowid
        aid = c.execute("INSERT INTO appts(code,patient_id,doctor_id,dept,date,slot,reason,created,kind,pid,status,ward,bed,src) VALUES(?,?,?,?,?,?,?,?,'IPD',?,'admitted','General ward','B-12','demo')",
                        (CODE, owner, doc, "Medicine", adm.strftime("%Y-%m-%d"), "IPD", "Fever and breathlessness (DEMO story)", adm.strftime(ns["FMT"]), pid)).lastrowid
        for cp, mins in (("Registered", 0), ("Reception", 10), ("Ward", 25)):
            c.execute("INSERT INTO events(appt_id,cp,ts,staff) VALUES(?,?,?,?)", (aid, cp, (adm + timedelta(minutes=mins)).strftime(ns["FMT"]), "DEMO"))
        c.commit(); c.close(); audit(who(), "TOUR_STORY_LOADED", CODE)

    def state():
        a = story()
        if not a: return dict(a=None, done=set(), tok=None)
        done = set()
        if q("SELECT 1 FROM careteam WHERE appt_id=?", (a["id"],), one=True): done.add("care")
        d = q("SELECT token FROM deaths WHERE appt_id=?", (a["id"],), one=True)
        tok = d["token"] if d else None
        if d: done |= {"death", "verify"}
        if q("SELECT 1 FROM audit WHERE action='BLOOD_STOCK' LIMIT 1", one=True): done.add("blood")
        if q("SELECT 1 FROM alerts LIMIT 1", one=True): done.add("safety")
        return dict(a=a, done=done, tok=tok)

    @app.context_processor
    def _tour_ctx():
        return dict(tour_on=on() and not request.path.startswith(("/static", "/tour")), tour_roles=ROLES)

    @app.route("/workflow")
    def workflow():
        return render_template("workflow.html", phases=PHASES, code=CODE, safety=SAFETY, who_sees=WHO, demo=on())

    @app.route("/tour")
    def tour():
        if not on(): abort(404)
        s = state(); steps = [dict(zip(("key", "role", "title", "todo", "see", "url"), x), url=x[5].format(code=CODE), done=x[0] in s["done"]) for x in STEPS]
        n_done = len([x for x in steps if x["done"]]); need_story = [x for x in steps if "{code}" in x["url"] or x["key"] in ("care", "death", "verify")]
        return render_template("tour.html", steps=steps, s=s, roles=ROLES, n_done=n_done, n_total=len([x for x in STEPS if x[0] in ("care", "blood", "death", "safety")]), team=SAMPLE_TEAM, code=CODE, cur=session.get("role"))

    @app.route("/tour/seed", methods=["POST"])
    def tour_seed():
        if not on(): abort(404)
        seed(); flash("Demo story loaded: Ram Prasad Tiwari (DEMO), admitted 3 days ago in the General ward."); return redirect("/tour")

    @app.route("/tour/fill", methods=["POST"])
    def tour_fill():
        if not on(): abort(404)
        a = story()
        if not a or a["status"] != "admitted": flash("Load the demo story first."); return redirect("/tour")
        t = SAMPLE_TEAM
        q("INSERT INTO careteam(appt_id,duty_doctor,nurse,attendant,shift,fam_name,fam_rel,fam_phone,updated,by) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(appt_id) DO UPDATE SET duty_doctor=excluded.duty_doctor,nurse=excluded.nurse,attendant=excluded.attendant,shift=excluded.shift,fam_name=excluded.fam_name,fam_rel=excluded.fam_rel,fam_phone=excluded.fam_phone,updated=excluded.updated,by=excluded.by",
          (a["id"], t["duty_doctor"], t["nurse"], t["attendant"], t["shift"], t["fam_name"], t["fam_rel"], t["fam_phone"], ts(), "DEMO"), commit=True)
        audit(who(), "TOUR_CARE_TEAM_FILLED", CODE); flash("Sample care team saved."); return redirect("/tour")

    def login_as(role):
        phone = ROLES[role][0]; u = q("SELECT * FROM users WHERE phone=?", (phone,), one=True)
        if not u and role == "nurse":
            q("INSERT INTO users(name,phone,role,pw,dept) VALUES('Demo Nurse',?,'nurse',?,NULL)", (phone, gph("nurse123")), commit=True); u = q("SELECT * FROM users WHERE phone=?", (phone,), one=True)
        if not u: abort(404)
        lang = session.get("lang"); session.clear(); session.update(uid=u["id"], role=u["role"], name=u["name"], dept=u["dept"], lang=lang or "en")

    @app.route("/tour/as/<role>")
    def tour_as(role):
        if not on() or role not in ROLES: abort(404)
        login_as(role); return redirect(HOME[role])

    @app.route("/tour/go/<key>")
    def tour_go(key):
        if not on(): abort(404)
        st = next((x for x in STEPS if x[0] == key), None)
        if not st: abort(404)
        if "{code}" in st[5] and not story(): flash("Load the demo story first."); return redirect("/tour")
        if key == "verify":
            d = q("SELECT d.token FROM deaths d JOIN appts a ON a.id=d.appt_id WHERE a.code=?", (CODE,), one=True)
            if not d: flash("Record the death first (step 8). Then the certificate and its QR exist."); return redirect("/tour")
            return redirect("/death/verify/" + d["token"])
        if st[1]: login_as(st[1])
        url = st[5].format(code=CODE)
        return redirect(url)
