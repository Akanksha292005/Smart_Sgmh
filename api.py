"""REST API (/api/v1) for the React frontend. Reuses the Flask app's DB + business logic; auth = signed bearer token."""
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, jsonify, g, session
from itsdangerous import URLSafeTimedSerializer, BadSignature
from werkzeug.security import check_password_hash

def init_api(app, G):
    bp = Blueprint("api", __name__, url_prefix="/api/v1")
    tok = URLSafeTimedSerializer(app.secret_key)
    q, now, ts, code, event, audit = (G[k] for k in ("q", "now", "ts", "code", "event", "audit"))

    def auth(*roles):
        def deco(f):
            @wraps(f)
            def w(*a, **k):
                try: g.u = tok.loads(request.headers.get("Authorization", "")[7:], max_age=60 * 60 * 12)
                except BadSignature: return jsonify(error="Please log in"), 401
                if roles and g.u["role"] not in roles and g.u["role"] != "admin": return jsonify(error="Forbidden"), 403
                return f(*a, **k)
            return w
        return deco

    @bp.post("/login")
    def login():
        d = request.get_json(silent=True) or {}
        u = q("SELECT * FROM users WHERE phone=?", (d.get("phone", ""),), one=True)
        if not u or not check_password_hash(u["pw"], d.get("password", "")): return jsonify(error="Wrong phone or password"), 401
        user = dict(id=u["id"], name=u["name"], role=u["role"], dept=u["dept"])
        lang = session.get("lang"); session.clear(); session.update(uid=u["id"], role=u["role"], name=u["name"], dept=u["dept"], lang=lang or "en")  # same login works on the staff / IPD pages
        return jsonify(token=tok.dumps(user), user=user)

    @bp.get("/doctors")
    def doctors(): return jsonify(G["get_docs"](dept=request.args.get("dept")))

    @bp.get("/slots")
    def slots():
        return jsonify(G["slot_states"](request.args.get("doctor", type=int), request.args.get("date", "")))

    @bp.get("/suggest")  # ML triage (ml.py) with the keyword matcher as fallback; red-flag rule always wins
    def suggest():
        import ml
        r = request.args.get("reason", ""); rk = ml.rank(r)
        if rk and rk[0]["prob"] < 0.3: rk = []  # too unsure to show
        extra = any(w in r.lower() for w in ("seene me dard", "seene mein dard", "dil ka daura", "heart attack", "saans nahi", "behosh", "unconscious", "fit aa"))
        return jsonify(dept=rk[0]["dept"] if rk else G["suggest"](r), emergency=bool(G["red_flag"](r)) or extra, ranked=rk, model=ml.INFO)

    @bp.post("/book")
    @auth("patient")
    def book():
        d = request.get_json(silent=True) or {}
        reason = (d.get("reason") or "")[:200]
        if G["red_flag"](reason): return jsonify(error=G["EMERG_MSG"], emergency=True), 400
        doc = next((x for x in G["get_docs"]() if x["id"] == d.get("doctor")), None)
        free = [s["slot"] for s in G["slot_states"](d.get("doctor"), d.get("date", "")) if s["state"] == "free"]
        if not doc or doc["code"] == "leave" or d.get("slot") not in free: return jsonify(error="Slot or doctor not available"), 409
        c = code("AP-")
        aid = q("INSERT INTO appts(code,patient_id,doctor_id,dept,date,slot,reason,created,kind) VALUES(?,?,?,?,?,?,?,?,'OPD')",
                (c, g.u["id"], doc["id"], doc["dept"], d["date"], d["slot"], reason, ts()), commit=True)
        q("INSERT INTO events(appt_id,cp,ts,staff) VALUES(?,?,?,?)", (aid, "Registered", ts(), f"patient:{g.u['name']}"), commit=True)
        audit(f"patient:{g.u['name']}", "BOOK", c)
        return jsonify(code=c), 201

    @bp.get("/appointments")
    @auth("patient")
    def mine():
        rows = q("SELECT a.code,a.date,a.slot,a.dept,a.status,d.name doctor FROM appts a JOIN users d ON d.id=a.doctor_id WHERE a.patient_id=? ORDER BY a.date DESC,a.slot", (g.u["id"],))
        return jsonify([dict(r) for r in rows])

    @bp.get("/visit/<c>")
    @auth()
    def visit(c):
        a = G["appt_row"](c)
        if not a: return jsonify(error="Not found"), 404
        if g.u["role"] == "guest" and g.u.get("code") != c: return jsonify(error="Forbidden"), 403
        if g.u["role"] == "patient" and a["patient_id"] != g.u["id"]: return jsonify(error="Forbidden"), 403
        return jsonify(dict(G["vdata"](a), doctor=a["doctor"], date=a["date"], slot=a["slot"], dept=a["dept"], cps=G["CPS"]))

    @bp.post("/ask")
    def ask():
        d = request.get_json(silent=True) or {}
        return jsonify(G["ai_answer"]((d.get("q") or "")[:300], G["red_flag"], d.get("lang", "en")))

    @bp.get("/admin/stats")
    @auth("admin")
    def stats():
        td = now().date().isoformat(); stuck = []
        for r in q("SELECT a.code,e.cp,MAX(e.ts) t FROM appts a JOIN events e ON e.appt_id=a.id WHERE a.date=? GROUP BY a.id", (td,)):
            m = int((now() - datetime.strptime(r["t"], G["FMT"])).total_seconds() // 60)
            if r["cp"] != "Discharge" and m >= G["STUCK_MIN"]: stuck.append(dict(code=r["code"], cp=r["cp"], mins=m))
        tot = q("SELECT COUNT(*) booked,COALESCE(SUM(status='arrived'),0) arrived,COALESCE(SUM(status='seen'),0) seen FROM appts WHERE date=? AND status!='cancelled'", (td,), one=True)
        return jsonify(today=dict(tot), avg_wait=G["avg_wait"](),
            by_dept=[dict(name=r["dept"], value=r["n"]) for r in q("SELECT dept,COUNT(*) n FROM appts WHERE status!='cancelled' GROUP BY dept")],
            funnel=[dict(name=cp, value=q("SELECT COUNT(DISTINCT appt_id) n FROM events WHERE cp=?", (cp,), one=True)["n"]) for cp in G["CPS"]],
            insights=G["insights"](), stuck=stuck, mins=G["STUCK_MIN"], chain_ok=G["verify_chain"]()[0],
            logs=[dict(r) for r in q("SELECT ts,actor,action,detail FROM audit ORDER BY id DESC LIMIT 8")],
            meds=[dict(name=r["name"], batch=r["batch"], stock=r["stock"], expiry=r["expiry"]) for r in q("SELECT * FROM meds ORDER BY expiry")],
            doctors=[dict(name=d["name"], dept=d["dept"], label=d["label"], color=d["color"]) for d in G["get_docs"]()])

    @bp.post("/track")  # family tracking without login: appointment code + last 4 digits of patient phone
    def track():
        d = request.get_json(silent=True) or {}
        a = G["appt_row"]((d.get("code") or "").strip().upper())
        if not a or a["pphone"][-4:] != (d.get("last4") or "").strip(): return jsonify(error="Code and last 4 digits do not match"), 404
        return jsonify(code=a["code"], token=tok.dumps(dict(id=0, name="guest", role="guest", code=a["code"])))

    @bp.get("/lab-services")
    def lab_services():
        t = request.args.get("q", "").strip(); g_ = {}
        for r in q("SELECT name,category,prep,tat FROM lab_tests WHERE name LIKE ? ORDER BY category,name", (f"%{t}%",)): g_.setdefault(r["category"], []).append(dict(r))
        return jsonify(g_)

    @bp.get("/medicines")
    def medicines():
        t = request.args.get("q", "").strip(); td = now().date().isoformat()
        rows = q("SELECT name,category,SUM(CASE WHEN expiry>=? THEN stock ELSE 0 END) total FROM meds WHERE name LIKE ? GROUP BY name,category ORDER BY name", (td, f"%{t}%"))
        return jsonify([dict(name=r["name"], category=r["category"], total=r["total"] or 0, status="Out of stock" if (r["total"] or 0) <= 0 else "Low stock" if r["total"] < 20 else "In stock") for r in rows])

    app.register_blueprint(bp)
