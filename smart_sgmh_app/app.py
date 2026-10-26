"""Smart SGMH (Arogya Path): patient journey platform prototype for Sanjay Gandhi Memorial Hospital, Rewa.
Doctors, departments, batches and hospital-system links are SAMPLE/SIMULATED. AI only rewrites wording."""
import os, io, re, secrets, sqlite3, hashlib, random, string
from datetime import datetime, timedelta, timezone
from functools import wraps
from zoneinfo import ZoneInfo
import qrcode
from flask import Flask, request, redirect, session, flash, render_template, send_file, send_from_directory, abort, jsonify
from i18n import HI
from ai import answer as ai_answer
from werkzeug.security import generate_password_hash as gph, check_password_hash as cph, safe_join

app = Flask(__name__)
def _secret_key():  # never a key that is written in the source: SECRET_KEY env, else a random key created once per install (secret_key.txt)
    k = os.environ.get("SECRET_KEY")
    if k and k != "dev-only-change-me": return k
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "secret_key.txt")
    try:
        if not os.path.exists(f):
            with open(f, "w") as h: h.write(secrets.token_hex(32))
            try: os.chmod(f, 0o600)
            except OSError: pass
        return open(f).read().strip()
    except OSError: return secrets.token_hex(32)  # read-only disk: random per start (sessions end on restart)
LAB_ROOT = os.path.join(os.environ.get("UPLOAD_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")), "lab"); os.makedirs(LAB_ROOT, exist_ok=True)
app.secret_key = _secret_key()
app.config.update(SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_HTTPONLY=True, MAX_CONTENT_LENGTH=16 * 1024 * 1024)
app.jinja_env.globals["csrf"] = lambda: session.setdefault("csrf", secrets.token_hex(16))
app.jinja_env.globals["is_staff"] = lambda: session.get("role") in ("reception", "doctor", "nurse", "lab", "pharmacy", "admin")  # staff never see patient booking buttons

@app.before_request
def csrf_guard():  # every POST must carry the session's CSRF token
    if request.method == "POST" and not request.path.startswith("/api/v1/") and (not session.get("csrf") or request.form.get("csrf") != session["csrf"]): abort(400)

@app.after_request
def headers(r):
    r.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin"}); return r
DB = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "smartsgmh.db"))
STUCK_MIN = int(os.environ.get("STUCK_MIN", 30))
FMT = "%Y-%m-%d %H:%M:%S"
CPS = ["Registered", "Reception", "OPD", "Lab", "X-ray", "Ward", "OT", "Recovery", "Discharge"]
SLOTS = [f"{h:02d}:{m}" for h in range(8, 16) for m in ("00", "30")]
SAMPLE_STATUS = ["Ordered", "Sample collected", "At lab", "Processing", "Report ready"]
DEPTS = {  # keyword suggestion only; reception/doctor confirm
    "Medicine": ["fever", "bukhar", "बुखार", "cough", "khansi", "sugar", "diabetes", "bp", "weakness", "kamzori"],
    "Orthopaedics": ["bone", "haddi", "हड्डी", "fracture", "joint", "ghutna", "kamar", "back pain"],
    "Paediatrics": ["child", "baby", "bachch", "bache", "बच्च", "vaccine", "teeka"],
    "Gynaecology": ["pregnan", "garbh", "गर्भ", "delivery", "periods", "mahila"],
    "Cardiology": ["heart", "dil", "दिल", "seene", "सीने", "chest pain", "palpitation"],
    "ENT": ["ear", "kaan", "कान", "nose", "naak", "throat", "gala"]}

try: IST = ZoneInfo("Asia/Kolkata")
except Exception: IST = timezone(timedelta(hours=5, minutes=30))  # Windows without tzdata: India has no DST
def now(): return datetime.now(IST).replace(tzinfo=None)
def ts(): return now().strftime(FMT)
def db():
    c = sqlite3.connect(DB, timeout=15); c.row_factory = sqlite3.Row
    try: c.execute("PRAGMA synchronous=NORMAL"); c.execute("PRAGMA temp_store=MEMORY")
    except sqlite3.Error: pass
    return c
def q(sql, a=(), one=False, commit=False):
    c = db()
    try:  # always close, even when the statement fails (for example a duplicate-slot IntegrityError), so no write lock is left behind
        cur = c.execute(sql, a); r = cur.fetchone() if one else cur.fetchall()
        if commit: c.commit()
        return cur.lastrowid if commit else r
    finally: c.close()

# Only map ward choices whose meaning matches one inventory unit exactly.
# "ICU / HDU" is intentionally not mapped because the form does not identify
# which unit the patient is assigned to; "Private room" has no inventory unit.
BED_UNIT_BY_WARD = {
    "General ward": "General Ward",
    "Maternity ward": "Maternity Ward",
    "Paediatric ward": "Paediatric Ward",
}


