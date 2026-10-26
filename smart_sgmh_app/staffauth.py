"""Staff ID-card login for Smart SGMH.

Every staff member (doctor, reception, lab, pharmacy, nurse, admin) gets ONE hospital ID card with a QR code.
A staff login needs all three: phone + password + the SGMH ID card (scan the QR or type the card code).
  * password alone (someone knows or guesses it)      -> login fails
  * somebody else's card with another person's password -> login fails (card is tied to ONE user)
  * a patient account                                   -> cannot use the staff login at all (OTP only)
  * admin revokes / replaces a card                     -> that staff member is signed out on the next click
Only a hash of the card secret is stored. The card code is shown ONCE when the card is issued.
SAMPLE: the physical card is "something you have". It does not prove who is holding it; the hospital desk still has to
hand cards over against a photo ID, and a lost card must be revoked at once (/admin/cards).
Set STAFF_ID_CARD_REQUIRED=0 ONLY for automated tests; the app prints a warning and records it.
"""
import os, io, base64, secrets, sqlite3
from datetime import timedelta
from flask import request, redirect, session, flash, render_template, abort
from werkzeug.security import generate_password_hash as gph, check_password_hash as cph

STAFF_ROLES = ("doctor", "reception", "lab", "pharmacy", "nurse", "admin")
RCODE = {"doctor": "DR", "reception": "RC", "lab": "LB", "pharmacy": "PH", "nurse": "NS", "admin": "AD"}
LOCK_TRIES = int(os.environ.get("STAFF_LOCK_TRIES", 5))
LOCK_MIN = int(os.environ.get("STAFF_LOCK_MIN", 15))
GENERIC = "Login failed. Staff need phone, password and their SGMH ID card."


def required():
    return os.environ.get("STAFF_ID_CARD_REQUIRED", "1") != "0"