def _ipd_bed_transition(appt_code, new_status, bed_number=None, actor="system"):
    """Atomically change IPD status and reconcile mapped ward occupancy.

    Returns (ok, reason). Existing admissions remain usable even when a ward has
    no configured capacity; in that case the occupancy count is stored but the
    public API continues to mark it unverified until staff sets a total.
    """
    c = db()
    try:
        c.execute("BEGIN IMMEDIATE")
        a = c.execute("SELECT id,kind,status,ward FROM appts WHERE code=?", (appt_code,)).fetchone()
        expected = "booked" if new_status == "admitted" else "admitted"
        if not a or a["kind"] != "IPD" or a["status"] != expected:
            c.rollback()
            return False, "Admission request not found or status has changed."

        unit = BED_UNIT_BY_WARD.get(a["ward"] or "")
        inventory = c.execute(
            "SELECT total_beds,unavailable_beds FROM bed_inventory WHERE unit_name=?",
            (unit,),
        ).fetchone() if unit else None

        if new_status == "admitted" and inventory and inventory["total_beds"] is not None:
            active = c.execute(
                "SELECT COUNT(*) n FROM appts WHERE kind='IPD' AND status='admitted' AND ward=?",
                (a["ward"],),
            ).fetchone()["n"]
            if active + inventory["unavailable_beds"] >= inventory["total_beds"]:
                c.rollback()
                return False, f"{unit} has no confirmed free capacity. Please verify with the admission desk."

        if new_status == "admitted":
            c.execute("UPDATE appts SET status='admitted',bed=? WHERE id=?", (bed_number, a["id"]))
        else:
            c.execute("UPDATE appts SET status='discharged' WHERE id=?", (a["id"],))

        if unit and inventory:
            occupied = c.execute(
                "SELECT COUNT(*) n FROM appts WHERE kind='IPD' AND status='admitted' AND ward=?",
                (a["ward"],),
            ).fetchone()["n"]
            total = inventory["total_beds"]
            unavailable = inventory["unavailable_beds"]
            if total is None:
                c.execute("UPDATE bed_inventory SET occupied_beds=? WHERE unit_name=?", (occupied, unit))
            elif occupied + unavailable <= total:
                stamp = ts()
                c.execute(
                    "UPDATE bed_inventory SET occupied_beds=?,updated_at=?,updated_by=? WHERE unit_name=?",
                    (occupied, stamp, actor, unit),
                )
            # If legacy records exceed configured capacity, keep the appointment
            # transition but do not violate the inventory CHECK constraint.
        c.commit()
        return True, unit
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def init():
    c = db(); c.executescript("""
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name,phone UNIQUE,role,pw,dept);
CREATE TABLE IF NOT EXISTS appts(id INTEGER PRIMARY KEY,code UNIQUE,patient_id,doctor_id,dept,date,slot,reason,status DEFAULT 'booked',token,created);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,appt_id,cp,ts,staff);
CREATE TABLE IF NOT EXISTS notes(appt_id INTEGER PRIMARY KEY,diagnosis,meds,do_text,avoid_text,care,followup,simplified,approved DEFAULT 0);
CREATE TABLE IF NOT EXISTS samples(id INTEGER PRIMARY KEY,appt_id,barcode UNIQUE,test,status,report,ts);
CREATE TABLE IF NOT EXISTS meds(id INTEGER PRIMARY KEY,batch UNIQUE,name,expiry);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,ts,actor,action,detail,prev,hash);
CREATE TABLE IF NOT EXISTS bed_inventory(
 id INTEGER PRIMARY KEY, unit_name TEXT UNIQUE NOT NULL,
 total_beds INTEGER, occupied_beds INTEGER NOT NULL DEFAULT 0,
 unavailable_beds INTEGER NOT NULL DEFAULT 0,
 updated_at TEXT, updated_by TEXT,
 CHECK(total_beds IS NULL OR total_beds >= 0),
 CHECK(occupied_beds >= 0), CHECK(unavailable_beds >= 0),
 CHECK(total_beds IS NULL OR occupied_beds + unavailable_beds <= total_beds)
);""")
    c.executescript("""CREATE TABLE IF NOT EXISTS doctor_avail(doctor_id INTEGER PRIMARY KEY,status DEFAULT 'available',note);
CREATE TABLE IF NOT EXISTS lab_tests(id INTEGER PRIMARY KEY,name UNIQUE,category,prep,tat);""")
    c.executescript("""CREATE TABLE IF NOT EXISTS patients(id INTEGER PRIMARY KEY,uhid TEXT UNIQUE,owner_id INTEGER,relation TEXT DEFAULT 'Self',name,gender,dob,age_years INTEGER,age_asof,
guardian_name,guardian_rel,phone,village_ward,district,state,pin,blood_group,allergies,conditions,category DEFAULT 'General',disabled INTEGER DEFAULT 0,abha,pmjay,id_type,id_last4,
em_name,em_phone,em_rel,lang DEFAULT 'hi',consent_ts,sms_ok INTEGER DEFAULT 1,created,created_by,src DEFAULT 'online',active INTEGER DEFAULT 1);
CREATE INDEX IF NOT EXISTS ix_pat_owner ON patients(owner_id);CREATE INDEX IF NOT EXISTS ix_pat_phone ON patients(phone);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY,user_id INTEGER,appt_code,phone,ts,text,channel DEFAULT 'SMS',seen INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS otps(id INTEGER PRIMARY KEY,phone,purpose,code_hash,expires,tries INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS otp_log(id INTEGER PRIMARY KEY,phone,ip,ts);
CREATE INDEX IF NOT EXISTS i_otp_log ON otp_log(phone,ts);
CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY,appt_id UNIQUE,rating INTEGER,comment,ts);""")
    for unit in ("General Ward", "ICU", "HDU", "Paediatric Ward", "NICU", "PICU", "Maternity Ward"):
        c.execute("INSERT OR IGNORE INTO bed_inventory(unit_name,total_beds,occupied_beds,unavailable_beds,updated_at,updated_by) VALUES(?,NULL,0,0,NULL,NULL)", (unit,))
    # Fresh database (for example a new Render deploy without smartsgmh.db): fill the clearly labelled DEMO bed counts so the Beds page is not blank.
    # Only when EVERY unit is still empty, so real counts entered by staff are never overwritten. Set SEED_DEMO_BEDS=0 to keep them empty.
    if os.environ.get("SEED_DEMO_BEDS", "1") == "1" and not c.execute("SELECT 1 FROM bed_inventory WHERE total_beds IS NOT NULL").fetchone():
        _stamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
        for _u, _t, _o, _x in (("General Ward", 100, 65, 5), ("ICU", 20, 12, 2), ("HDU", 15, 8, 1), ("Paediatric Ward", 30, 18, 2), ("NICU", 12, 7, 1), ("PICU", 10, 5, 1), ("Maternity Ward", 25, 14, 2)):
            c.execute("UPDATE bed_inventory SET total_beds=?,occupied_beds=?,unavailable_beds=?,updated_at=?,updated_by=? WHERE unit_name=?", (_t, _o, _x, _stamp, "DEMO SAMPLE DATA - NOT REAL HOSPITAL DATA", _u))
    for tbl, col in [("meds", "stock INTEGER DEFAULT 0"), ("meds", "category TEXT DEFAULT 'General'"), ("notes", "dispensed INTEGER DEFAULT 0"), ("samples", "category TEXT"), ("appts", "kind TEXT DEFAULT 'OPD'"), ("appts", "ward TEXT"), ("appts", "bed TEXT"),
                     ("appts", "pid INTEGER"), ("appts", "prio INTEGER DEFAULT 0"), ("appts", "prio_why TEXT"), ("appts", "referred_by TEXT"), ("appts", "visit_type TEXT"),
                     ("appts", "src TEXT DEFAULT 'online'"), ("appts", "resched_n INTEGER DEFAULT 0"),
                     ("appts", "adm_type TEXT"), ("appts", "att_name TEXT"), ("appts", "att_phone TEXT"), ("appts", "att_rel TEXT"), ("appts", "mobility TEXT"),
                     ("notes", "followup_date TEXT"), ("notes", "tests_advised TEXT"), ("notifications", "kind TEXT DEFAULT 'info'"), ("notifications", "level TEXT"),
                     ("notes", "recalled INTEGER DEFAULT 0"), ("notes", "recall_reason TEXT"), ("notes", "recall_by TEXT"), ("notes", "recall_ts TEXT"),
                     ("notes", "flagged INTEGER DEFAULT 0"), ("notes", "flag_reason TEXT"), ("notes", "flag_by TEXT"), ("notes", "flag_ts TEXT"), ("samples", "report_file TEXT")]:
        try: c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col}")
        except sqlite3.OperationalError: pass
    try: c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_slot ON appts(doctor_id,date,slot) WHERE status!='cancelled' AND kind='OPD' AND slot!='Walk-in'")  # no double booking, even under a race
    except sqlite3.OperationalError: pass  # an old DB that already holds duplicates keeps working; the app still checks in code
    if not c.execute("SELECT 1 FROM lab_tests").fetchone():  # SAMPLE catalogue and stock
        F, N, M = "Fasting 8-12 hours", "No special preparation", "Morning clean-catch sample"
        for n, cat, p, t in [("Complete Blood Count (CBC)", "Blood Tests", N, "2-4 hours"), ("Hemoglobin", "Blood Tests", N, "1-2 hours"), ("Blood Sugar (Fasting)", "Blood Tests", F, "1-2 hours"),
                             ("Lipid Profile", "Blood Tests", F, "4-6 hours"), ("Liver Function Test (LFT)", "Blood Tests", F, "4-6 hours"), ("Kidney Function Test (KFT)", "Blood Tests", N, "4-6 hours"),
                             ("Thyroid (TSH)", "Blood Tests", N, "6-8 hours"), ("Malaria Antigen", "Pathology", N, "1-2 hours"), ("Widal Test", "Pathology", N, "2-4 hours"),
                             ("Biopsy (Histopathology)", "Pathology", "Sample collected by lab staff", "3-7 days"), ("Urine Routine", "Urine and Stool", M, "1-2 hours"), ("Stool Routine", "Urine and Stool", "Follow lab instructions", "2-4 hours"),
                             ("X-ray Chest", "Imaging", N, "1-2 hours")]:
            c.execute("INSERT INTO lab_tests(name,category,prep,tat) VALUES(?,?,?,?)", (n, cat, p, t))
        t0 = now().date()
        for b, n, cat, exp, st in [("B4001", "Paracetamol 500 mg tablet", "Tablet", 300, 250), ("B4002", "Amoxicillin 500 mg capsule", "Capsule", 200, 12), ("B4003", "ORS sachet", "Powder", 500, 0),
                                   ("B4004", "Iron-Folic Acid tablet", "Tablet", 250, 80), ("B4005", "Metformin 500 mg tablet", "Tablet", 220, 60), ("B4006", "Cetirizine 10 mg tablet", "Tablet", 180, 5),
                                   ("B4007", "Pantoprazole 40 mg tablet", "Tablet", 260, 90), ("B4008", "Salbutamol inhaler", "Inhaler", 150, 25)]:
            c.execute("INSERT OR IGNORE INTO meds(batch,name,expiry,stock,category) VALUES(?,?,?,?,?)", (b, n, str(t0 + timedelta(days=exp)), st, cat))
        c.execute("UPDATE meds SET stock=100,category='Tablet' WHERE batch='B1001'"); c.execute("UPDATE meds SET stock=40,category='Syrup' WHERE batch='B2002'"); c.execute("UPDATE meds SET stock=15,category='Capsule' WHERE batch='B3003'")
    if not c.execute("SELECT 1 FROM users").fetchone():
        seed = [("Admin", "9000000000", "admin", "admin123", None), ("Demo Patient", "9000000001", "patient", "pat123", None),
                ("Reception Desk", "9000000010", "reception", "rec123", None), ("Lab Tech", "9000000020", "lab", "lab123", None),
                ("Pharmacist", "9000000030", "pharmacy", "ph123", None)]
        for i, d in enumerate(DEPTS):  # SAMPLE doctors
            seed.append((f"Dr. Sample ({d})", f"90000000{41+i}", "doctor", "doc123", d))
        seed += [("Dr. Sample 2 (Medicine)", "9000000051", "doctor", "doc123", "Medicine"), ("Dr. Sample 2 (Paediatrics)", "9000000052", "doctor", "doc123", "Paediatrics"), ("Dr. Sample 2 (Orthopaedics)", "9000000053", "doctor", "doc123", "Orthopaedics")]
        for n, p, r, pw, d in seed: c.execute("INSERT INTO users(name,phone,role,pw,dept) VALUES(?,?,?,?,?)", (n, p, r, gph(pw), d))
        t = now().date()
        for b, n, e in [("B1001", "Sample Tablet A", t + timedelta(days=400)), ("B2002", "Sample Syrup B", t - timedelta(days=20)), ("B3003", "Sample Capsule C", t + timedelta(days=12))]:
            c.execute("INSERT INTO meds(batch,name,expiry) VALUES(?,?,?)", (b, n, str(e)))
    for col in ("degree", "designation", "photo"):
        try: c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError: pass
    from doctors_data import DOCTORS  # real SGMH faculty (public college site); demo logins keep their phone/password
    for ph, nm, dp, ds, dg, pic in DOCTORS:
        if c.execute("SELECT 1 FROM users WHERE phone=?", (ph,)).fetchone():
            c.execute("UPDATE users SET name=?,dept=?,designation=?,degree=?,photo=? WHERE phone=?", (nm, dp, ds, dg, pic, ph))
        else: c.execute("INSERT INTO users(name,phone,role,pw,dept,designation,degree,photo) VALUES(?,?,?,?,?,?,?,?)", (nm, ph, "doctor", gph("doc123"), dp, ds, dg, pic))
    seed_roster(c)  # OPD roster read from the hospital signboards (opd_roster.py)
    c.commit(); c.close()

def seed_roster(c):
    """Load the weekday roster from opd_roster.py: adds doctors that are on the boards but not in the DB yet and rebuilds doctor_days."""
    import opd_roster as R, zlib
    c.execute("CREATE TABLE IF NOT EXISTS doctor_days(doctor_id INTEGER, wd INTEGER, room TEXT DEFAULT '', desig TEXT, PRIMARY KEY(doctor_id,wd,room))")
    c.execute("DELETE FROM doctor_days"); ids = {}
    for dept, days in R.ROSTER.items():
        for wd, people in days.items():
            for name, desig, room in people:
                name = R.ALIASES.get(name, name); key = (name, dept)
                if key not in ids:
                    r = c.execute("SELECT id FROM users WHERE role='doctor' AND name=? AND dept=?", (name, dept)).fetchone()
                    if r: ids[key] = r[0]
                    else:
                        n = zlib.crc32(name.encode()) % 10**8
                        while c.execute("SELECT 1 FROM users WHERE phone=?", (f"92{n:08d}",)).fetchone(): n = (n + 1) % 10**8
                        ids[key] = c.execute("INSERT INTO users(name,phone,role,pw,dept,designation,degree) VALUES(?,?,?,?,?,?,?)",
                                             (name, f"92{n:08d}", "doctor", gph("doc123"), dept, desig or "Faculty / Consultant", None)).lastrowid
                c.execute("INSERT OR IGNORE INTO doctor_days(doctor_id,wd,room,desig) VALUES(?,?,?,?)", (ids[key], wd, room or "", desig))

# ---- tamper-evident audit (hash chain) ----
def audit(actor, action, detail=""):
    c = db(); last = c.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
    prev = last["hash"] if last else "0"; t = ts()
    h = hashlib.sha256(f"{prev}|{t}|{actor}|{action}|{detail}".encode()).hexdigest()
    c.execute("INSERT INTO audit(ts,actor,action,detail,prev,hash) VALUES(?,?,?,?,?,?)", (t, actor, action, detail, prev, h)); c.commit(); c.close()

def verify_chain():
    prev = "0"
    for r in q("SELECT * FROM audit ORDER BY id"):
        h = hashlib.sha256(f"{prev}|{r['ts']}|{r['actor']}|{r['action']}|{r['detail']}".encode()).hexdigest()
        if r["prev"] != prev or r["hash"] != h: return False, r["id"]
        prev = r["hash"]
    return True, 0

def who(): return f"{session.get('role')}:{session.get('name')}"
def need(*roles):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if "uid" not in session:
                session["next"] = request.full_path.rstrip("?"); flash("Please log in."); return redirect("/start" if roles == ("patient",) else "/login")
            if session["role"] not in roles: abort(403)
            return f(*a, **k)
        return w
    return deco

def code(prefix, n=5): return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=n))
def event(appt_id, cp): q("INSERT INTO events(appt_id,cp,ts,staff) VALUES(?,?,?,?)", (appt_id, cp, ts(), who()), commit=True)
# patient identity = the patient PROFILE (patients table) when the booking has one, else the login account (older bookings)
PJOIN = "LEFT JOIN users p ON p.id=a.patient_id LEFT JOIN patients pt ON pt.id=a.pid"
PCOLS = ("COALESCE(pt.name,p.name) pname,COALESCE(pt.phone,p.phone,'') pphone,pt.uhid uhid,pt.gender pgender,pt.dob pdob,pt.age_years page,pt.age_asof pasof,"
         "pt.category pcat,CASE WHEN pt.id IS NOT NULL THEN COALESCE(pt.allergies,'') ELSE p.allergies END pallergy,pt.conditions pcond,pt.blood_group pbg,pt.disabled pdis")
def appt_row(c): return q(f"SELECT a.*,{PCOLS},d.name doctor FROM appts a {PJOIN} JOIN users d ON d.id=a.doctor_id WHERE a.code=?", (c,), one=True)

RED_FLAGS = ["chest pain", "seene mein dard", "सीने", "unconscious", "behosh", "बेहोश", "not breathing", "saans nahi", "सांस नहीं", "heavy bleeding", "bahut khoon", "stroke", "lakwa", "seizure", "daura", "snake", "saanp", "सांप", "poison", "zeher", "suicide"]
def red_flag(t): t = (t or "").lower(); return any(k.lower() in t for k in RED_FLAGS)

def suggest(text):
    t = (text or "").lower(); best = max(DEPTS, key=lambda d: sum(k.lower() in t for k in DEPTS[d]))
    return best if any(k.lower() in t for k in DEPTS[best]) else None

def simplify(n):  # doctor's fields -> plain Hindi/English text; optional LLM rewording
    meds = "\n".join(f"  - {m.strip()}" for m in (n["meds"] or "").splitlines() if m.strip()) or "  -"
    txt = (f"बीमारी / Diagnosis: {n['diagnosis'] or '-'}\n\nदवाइयाँ / Medicines:\n{meds}\n\nक्या खाएँ / Eat: {n['do_text'] or '-'}\n"
           f"क्या न खाएँ / Avoid: {n['avoid_text'] or '-'}\nसावधानी / Care: {n['care'] or '-'}\nअगली बार / Follow-up: {n['followup'] or '-'}")
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            r = anthropic.Anthropic().messages.create(model=os.environ.get("MODEL", "claude-sonnet-5-5"), max_tokens=700,
                system="Rewrite this doctor's note in very simple Hindi. Keep every medicine name, dose and duration EXACTLY as written. Add nothing new.",
                messages=[{"role": "user", "content": txt}])
            out = "".join(b.text for b in r.content if b.type == "text")
            if out.strip(): return out
        except Exception: pass
    return txt

# ---- auth ----
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")  # built React app (npm run build)

@app.route("/app/", defaults={"p": ""})
@app.route("/app/<path:p>")
def react_app(p):  # ONE SERVER: Flask serves the React build; unknown paths fall back to index.html (client-side routing)
    if not os.path.isfile(os.path.join(DIST, "index.html")):
        return "React build not found. Run: cd frontend && npm install && npm run build", 503
    f = safe_join(DIST, p) if p else None
    if f and os.path.isfile(f): return send_from_directory(DIST, p)
    return send_from_directory(DIST, "index.html")