def register(ns):
    app, q, db, audit, who, need, now, ts, FMT = (ns[k] for k in ("app", "q", "db", "audit", "who", "need", "now", "ts", "FMT"))

    c = db()
    c.executescript("""CREATE TABLE IF NOT EXISTS staff_cards(id INTEGER PRIMARY KEY,user_id INTEGER UNIQUE,card_no TEXT UNIQUE,secret_hash TEXT,
status TEXT DEFAULT 'active',version INTEGER DEFAULT 1,issued_by TEXT,issued_ts TEXT,last_used TEXT,revoked_ts TEXT);
CREATE TABLE IF NOT EXISTS staff_authfail(k TEXT PRIMARY KEY,n INTEGER DEFAULT 0,until TEXT);""")
    c.commit(); c.close()
    if not required(): print("WARNING: STAFF_ID_CARD_REQUIRED=0 -> staff ID-card check is OFF. Use only for tests.")

    # ---------------------------------------------------------------- cards
    def card_no_for(u): return f"SGMH-{RCODE[u['role']]}-{u['id']:04d}"

    def issue_card(uid, by="system"):
        """Create or REPLACE the card of one staff user. Returns the full card code (shown once, never stored in clear)."""
        u = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
        if not u or u["role"] not in STAFF_ROLES: raise ValueError("not a staff user")
        secret = secrets.token_hex(5).upper(); no = card_no_for(u); h = gph(secret)
        old = q("SELECT version FROM staff_cards WHERE user_id=?", (uid,), one=True)
        if old: q("UPDATE staff_cards SET card_no=?,secret_hash=?,status='active',version=version+1,issued_by=?,issued_ts=?,revoked_ts=NULL WHERE user_id=?", (no, h, by, ts(), uid), commit=True)
        else: q("INSERT INTO staff_cards(user_id,card_no,secret_hash,issued_by,issued_ts) VALUES(?,?,?,?,?)", (uid, no, h, by, ts()), commit=True)
        audit(by, "CARD_REISSUED" if old else "CARD_ISSUED", f"{no} for user {uid}")
        return f"{no}-{secret}"

    def revoke_card(uid, by):
        q("UPDATE staff_cards SET status='revoked',revoked_ts=? WHERE user_id=?", (ts(), uid), commit=True); audit(by, "CARD_REVOKED", f"user {uid}")

    def card_ok(u, text):
        """(ok, reason). The card must exist, be active, belong to THIS user and carry the right secret."""
        text = (text or "").strip().upper()
        if "-" not in text: return False, "BAD_CARD"
        no, secret = text.rsplit("-", 1)
        row = q("SELECT * FROM staff_cards WHERE user_id=?", (u["id"],), one=True)
        if not row: return False, "NO_CARD_ISSUED"
        if row["status"] != "active": return False, "CARD_REVOKED"
        if no != row["card_no"]:
            other = q("SELECT user_id FROM staff_cards WHERE card_no=?", (no,), one=True)
            return False, "CARD_OF_ANOTHER_USER" if other else "BAD_CARD"
        if not cph(row["secret_hash"], secret): return False, "BAD_CARD"
        return True, "OK"

    def card_ver(uid):
        r = q("SELECT version FROM staff_cards WHERE user_id=?", (uid,), one=True); return r["version"] if r else 0

    def card_active(uid, cv=None):
        """Used on every request of a staff session / API token: revoking OR replacing a card signs the old session out at once."""
        if not required(): return True
        r = q("SELECT status,version FROM staff_cards WHERE user_id=?", (uid,), one=True)
        return bool(r and r["status"] == "active" and r["version"] == cv)

    # ---------------------------------------------------------------- lockout (per phone and per IP)
    def locked(k):
        r = q("SELECT until FROM staff_authfail WHERE k=?", (k,), one=True)
        if r and r["until"] and r["until"] > ts(): return int((__import__("datetime").datetime.strptime(r["until"], FMT) - now()).total_seconds() // 60) + 1
        return 0

    def fail(k, limit):
        r = q("SELECT n FROM staff_authfail WHERE k=?", (k,), one=True); n = (r["n"] if r else 0) + 1
        until = (now() + timedelta(minutes=LOCK_MIN)).strftime(FMT) if n >= limit else None
        q("INSERT INTO staff_authfail(k,n,until) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET n=excluded.n,until=excluded.until", (k, 0 if until else n, until), commit=True)
        if until: audit(k, "STAFF_LOGIN_LOCKED", f"{LOCK_MIN} min")

    def attempt(phone, pw, card, ip="?"):
        """The ONE gate for every staff sign-in (web form and REST API).
        Returns dict(ok, kind in staff|patient|fail|locked, msg, user, reason)."""
        phone = (phone or "").strip(); kp, ki = "phone:" + phone, "ip:" + ip
        m = locked(kp) or locked(ki)
        if m: return dict(ok=False, kind="locked", msg=f"Too many failed attempts. Try again in about {m} minutes.", user=None, reason="LOCKED")
        u = q("SELECT * FROM users WHERE phone=?", (phone,), one=True)

        def bad(reason):
            fail(kp, LOCK_TRIES); fail(ki, LOCK_TRIES * 4); audit(f"phone:{phone}", "STAFF_LOGIN_FAILED", f"{reason} ip={ip}")
            return dict(ok=False, kind="fail", msg=GENERIC, user=None, reason=reason)
        if not u or not cph(u["pw"], pw or ""): return bad("BAD_PASSWORD")
        if u["role"] == "patient": return dict(ok=False, kind="patient", msg="Patients log in with an OTP on the start page.", user=u, reason="PATIENT")
        if u["role"] not in STAFF_ROLES: return bad("NOT_STAFF")
        if required():
            ok, why = card_ok(u, card)
            if not ok: return bad(why)
            q("UPDATE staff_cards SET last_used=? WHERE user_id=?", (ts(), u["id"]), commit=True)
        q("DELETE FROM staff_authfail WHERE k IN (?,?)", (kp, ki), commit=True)
        audit(f"{u['role']}:{u['name']}", "STAFF_LOGIN_OK", f"ip={ip}")
        return dict(ok=True, kind="staff", msg="", user=u, reason="OK")

    # ---------------------------------------------------------------- the /login page (replaces the password-only one)
    def login():
        if request.method == "POST":
            r = attempt(request.form.get("phone", ""), request.form.get("pw", ""), request.form.get("card", ""), request.remote_addr or "?")
            if r["kind"] == "patient": flash(r["msg"]); return redirect("/start")
            if not r["ok"]: flash(r["msg"])
            else:
                u = r["user"]; nxt, lang = session.get("next"), session.get("lang")
                session.clear(); session.update(uid=u["id"], role=u["role"], name=u["name"], dept=u["dept"], lang=lang or "en", card=card_no_for(u), cv=card_ver(u["id"]))
                if nxt and nxt.startswith("/") and not nxt.startswith("//") and u["role"] == "admin": return redirect(nxt)
                return redirect({"reception": "/reception", "doctor": "/doctor", "lab": "/lab", "pharmacy": "/pharmacy", "nurse": "/vitals", "admin": "/admin"}[u["role"]])
        return render_template("login.html", card_required=required())
    app.view_functions["login"] = login

    @app.before_request
    def staff_session_guard():
        """A staff session is only alive while its ID card is still active (lost / replaced / revoked cards stop working at once)."""
        role = session.get("role")
        if role in STAFF_ROLES and required():
            r = q("SELECT card_no,status,version FROM staff_cards WHERE user_id=?", (session.get("uid"),), one=True)
            if not r or r["status"] != "active" or r["card_no"] != session.get("card") or r["version"] != session.get("cv"):
                session.clear(); flash("Your ID card is no longer valid. Please sign in again with your current SGMH ID card.")
                return redirect("/login")

    # ---------------------------------------------------------------- printable card + admin pages
    def card_html(u, code):
        import qrcode
        buf = io.BytesIO(); qrcode.make(code, box_size=6, border=2).save(buf, format="PNG")
        qr = base64.b64encode(buf.getvalue()).decode()
        return (f'<div class="idcard"><div class="hd">SANJAY GANDHI MEMORIAL HOSPITAL, REWA<br><small>STAFF ID CARD</small></div>'
                f'<div class="nm">{u["name"]}</div><div class="ro">{u["role"].upper()}{(" &middot; " + u["dept"]) if u["dept"] else ""}</div>'
                f'<img src="data:image/png;base64,{qr}" width="150" height="150" alt="card QR"><div class="cd">{code}</div>'
                f'<div class="ft">Keep this card safe. Never lend it. Lost? Tell the admin at once.</div></div>')
    CARD_CSS = (".idcard{width:300px;border:2px solid #0b3a75;border-radius:12px;padding:12px;text-align:center;font-family:system-ui,sans-serif;display:inline-block;margin:8px;vertical-align:top;background:#fff;color:#111}"
                ".idcard .hd{background:#0b3a75;color:#fff;border-radius:6px;padding:6px;font-size:12px;font-weight:700}.idcard .nm{font-size:18px;font-weight:800;margin-top:8px}"
                ".idcard .ro{font-size:13px;color:#0b3a75;margin-bottom:6px}.idcard .cd{font:700 14px monospace;margin-top:4px;word-break:break-all}.idcard .ft{font-size:10px;color:#666;margin-top:6px}")

    @app.route("/admin/cards")
    @need("admin")
    def cards_page():
        rows = q("SELECT u.id,u.name,u.phone,u.role,u.dept,c.card_no,c.status,c.last_used,c.issued_ts,c.version FROM users u LEFT JOIN staff_cards c ON c.user_id=u.id "
                 "WHERE u.role IN (%s) ORDER BY u.role,u.name" % ",".join("?" * len(STAFF_ROLES)), STAFF_ROLES)
        return render_template("cards.html", rows=rows, required=required())

    @app.route("/admin/cards/issue/<int:uid>", methods=["POST"])
    @need("admin")
    def cards_issue(uid):
        u = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
        if not u or u["role"] not in STAFF_ROLES: abort(404)
        code = issue_card(uid, who())
        return render_template("card_print.html", card=card_html(u, code), css=CARD_CSS, name=u["name"])

    @app.route("/admin/cards/revoke/<int:uid>", methods=["POST"])
    @need("admin")
    def cards_revoke(uid):
        if not q("SELECT 1 FROM staff_cards WHERE user_id=?", (uid,), one=True): abort(404)
        revoke_card(uid, who()); flash("Card revoked. That person is signed out and cannot sign in until a new card is issued."); return redirect("/admin/cards")

    ns.update(card_ver=card_ver, issue_card=issue_card, revoke_card=revoke_card, staff_attempt=attempt, staff_card_active=card_active, card_html=card_html, CARD_CSS=CARD_CSS,
              STAFF_ROLES=STAFF_ROLES, card_no_for=card_no_for)