HOME_OF = {"patient": "/app/", "reception": "/reception", "doctor": "/doctor", "lab": "/lab", "pharmacy": "/pharmacy", "nurse": "/vitals", "admin": "/admin"}
@app.route("/")
def index():  # the whole website is open to everyone; login / registration is asked only when a patient books or opens personal data
    return redirect(HOME_OF.get(session.get("role"), "/app/"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = q("SELECT * FROM users WHERE phone=?", (request.form["phone"].strip(),), one=True)
        if u and u["role"] == "patient" and cph(u["pw"], request.form["pw"]): flash("Patients log in with an OTP on the start page."); return redirect("/start")
        if u and cph(u["pw"], request.form["pw"]):
            nxt, lang = session.get("next"), session.get("lang")
            session.clear(); session.update(uid=u["id"], role=u["role"], name=u["name"], dept=u["dept"], lang=lang or "en")
            if nxt and nxt.startswith("/") and not nxt.startswith("//") and u["role"] in ("admin", "patient"): return redirect(nxt)
            return redirect({"patient": "/mine", "reception": "/reception", "doctor": "/doctor", "lab": "/lab", "pharmacy": "/pharmacy", "nurse": "/vitals", "admin": "/admin"}[u["role"]])
        flash("Wrong phone or password.")
    return render_template("login.html")

@app.route("/logout")
def logout(): session.clear(); return redirect("/")

# ---- patient ----
from urllib.parse import urlencode
WARDS = ["General ward", "Private room", "ICU / HDU", "Maternity ward", "Paediatric ward"]
def burl(base, **kw): return base + "?" + urlencode({k: v for k, v in kw.items() if v not in (None, "")})
def next_opd_day(d):
    while d.weekday() == 6: d += timedelta(days=1)
    return d
def default_date():
    n = now(); d = n.date()
    return next_opd_day(d + timedelta(days=1) if n.hour >= 16 else d)
def works_on(doc_id, date):
    """True if the doctor sits in OPD on that date. Doctors not listed on the boards (no roster rows) count as every day Mon-Sat."""
    try: wd = datetime.strptime(date, "%Y-%m-%d").weekday()
    except (ValueError, TypeError): return True
    rows = q("SELECT wd FROM doctor_days WHERE doctor_id=?", (doc_id,))
    return not rows or wd in {r["wd"] for r in rows}
def slot_states(doc_id, date):
    taken = {r["slot"] for r in q("SELECT slot FROM appts WHERE doctor_id=? AND date=? AND status!='cancelled' AND kind='OPD'", (doc_id, date))}
    from opd_roster import DEPT_HOURS
    u = q("SELECT dept FROM users WHERE id=?", (doc_id,), one=True); lo, hi = DEPT_HOURS.get(u["dept"] if u else None, (SLOTS[0], SLOTS[-1]))
    day_off = not works_on(doc_id, date)
    n = now(); out = []
    for s in SLOTS:
        h, m = map(int, s.split(":"))
        past = date == n.date().isoformat() and (h, m) <= (n.hour, n.minute)
        out.append(dict(slot=s, state="off" if day_off or not (lo <= s <= hi) else "taken" if s in taken else "past" if past else "free"))
    return out
def next_free(doc_id):
    d = default_date()
    for _ in range(8):
        free = [x["slot"] for x in slot_states(doc_id, d.isoformat()) if x["state"] == "free"]
        if free: return dict(date=d.isoformat(), slot=free[0], today=d == now().date())
        d = next_opd_day(d + timedelta(days=1))
    return None
EMERG_MSG = "Possible emergency: please go to the Emergency gate or call 112."

def d_leave(d): return d["code"] == "leave"

# /admit (IPD admission request) now lives in registration.py: it uses the same patient profile, completeness check and family members as OPD booking.

@app.route("/opd")
def opd_page():  # OPD hub: how it works, then every doctor (filter by department), then Book (login is asked at Book)
    dept = request.args.get("dept", ""); alld = [d for d in get_docs() if d["code"] != "leave"]; depts = sorted({d["dept"] for d in alld})
    return render_template("opd.html", docs=[d for d in alld if not dept or d["dept"] == dept], depts=depts, dept=dept if dept in depts else "")
@app.route("/ipd")
def ipd_page(): return render_template("ipd.html", wards=WARDS)

@app.route("/mine")
@need("patient")
def mine(): return render_template("mine.html", rows=q("SELECT a.*,COALESCE(pt.name,p.name) pname,pt.uhid FROM appts a LEFT JOIN users p ON p.id=a.patient_id LEFT JOIN patients pt ON pt.id=a.pid WHERE a.patient_id=? ORDER BY a.id DESC", (session["uid"],)), today=now().date().isoformat())

@app.route("/qr/<c>.png")
def qr(c):
    b = io.BytesIO(); qrcode.make(c).save(b, format="PNG"); b.seek(0); return send_file(b, mimetype="image/png")

@app.route("/track", methods=["GET", "POST"])
def track():
    if request.method == "POST":
        a = appt_row(request.form["code"].strip().upper())
        if a and len(a["pphone"]) >= 4 and request.form["last4"].strip().isdigit() and a["pphone"][-4:] == request.form["last4"].strip():
            session.setdefault("track", []); session["track"] = session["track"] + [a["code"]]; return redirect(f"/visit/{a['code']}")
        flash("Code and last 4 digits do not match.")
    return render_template("track.html")

def can_view(a, c):
    return (session.get("role") == "patient" and session.get("uid") == a["patient_id"]) or c in session.get("track", []) or session.get("role") in ("reception", "doctor", "lab", "admin")

def avg_wait():  # recent average Reception -> OPD minutes
    rows = q("SELECT e1.ts r, MIN(e2.ts) o FROM events e1 JOIN events e2 ON e2.appt_id=e1.appt_id AND e2.cp='OPD' AND e2.id>e1.id WHERE e1.cp='Reception' GROUP BY e1.appt_id")
    m = [(datetime.strptime(r["o"], FMT) - datetime.strptime(r["r"], FMT)).total_seconds() / 60 for r in rows if r["o"]]
    return round(sum(m) / len(m)) if m else None

def vdata(a):
    ev = [dict(cp=e["cp"], ts=e["ts"]) for e in q("SELECT * FROM events WHERE appt_id=? ORDER BY id", (a["id"],))]
    pos = est = None
    if a["status"] == "arrived" and a["token"]:
        pos = q("SELECT COUNT(*) n FROM appts WHERE doctor_id=? AND date=? AND status='arrived' AND (COALESCE(prio,0)>? OR (COALESCE(prio,0)=? AND token<?))", (a["doctor_id"], a["date"], a["prio"] or 0, a["prio"] or 0, a["token"]), one=True)["n"]
        est = pos * int(os.environ.get("CONSULT_MIN", 8))
    n = q("SELECT * FROM notes WHERE appt_id=? AND approved=1", (a["id"],), one=True)
    last = ev[-1] if ev else None
    stale = bool(last and last["cp"] != "Discharge" and (now() - datetime.strptime(last["ts"], FMT)).total_seconds() > 60 * STUCK_MIN)
    return dict(status=a["status"], token=a["token"], pos=pos, est_min=est, avg_wait=avg_wait(), events=ev, last=last["ts"] if last else None, stale=stale,
                advice=n["simplified"] if n else None, samples=[dict(test=x["test"], barcode=x["barcode"], status=x["status"], report=x["report"], ts=x["ts"]) for x in q("SELECT * FROM samples WHERE appt_id=?", (a["id"],))])

@app.route("/visit/<c>")
def visit(c):
    a = appt_row(c)
    if not a: abort(404)
    if not can_view(a, c): flash("Please log in or use Track patient."); return redirect("/track")
    return render_template("visit.html", a=a, cps=CPS)

@app.route("/api/visit/<c>")
def api_visit(c):
    a = appt_row(c)
    if not a or not can_view(a, c): return jsonify(error="forbidden"), 403
    return jsonify(vdata(a))

@app.route("/rx/<c>")
def rx(c):
    a = appt_row(c)
    if not a or not can_view(a, c): abort(403)
    n = q("SELECT * FROM notes WHERE appt_id=? AND approved=1", (a["id"],), one=True)
    if not n:
        if q("SELECT 1 FROM notes WHERE appt_id=? AND recalled=1", (a["id"],), one=True): flash("Your doctor has withdrawn this prescription. Do not take medicines from it. A corrected one will appear here.")
        else: flash("Advice not approved yet.")
        return redirect(f"/visit/{c}")
    return render_template("rx.html", a=a, note=n, tests=q("SELECT * FROM samples WHERE appt_id=?", (a["id"],)), given=q("SELECT * FROM dispensed WHERE appt_id=? ORDER BY id", (a["id"],)))

@app.route("/cancel/<c>", methods=["POST"])
@need("patient")
def cancel(c):
    a = appt_row(c)
    if not a or a["patient_id"] != session["uid"] or a["status"] != "booked": flash("Only your upcoming bookings can be cancelled.")
    else: q("UPDATE appts SET status='cancelled' WHERE id=?", (a["id"],), commit=True); audit(who(), "CANCEL", c); sms(a["pphone"], f"SGMH Rewa: {'admission request' if a['kind'] == 'IPD' else 'appointment'} {c} for {a['pname']} is cancelled.", session["uid"], c); flash("Admission request cancelled." if a["kind"] == "IPD" else "Appointment cancelled.")
    return redirect("/mine")

# ---- reception / scan ----
@app.route("/reception", methods=["GET", "POST"])
@need("reception")
def reception():
    if request.method == "POST":
        a = appt_row(request.form["code"].strip().upper())
        if not a: flash("Appointment not found.")
        elif a["kind"] == "IPD": flash("This is an IPD admission request. Use the IPD list below.")
        elif a["status"] != "booked": flash(f"Already {a['status']}.")
        elif a["date"] != now().date().isoformat(): flash(f"This appointment is for {a['date']}.")
        else:
            tok = q("SELECT COUNT(*) n FROM appts WHERE doctor_id=? AND date=? AND token IS NOT NULL", (a["doctor_id"], a["date"]), one=True)["n"] + 1
            q("UPDATE appts SET status='arrived',token=? WHERE id=?", (tok, a["id"]), commit=True)
            event(a["id"], "Reception"); audit(who(), "ARRIVED", a["code"]); flash(f"{a['pname']}: token {tok}.")
            return redirect("/reception?v=" + a["code"])
        return redirect("/reception")
    rows = q(f"SELECT a.*,{PCOLS},d.name doctor FROM appts a {PJOIN} JOIN users d ON d.id=a.doctor_id WHERE a.date=? AND a.kind='OPD' AND a.status!='cancelled' ORDER BY a.slot", (now().date().isoformat(),))
    ipd = q(f"SELECT a.*,{PCOLS},d.name doctor FROM appts a {PJOIN} JOIN users d ON d.id=a.doctor_id WHERE a.kind='IPD' AND a.status IN ('booked','admitted') ORDER BY a.id DESC")
    vp = appt_row(request.args.get("v", "").strip().upper()) if request.args.get("v") else None
    if vp and vp["date"] != now().date().isoformat(): vp = None
    vb = []
    if vp and vp["pid"]:
        pf = get_profile(vp["pid"]); vb = docs_to_bring(pf, bool(vp["referred_by"]), "Pregnant woman" in (vp["prio_why"] or ""))
        audit(who(), "VERIFY_VIEW", vp["code"])
    return render_template("reception.html", rows=rows, ipd=ipd, vp=vp, vbring=vb)

@app.route("/reception/admit/<c>", methods=["POST"])
@need("reception", "admin")
def ipd_admit(c):
    a = appt_row(c); bed = request.form.get("bed", "").strip()[:20]
    if not a or a["kind"] != "IPD" or a["status"] != "booked": flash("Admission request not found.")
    elif not request.form.get("id_ok"): flash("Tick 'photo ID checked' before admitting the patient.")
    elif not bed: flash("Enter the bed number.")
    else:
        ok, detail = _ipd_bed_transition(c, "admitted", bed, who())
        if not ok:
            flash(detail)
        else:
            event(a["id"], "Reception"); event(a["id"], "Ward")
            audit(who(), "ADMITTED", f"{c} bed {bed} id-checked; bed_sync={detail or 'not mapped'}")
            flash(f"{a['pname']}: admitted, bed {bed}.")
    return redirect("/reception")

@app.route("/reception/discharge/<c>", methods=["POST"])
@need("reception", "admin")
def ipd_discharge(c):
    a = appt_row(c)
    if not a or a["kind"] != "IPD" or a["status"] != "admitted": flash("Admission request not found.")
    elif (globals().get("ipd_discharge_block") or (lambda _a: None))(a):
        flash(globals()["ipd_discharge_block"](a))
    else:
        ok, detail = _ipd_bed_transition(c, "discharged", actor=who())
        if not ok:
            flash(detail)
        else:
            event(a["id"], "Discharge")
            audit(who(), "DISCHARGED", f"{c}; bed_sync={detail or 'not mapped'}")
            flash(f"{a['pname']}: discharged." + " " + ((globals().get("ipd_discharge_note") or (lambda _a: None))(a) or ""))
    return redirect("/reception")

@app.route("/scan", methods=["GET", "POST"])
@need("reception", "lab", "pharmacy", "doctor")
def scan():
    if request.method == "POST":
        a = appt_row(request.form["code"].strip().upper()); cp = request.form["cp"]
        if not a or cp not in CPS: flash("Unknown code or checkpoint.")
        else: event(a["id"], cp); audit(who(), "SCAN", f"{a['code']}@{cp}"); flash(f"{a['pname']}: {cp} recorded.")
        return redirect("/scan")
    return render_template("scan.html", cps=CPS)

# ---- doctor ----
@app.route("/doctor")
@need("doctor")
def doctor():
    td = now().date().isoformat(); me = session["role"] == "doctor"
    view = request.args.get("view", "today").lower()
    if view not in {"today", "upcoming", "past", "cancelled", "all"}: view = "today"
    where = ["(?=0 OR a.doctor_id=?)"]
    args = [1 if me else 0, session["uid"]]
    if view == "today":
        where.append("(a.date=? OR (a.kind='IPD' AND a.status IN ('booked','admitted')))" ); args.append(td)
        where.append("a.status!='cancelled'")
    elif view == "upcoming":
        where.extend(["a.date>?", "a.status IN ('booked','arrived','admitted')"]); args.append(td)
    elif view == "past":
        where.extend(["(a.date<? OR a.status IN ('seen','completed','discharged'))", "a.status!='cancelled'"]); args.append(td)
    elif view == "cancelled":
        where.append("a.status='cancelled'")
    rows = q(f"SELECT a.*,{PCOLS},d.name dname FROM appts a {PJOIN} JOIN users d ON d.id=a.doctor_id WHERE {' AND '.join(where)} ORDER BY a.date DESC,a.token IS NULL,CASE WHEN a.token IS NULL THEN 0 ELSE a.prio END DESC,a.token,a.slot", tuple(args))
    av = q("SELECT status,note FROM doctor_avail WHERE doctor_id=?", (session["uid"],), one=True) if me else None
    counts = {}
    for v, sql, extra in [
        ("today", "(date=? OR (kind='IPD' AND status IN ('booked','admitted'))) AND status!='cancelled'", (td,)),
        ("upcoming", "date>? AND status IN ('booked','arrived','admitted')", (td,)),
        ("past", "(date<? OR status IN ('seen','completed','discharged')) AND status!='cancelled'", (td,)),
        ("cancelled", "status='cancelled'", ()),
        ("all", "1=1", ())]:
        counts[v] = q(f"SELECT COUNT(*) n FROM appts WHERE ({'doctor_id=?' if me else '1=1'}) AND {sql}", ((session['uid'],) if me else ()) + extra, one=True)["n"]
    return render_template("doctor.html", rows=rows, av=av, me=me, view=view, counts=counts)

@app.route("/doctor/availability", methods=["POST"])
@need("doctor")
def my_availability():
    set_avail(session["uid"], request.form.get("status"), request.form.get("note", "")); flash("Availability updated."); return redirect("/doctor")

@app.route("/doctor/<c>/order-test", methods=["POST"])
@need("doctor")
def order_test(c):
    a = mine_appt(c)
    if a["status"] == "deceased": flash("Patient is recorded as deceased. New orders are blocked."); return redirect("/doctor")
    t = q("SELECT * FROM lab_tests WHERE name=?", (request.form.get("test"),), one=True)
    if not t: flash("Unknown test.")
    else:
        b = code("SM-", 6); q("INSERT INTO samples(appt_id,barcode,test,status,category,ts) VALUES(?,?,?,?,?,?)", (a["id"], b, t["name"], "Ordered", t["category"], ts()), commit=True)
        audit(who(), "TEST_ORDERED", f"{b}:{t['name']} for {c}"); flash("Test ordered. The lab will collect the sample.")
    return redirect(f"/doctor/{c}")

def mine_appt(c):
    a = appt_row(c)
    if not a or (session["role"] == "doctor" and a["doctor_id"] != session["uid"]): abort(404)
    return a

@app.route("/doctor/<c>", methods=["GET", "POST"])
@need("doctor")
def note(c):
    a = mine_appt(c)
    if request.method == "POST":
        f = request.form; n = {k: f.get(k, "").strip() for k in ("diagnosis", "meds", "do_text", "avoid_text", "care", "followup")}
        fd = f.get("followup_date", "").strip()
        try: datetime.strptime(fd, "%Y-%m-%d")
        except ValueError: fd = ""
        if fd: n["followup"] = fd + (" - " + n["followup"] if n["followup"] else "")  # the date is also part of the patient's plain-language advice
        known = {t["name"] for t in q("SELECT name FROM lab_tests")}; adv = [t for t in f.getlist("tests") if t in known]
        s = simplify(n)
        if adv: s += "\n\nजाँच / Tests advised: " + ", ".join(adv)
        q("INSERT INTO notes(appt_id,diagnosis,meds,do_text,avoid_text,care,followup,simplified,approved,followup_date,tests_advised) VALUES(?,?,?,?,?,?,?,?,0,?,?) "
          "ON CONFLICT(appt_id) DO UPDATE SET diagnosis=excluded.diagnosis,meds=excluded.meds,do_text=excluded.do_text,avoid_text=excluded.avoid_text,"
          "care=excluded.care,followup=excluded.followup,simplified=excluded.simplified,approved=0,followup_date=excluded.followup_date,tests_advised=excluded.tests_advised",
          (a["id"], n["diagnosis"], n["meds"], n["do_text"], n["avoid_text"], n["care"], n["followup"], s, fd or None, "\n".join(adv) or None), commit=True)
        audit(who(), "NOTE_SAVED", c)
        for w in rx_risks(a, n["meds"], n["diagnosis"]): flash("Medicine safety warning: " + w)  # doctor decides; nothing is blocked here
        return redirect(f"/doctor/{c}")
    return render_template("note.html", a=a, n=q("SELECT * FROM notes WHERE appt_id=?", (a["id"],), one=True), tests=q("SELECT name,category FROM lab_tests ORDER BY category,name"), orders=q("SELECT * FROM samples WHERE appt_id=?", (a["id"],)))

@app.route("/doctor/<c>/approve", methods=["POST"])
@need("doctor")
def approve(c):
    a = mine_appt(c)
    q("UPDATE notes SET approved=1,recalled=0 WHERE appt_id=?", (a["id"],), commit=True); q("UPDATE appts SET status='seen' WHERE id=? AND kind='OPD'", (a["id"],), commit=True)
    event(a["id"], "OPD"); audit(who(), "NOTE_APPROVED", c); on_note_approved(a)
    flash("Approved. Patient can now see the advice, the pharmacy can see the prescription and the lab can see the tests."); return redirect("/doctor")

@app.route("/doctor/<c>/recall", methods=["POST"])
@need("doctor")
def recall_rx(c):
    """Doctor withdraws an approved prescription (wrong drug/dose, or doctor ID misuse). Pharmacy stops, patient is alerted, everything is audited."""
    a = mine_appt(c); reason = request.form.get("reason", "").strip()[:300]
    n = q("SELECT approved FROM notes WHERE appt_id=?", (a["id"],), one=True)
    if not n or not n["approved"]: flash("Only an approved prescription can be recalled."); return redirect(f"/doctor/{c}")
    if len(reason) < 3: flash("Please write the reason for recalling (needed for the audit log)."); return redirect(f"/doctor/{c}")
    given = [d["name"] for d in q("SELECT name FROM dispensed WHERE appt_id=?", (a["id"],))]
    q("UPDATE notes SET approved=0,recalled=1,recall_reason=?,recall_by=?,recall_ts=?,flagged=0 WHERE appt_id=?", (reason, who(), ts(), a["id"]), commit=True)
    audit(who(), "RX_RECALLED", f"{c}: {reason}" + (f" (already given: {', '.join(given)})" if given else ""))
    new_alert(a["id"], "RX_RECALLED", "critical" if given else "warning", f"{a['pname']} ({c}): prescription RECALLED by {who()}. Reason: {reason}." + (f" Already handed over: {', '.join(given)}. Contact the patient." if given else ""),
              [f"{who()} recalled the prescription: {reason}", "Pharmacy cannot dispense it any more", "Patient has been told" + (" (some medicines were already given)" if given else "")])
    flash("Prescription recalled. The pharmacy can no longer dispense it and the patient has been alerted. Edit it and approve again if a corrected one is needed."); return redirect(f"/doctor/{c}")

@app.route("/doctor/<c>/confirm-rx", methods=["POST"])
@need("doctor")
def confirm_rx(c):
    """Doctor confirms 'yes, I wrote this' after the pharmacist flagged the prescription. Clears the flag."""
    a = mine_appt(c)
    n = q("SELECT flagged FROM notes WHERE appt_id=?", (a["id"],), one=True)
    if not n or not n["flagged"]: flash("This prescription is not flagged."); return redirect(f"/doctor/{c}")
    q("UPDATE notes SET flagged=0 WHERE appt_id=?", (a["id"],), commit=True)
    for al in q("SELECT id FROM alerts WHERE appt_id=? AND kind='RX_FLAGGED' AND status IN ('open','escalated','acknowledged')", (a["id"],)):
        q("UPDATE alerts SET status='closed' WHERE id=?", (al["id"],), commit=True); trace_add(al["id"], f"Confirmed genuine by {who()}")
    audit(who(), "RX_CONFIRMED", c); patient_notice(a["id"], f"The pharmacy double-check is done: {who()} confirmed your prescription for visit {c}. You can collect your medicines.", "dispense")
    flash("Confirmed. The pharmacy can dispense now."); return redirect(f"/doctor/{c}")

# ---- lab ----
@app.route("/lab")
@need("lab")
def lab():
    groups = {}
    for r in q("SELECT s.*,a.code FROM samples s JOIN appts a ON a.id=s.appt_id ORDER BY s.id DESC"): groups.setdefault(r["category"] or "Other", []).append(r)
    return render_template("lab.html", groups=groups, sts=SAMPLE_STATUS, tests=q("SELECT name FROM lab_tests ORDER BY name"), pending=sum(1 for g in groups.values() for r in g if r["status"] == "Ordered"))

@app.route("/lab/new", methods=["POST"])
@need("lab")
def lab_new():
    a = appt_row(request.form["code"].strip().upper())
    if not a: flash("Appointment not found."); return redirect("/lab")
    b = code("SM-", 6); tn = request.form["test"].strip(); tr = q("SELECT category FROM lab_tests WHERE name=?", (tn,), one=True)
    q("INSERT INTO samples(appt_id,barcode,test,status,category,ts) VALUES(?,?,?,?,?,?)", (a["id"], b, tn, "Sample collected", tr["category"] if tr else "Other", ts()), commit=True)
    event(a["id"], "Lab"); audit(who(), "SAMPLE_NEW", f"{b} for {a['code']}"); flash(f"Sample {b} created."); return redirect("/lab")

@app.route("/lab/update/<int:sid>", methods=["POST"])
@need("lab")
def lab_update(sid):
    st, rep = request.form["status"], request.form.get("report", "").strip()
    if st not in SAMPLE_STATUS or (st == SAMPLE_STATUS[-1] and not rep): flash("Enter report text for 'Report ready'."); return redirect("/lab")
    q("UPDATE samples SET status=?,report=?,ts=? WHERE id=?", (st, rep or None, ts(), sid), commit=True); audit(who(), "SAMPLE_UPDATE", f"{sid}:{st}"); return redirect("/lab")

# ---- pharmacy ----
@app.route("/pharmacy", methods=["GET", "POST"])
@need("pharmacy")
def pharmacy():
    res = None
    if request.method == "POST":
        b = request.form["batch"].strip().upper(); m = q("SELECT * FROM meds WHERE batch=?", (b,), one=True)
        if not m: res = dict(level="UNKNOWN", color="#8a948d", msg="Batch not in system. Do not dispense until verified.")
        else:
            days = (datetime.strptime(m["expiry"], "%Y-%m-%d").date() - now().date()).days
            res = (dict(level="EXPIRED", color="#d9534f", msg=f"{m['name']} expired {-days} days ago. Do not dispense.") if days < 0 else
                   dict(level="NEAR EXPIRY", color="#8a948d", msg=f"{m['name']} expires in {days} days. Pharmacist to decide.") if days <= 30 else
                   dict(level="OK", color="#1b9e5a", msg=f"{m['name']}, valid for {days} more days."))
        audit(who(), "BATCH_CHECK", f"{b}:{res['level']}")
    queue = q("SELECT a.id,a.code,COALESCE(pt.name,p.name) pname,n.meds,n.flagged,n.flag_reason,n.flag_by,n.flag_ts FROM notes n JOIN appts a ON a.id=n.appt_id LEFT JOIN users p ON p.id=a.patient_id LEFT JOIN patients pt ON pt.id=a.pid WHERE n.approved=1 AND COALESCE(n.dispensed,0)=0 ORDER BY a.id DESC")
    return render_template("pharmacy.html", flag_reasons=FLAG_REASONS, res=res, queue=queue, stock=q("SELECT * FROM meds ORDER BY name,expiry"), today=now().date().isoformat())

FLAG_REASONS = ["Need to confirm with the doctor", "Prescription looks wrong or unusual", "Doctor says he/she did not write this", "Other"]

@app.route("/pharmacy/flag", methods=["POST"])
@need("pharmacy")
def flag_rx():
    """Pharmacist pauses dispensing and asks the prescribing doctor to confirm. Doctor + nurse see a critical alert; patient is told calmly."""
    a = appt_row(request.form.get("code", "").strip().upper())
    n = q("SELECT approved FROM notes WHERE appt_id=?", (a["id"],), one=True) if a else None
    if not a or not n or not n["approved"]: flash("No approved prescription found for this code."); return redirect("/pharmacy")
    why = request.form.get("reason", ""); why = why if why in FLAG_REASONS else "Other"; extra = request.form.get("note", "").strip()[:200]; full = why + (f": {extra}" if extra else "")
    q("UPDATE notes SET flagged=1,flag_reason=?,flag_by=?,flag_ts=? WHERE appt_id=?", (full, who(), ts(), a["id"]), commit=True)
    audit(who(), "RX_FLAGGED", f"{a['code']}: {full}")
    new_alert(a["id"], "RX_FLAGGED", "critical", f"{a['pname']} ({a['code']}): pharmacy FLAGGED the prescription of {a['doctor']}. Reason: {full}. Dispensing is paused until the doctor confirms or recalls it.",
              [f"{who()} (pharmacy) flagged it: {full}", "Dispensing paused", f"{a['doctor']} must confirm 'I wrote this' or recall it (open the visit {a['code']})"])
    flash("Flagged. Dispensing is paused and the doctor has been alerted."); return redirect("/pharmacy")

@app.route("/pharmacy/dispense/<int:aid>", methods=["POST"])
@need("pharmacy")
def dispense(aid):
    _r = q("SELECT status FROM appts WHERE id=?", (aid,), one=True)
    if _r and _r["status"] == "deceased": flash("Patient is recorded as deceased. Dispensing is blocked."); return redirect("/pharmacy")
    _f = q("SELECT approved,flagged FROM notes WHERE appt_id=?", (aid,), one=True)
    if _f and _f["flagged"]: flash("This prescription is FLAGGED. Wait for the doctor to confirm it."); return redirect("/pharmacy")
    if not q("SELECT 1 FROM dispensed WHERE appt_id=?", (aid,), one=True): flash("Verify at least one medicine batch first (Verified dispensing)."); return redirect("/pharmacy")
    if not _f or not _f["approved"]: flash("No approved prescription (it may have been recalled)."); return redirect("/pharmacy")
    q("UPDATE notes SET dispensed=1 WHERE appt_id=?", (aid,), commit=True); audit(who(), "DISPENSED", str(aid)); patient_notice(aid, "All medicines for your visit are marked as handed over by the pharmacy.", "dispense"); flash("Marked as dispensed."); return redirect("/pharmacy")

@app.route("/pharmacy/stock", methods=["POST"])
@need("pharmacy")
def set_stock():
    try: n = int(request.form["stock"]); assert n >= 0
    except (ValueError, AssertionError, KeyError): flash("Enter a valid stock number."); return redirect("/pharmacy")
    q("UPDATE meds SET stock=? WHERE batch=?", (n, request.form["batch"]), commit=True); audit(who(), "STOCK", f"{request.form['batch']}={n}"); flash("Stock updated."); return redirect("/pharmacy")

# ---- admin ----
@app.route("/admin")
@need("admin")
def admin():
    td = now().date().isoformat(); stuck = []
    for r in q("SELECT a.code,e.cp,MAX(e.ts) t FROM appts a JOIN events e ON e.appt_id=a.id WHERE a.date=? GROUP BY a.id", (td,)):
        m = int((now() - datetime.strptime(r["t"], FMT)).total_seconds() // 60)
        if r["cp"] != "Discharge" and m >= STUCK_MIN: stuck.append(dict(code=r["code"], cp=r["cp"], mins=m))
    tot = q("SELECT COUNT(*) booked,COALESCE(SUM(status='arrived'),0) arrived,COALESCE(SUM(status='seen'),0) seen FROM appts WHERE date=? AND status!='cancelled'", (td,), one=True)
    ok, bad = verify_chain()
    reg = dict(total=q("SELECT COUNT(*) n FROM patients WHERE active=1", one=True)["n"], new_today=q("SELECT COUNT(*) n FROM patients WHERE created LIKE ?", (td + "%",), one=True)["n"],
               online=q("SELECT COUNT(*) n FROM appts WHERE date=? AND kind='OPD' AND status!='cancelled' AND COALESCE(src,'online')='online'", (td,), one=True)["n"],
               walkin=q("SELECT COUNT(*) n FROM appts WHERE date=? AND kind='OPD' AND src='walk-in'", (td,), one=True)["n"],
               prio=q("SELECT COUNT(*) n FROM appts WHERE date=? AND prio=1 AND status!='cancelled'", (td,), one=True)["n"],
               by_cat=[[r["c"], r["n"]] for r in q("SELECT COALESCE(category,'General') c,COUNT(*) n FROM patients WHERE active=1 GROUP BY c ORDER BY n DESC")],
               rating=q("SELECT ROUND(AVG(rating),1) r,COUNT(*) n FROM feedback", one=True), sms=q("SELECT COUNT(*) n FROM notifications", one=True)["n"])
    return render_template("admin.html", reg=reg, tot=tot, avg_wait=avg_wait(), stuck=stuck, mins=STUCK_MIN, ok=ok, bad=bad, logs=q("SELECT * FROM audit ORDER BY id DESC LIMIT 20"),
        by_dept=[[r["dept"], r["n"]] for r in q("SELECT dept,COUNT(*) n FROM appts WHERE status!='cancelled' GROUP BY dept")],
        funnel=[[cp, q("SELECT COUNT(DISTINCT appt_id) n FROM events WHERE cp=?", (cp,), one=True)["n"]] for cp in CPS],
        docs=q("SELECT name,dept,phone FROM users WHERE role='doctor'"), meds=q("SELECT * FROM meds ORDER BY expiry"), ins=insights())

@app.route("/admin/doctor", methods=["POST"])
@need("admin")
def add_doctor():
    f = request.form; n, d, p, pw = (f[k].strip() for k in ("name", "dept", "phone", "pw"))
    if not n or not d or not (p.isdigit() and len(p) == 10) or len(pw) < 6 or q("SELECT 1 FROM users WHERE phone=?", (p,), one=True): flash("Check details (unique 10-digit phone, password 6+).")
    else: q("INSERT INTO users(name,phone,role,pw,dept) VALUES(?,?,?,?,?)", (n, p, "doctor", gph(pw), d), commit=True); audit(who(), "ADD_DOCTOR", f"{n}/{d}"); flash("Doctor added.")
    return redirect("/admin")

@app.route("/admin/med", methods=["POST"])
@need("admin")
def add_med():
    f = request.form; b = f["batch"].strip().upper()
    try: datetime.strptime(f["expiry"], "%Y-%m-%d"); good = bool(b and f["name"].strip()) and not q("SELECT 1 FROM meds WHERE batch=?", (b,), one=True)
    except ValueError: good = False
    if not good: flash("Invalid or duplicate batch.")
    else:
        try: st = max(int(f.get("stock") or 0), 0)
        except ValueError: st = 0
        q("INSERT INTO meds(batch,name,expiry,stock,category) VALUES(?,?,?,?,?)", (b, f["name"].strip(), f["expiry"], st, (f.get("category") or "General").strip()), commit=True); audit(who(), "ADD_BATCH", b); flash("Batch added.")
    return redirect(request.referrer and request.referrer.startswith(request.host_url) and request.referrer.replace(request.host_url.rstrip("/"), "") or "/admin")

# ---- availability, public pages, i18n, errors ----
def opd_open(): n = now(); return n.weekday() < 6 and 8 <= n.hour < 16

def set_avail(did, status, note=""):
    if status not in ("available", "break", "leave"): status = "available"
    q("INSERT INTO doctor_avail(doctor_id,status,note) VALUES(?,?,?) ON CONFLICT(doctor_id) DO UPDATE SET status=excluded.status,note=excluded.note", (did, status, (note or "")[:80]), commit=True)

def get_docs(dept=None, text=None):
    sql = "SELECT u.id,u.name,u.dept,u.degree,u.designation,u.photo,COALESCE(a.status,'available') st,a.note FROM users u LEFT JOIN doctor_avail a ON a.doctor_id=u.id WHERE u.role='doctor'"; args = []
    if dept: sql += " AND u.dept=?"; args.append(dept)
    if text: sql += " AND (u.name LIKE ? OR u.dept LIKE ?)"; args += [f"%{text}%"] * 2
    op, td, out = opd_open(), now().date().isoformat(), []
    from opd_roster import DAYS_EN
    sched = {}
    for x in q("SELECT doctor_id,wd,room FROM doctor_days ORDER BY wd"): sched.setdefault(x["doctor_id"], []).append((x["wd"], x["room"]))
    for r in q(sql + " ORDER BY u.dept,u.name", args):
        mine = sched.get(r["id"]); wds = sorted({w for w, _ in mine}) if mine else None
        rooms = sorted({rm for _, rm in mine if rm}) if mine else []
        today_off = bool(wds) and now().weekday() not in wds
        k, label, color = (("leave", "On leave", "#d9534f") if r["st"] == "leave" else ("break", "On break", "#8a948d") if r["st"] == "break" else
                           ("closed", "Not in OPD today", "#60727f") if op and today_off else
                           ("avail", "Available now", "#1b9e5a") if op else ("closed", "OPD closed", "#60727f"))
        left = sum(x["state"] == "free" for x in slot_states(r["id"], td)) if op else 0
        nf = next_free(r["id"]); nxt = None
        if nf: nxt = dict(slot=nf["slot"], when="Today" if nf["today"] else "Tomorrow" if nf["date"] == (now().date() + timedelta(days=1)).isoformat() else datetime.strptime(nf["date"], "%Y-%m-%d").strftime("%d-%m-%Y"))
        out.append(dict(id=r["id"], name=r["name"], dept=r["dept"], degree=r["degree"], designation=r["designation"], photo=r["photo"], note=r["note"], code=k, label=label, color=color, left=left, nxt=nxt, days=", ".join(DAYS_EN[w] for w in wds) if wds else "Mon-Sat", room=" / ".join(rooms), ipd="On leave" if r["st"] == "leave" else "On duty", st_key=0 if r["st"] == "available" else 1))
    return out

@app.route("/departments")
def departments():
    g = {}
    for d in get_docs(): x = g.setdefault(d["dept"], dict(dept=d["dept"], n=0, av=0)); x["n"] += 1; x["av"] += d["code"] == "avail"
    return render_template("departments.html", deps=list(g.values()))

@app.route("/department/<name>")
def department(name):
    docs = get_docs(dept=name)
    if not docs: abort(404)
    return render_template("department.html", name=name, docs=docs)

@app.route("/doctors")
def doctors():
    dept, text = request.args.get("dept", ""), request.args.get("q", "").strip()
    return render_template("doctors.html", docs=get_docs(dept or None, text or None), depts=sorted({d["dept"] for d in get_docs()}), dept=dept, text=text)

@app.route("/lab-services")
def lab_services():
    text = request.args.get("q", "").strip(); g = {}
    for t in q("SELECT * FROM lab_tests WHERE name LIKE ? ORDER BY category,name", (f"%{text}%",)): g.setdefault(t["category"], []).append(t)
    return render_template("lab_services.html", groups=g, text=text)

@app.route("/medical-store")
def medical_store():
    text = request.args.get("q", "").strip(); td = now().date().isoformat()
    rows = q("SELECT name,category,SUM(CASE WHEN expiry>=? THEN stock ELSE 0 END) total FROM meds WHERE name LIKE ? GROUP BY name,category ORDER BY name", (td, f"%{text}%"))
    return render_template("medical_store.html", rows=[dict(r, st=("Out of stock" if (r["total"] or 0) <= 0 else "Low stock" if r["total"] < 20 else "In stock")) for r in rows], text=text)

@app.route("/help")
def help_page(): return render_template("help.html", helpline=os.environ.get("HELPLINE", "07662-241655 (Hospital office)"))

@app.route("/report-file/<int:sid>")
def report_file(sid):
    s = q("SELECT s.report_file,a.code FROM samples s JOIN appts a ON a.id=s.appt_id WHERE s.id=?", (sid,), one=True)
    if not s or not s["report_file"]: abort(404)
    a = appt_row(s["code"])
    if not a or not (can_view(a, s["code"]) or session.get("role") in ("nurse", "pharmacy")): abort(403)
    path = os.path.join(LAB_ROOT, os.path.basename(s["report_file"]))
    if not os.path.isfile(path): abort(404)
    r = send_file(path, mimetype="application/pdf", download_name=f"report-{s['code']}-{sid}.pdf"); r.headers["X-Content-Type-Options"] = "nosniff"; r.headers["Content-Security-Policy"] = "sandbox"; r.headers["Cache-Control"] = "private, no-store"; return r

@app.route("/reports")
@need("patient")
def my_reports():
    return render_template("reports.html", rows=q("SELECT s.*,a.code,a.date FROM samples s JOIN appts a ON a.id=s.appt_id WHERE a.patient_id=? ORDER BY s.id DESC", (session["uid"],)))

@app.route("/admin/manage")
@need("admin")
def manage(): return render_template("manage.html", docs=get_docs(), tests=q("SELECT * FROM lab_tests ORDER BY category,name"))

@app.route("/admin/availability/<int:did>", methods=["POST"])
@need("admin")
def admin_avail(did): set_avail(did, request.form.get("status"), request.form.get("note", "")); audit(who(), "AVAIL", str(did)); flash("Availability updated."); return redirect("/admin/manage")

@app.route("/admin/test", methods=["POST"])
@need("admin")
def add_test():
    f = request.form; n = f.get("name", "").strip()
    if not n or q("SELECT 1 FROM lab_tests WHERE name=?", (n,), one=True): flash("Invalid or duplicate test.")
    else: q("INSERT INTO lab_tests(name,category,prep,tat) VALUES(?,?,?,?)", (n, f.get("category", "Other"), f.get("prep", "No special preparation"), (f.get("tat") or "-")[:30]), commit=True); audit(who(), "ADD_TEST", n); flash("Test added.")
    return redirect("/admin/manage")

# ---- AI layer: assistant, workflow-delay prediction, load forecast ----
def _mins(a, b): return (datetime.strptime(b, FMT) - datetime.strptime(a, FMT)).total_seconds() / 60
def insights():
    dw, prev = {}, None
    for e in q("SELECT appt_id,cp,ts FROM events ORDER BY appt_id,id"):
        if prev and prev["appt_id"] == e["appt_id"]: dw.setdefault(prev["cp"], []).append(_mins(prev["ts"], e["ts"]))
        prev = e
    avg = {cp: round(sum(v) / len(v), 1) for cp, v in dw.items()}; risk = []
    for r in q("SELECT a.code,e.cp,MAX(e.ts) t FROM appts a JOIN events e ON e.appt_id=a.id WHERE a.date=? GROUP BY a.id", (now().date().isoformat(),)):
        m = (now() - datetime.strptime(r["t"], FMT)).total_seconds() / 60; base = avg.get(r["cp"]) or STUCK_MIN / 2
        if r["cp"] != "Discharge" and m > 5 and m > 1.25 * base: risk.append(dict(code=r["code"], cp=r["cp"], mins=int(m), base=round(base), level="High" if m > 2 * base else "Watch"))
    pend = [dict(code=r["code"], test=r["test"], mins=int(_mins(r["ts"], ts()))) for r in q("SELECT s.test,s.ts,a.code FROM samples s JOIN appts a ON a.id=s.appt_id WHERE s.status='Ordered'") if _mins(r["ts"], ts()) >= STUCK_MIN]
    d = now().date() + timedelta(days=1)
    while d.weekday() == 6: d += timedelta(days=1)
    hist = [r["n"] for r in q("SELECT COUNT(*) n FROM appts WHERE status!='cancelled' AND date<? GROUP BY date", (now().date().isoformat(),)) if r["n"]]
    return dict(avg=avg, risk=sorted(risk, key=lambda x: -x["mins"]), pend=pend, day=d.strftime("%A %d %b"), forecast=round(sum(hist) / len(hist)) if hist else None, days=len(hist))

@app.route("/assistant")
def assistant(): return render_template("assistant.html")

@app.route("/api/ask", methods=["POST"])
def api_ask(): return jsonify(ai_answer(request.form.get("q", "")[:300], red_flag, session.get("lang", "en")))

@app.route("/about")
def about(): return render_template("about.html")

@app.route("/lang/<l>")
def set_lang(l):
    session["lang"] = l if l in ("en", "hi") else "en"; ref = request.referrer or ""
    return redirect(ref if ref.startswith(request.host_url) else "/")

@app.context_processor
def inject_lang(): return dict(lang=session.get("lang", "en"), hi_map=HI if session.get("lang") == "hi" else {})

_SPLIT, _TEXT, _ATTR = re.compile(r"(<script.*?</script>|<style.*?</style>)", re.S), re.compile(r">([^<>]+)<"), re.compile(r'(placeholder|title)="([^"]*)"')
PAT = []  # (regex, replacement) phrase patterns for text that mixes fixed words with data (dates, bed numbers); filled by ward.py
def _t(m):
    raw = m.group(1); k = raw.strip()
    if not k: return m.group(0)
    if k in HI: return ">" + raw.replace(k, HI[k], 1) + "<"
    if PAT and re.search(r"[A-Za-z]{2,}", re.sub(r"&\w+;", "", k)) and not re.search(r"[\u0900-\u097f]", k):
        o = k
        for rx, rp in PAT: o = rx.sub(rp, o)
        if o != k: return ">" + raw.replace(k, o, 1) + "<"
    return m.group(0)
def tr_html(h):
    parts = _SPLIT.split(h)
    for i in range(0, len(parts), 2): parts[i] = _ATTR.sub(lambda m: f'{m.group(1)}="{HI.get(m.group(2), m.group(2))}"', _TEXT.sub(_t, parts[i]))
    return "".join(parts)

@app.after_request
def translate(r):
    if session.get("lang") == "hi" and not request.path.startswith("/app/") and r.mimetype == "text/html" and not r.direct_passthrough: r.set_data(tr_html(r.get_data(as_text=True)))
    return r

@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(500)
def err(e):
    code = getattr(e, "code", 500) or 500
    role = session.get("role")
    title = {400: "Session expired or form out of date", 403: "Access denied", 404: "Page not found"}.get(code, "Something went wrong")
    msg = {400: "Please go back, reload the page and try again. If you were logged out, log in again.",
           403: "Please log in with the correct account to open this page.", 404: "This page does not exist."}.get(code, "Something went wrong. Please go back and try again.")
    if code == 403 and role and role != "patient": msg = f"You are logged in as {role}, but this page is for patients. Log out and continue as a patient."
    if code == 403 and role == "patient": msg = "This page is not available for your account."
    return render_template("error.html", code=code, title=title, msg=msg, role=role), code

@app.route("/beds")
def beds_page(): return render_template("beds.html")

from api import init_api
init_api(app, globals())  # JSON REST API (/api/v1) used by the React frontend
init()
import safety; safety.register(globals())  # patient-safety layer: vitals, alerts, verified lab/dispensing, summary
import demo; demo.register(globals())  # judge demo console (/demo) + alert feed
import ward; ward.register(globals())  # blood bank, IPD care team, death record + signed certificate
import hospital_map; hospital_map.register(globals())  # indoor hospital map + wayfinding (/navigate)
import registration; registration.register(globals())  # patient registration, family profiles, smart booking, walk-in, slips, reschedule, notifications
import flow; flow.register(globals())  # patient journey: OTP start page, welcome home, registration at first booking, history, records
import idverify; idverify.register(globals())  # Aadhaar / Ayushman document check (/verify, /admin/verify)
import tour; tour.register(globals())  # workflow page, judge tour, role switcher
import staffauth; staffauth.register(globals())  # staff ID-card login: phone + password + SGMH ID card, lockout, revoke
import ipd_care; ipd_care.register(globals())  # doctor refer-to-admit, emergency admit, IPD chart, discharge summary, IPD board
import ipd_mar; ipd_mar.register(globals())  # nurse medicine record (MAR), late-dose alerts, patient/family A-to-Z stay view
import wardduty; wardduty.register(globals())  # ward duty roster, ward-wise alerts, auto care team, ward live view
import ease; ease.register(globals())  # free-service notice, all-services grid, Hindi first, bigger text, voice input
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
