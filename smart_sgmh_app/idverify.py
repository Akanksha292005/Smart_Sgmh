"""Aadhaar / Ayushman (PM-JAY) card document check.  Patient: /verify   Reception: /admin/verify

WHAT THIS IS: a document check, NOT government e-KYC. Software checks the number format (Aadhaar: 12 digits + Verhoeff checksum), reads the card photo (OCR) to see that the
typed number and the patient's name appear on it, flags a number already used on another profile, then reception staff compare the photo with the person and approve or reject.
It cannot confirm with UIDAI that an Aadhaar is genuine, or with NHA that Ayushman cover is active; that needs official API access.
PRIVACY: full number is never stored or logged (last 4 digits + salted hash only). Photo is re-encoded (EXIF/GPS removed), kept in a private folder, shown only to the owner and
reception, and deleted as soon as staff decide. Max 5 submissions per user per day."""
import os, io, secrets, hashlib
from flask import request, session, render_template, redirect, flash, abort, send_file
from PIL import Image, ImageOps
import idcheck

LABEL = {"aadhaar": "Aadhaar card", "ayushman": "Ayushman (PM-JAY) card"}

def register(ns):
    app, q, db, ts, who, need, audit, sms, pneed = (ns[k] for k in ("app", "q", "db", "ts", "who", "need", "audit", "sms", "pneed"))
    ROOT = os.path.join(os.environ.get("UPLOAD_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")), "ids"); os.makedirs(ROOT, exist_ok=True)
    c = db(); c.execute("""CREATE TABLE IF NOT EXISTS idverify(id INTEGER PRIMARY KEY, pid INT, owner_id INT, doc_type TEXT, masked TEXT, num_hash TEXT, ocr_ran INT, num_found INT, name_score INT,
        dup INT DEFAULT 0, status TEXT, reason TEXT, file TEXT, created TEXT, decided_by TEXT, decided_ts TEXT)"""); c.commit(); c.close()
    key = app.secret_key if isinstance(app.secret_key, bytes) else str(app.secret_key).encode()
    H = lambda kind, n: hashlib.sha256(key + kind.encode() + n.encode()).hexdigest()
    clip = lambda s, n=200: (s or "").strip()[:n]
    profiles = lambda uid: q("SELECT * FROM patients WHERE owner_id=? AND active=1 ORDER BY (relation='Self') DESC,id", (uid,))   # never creates a profile (UHID is issued at the first booking)

    def idv_types(pid): return [LABEL[r["doc_type"]] for r in q("SELECT DISTINCT doc_type FROM idverify WHERE pid=? AND status='verified'", (pid,))] if pid else []
    def idv_status(uid):
        ps = profiles(uid)
        if not ps: return None
        me = ps[0]; return dict(pid=me["id"], types=idv_types(me["id"]), pending=bool(q("SELECT 1 FROM idverify WHERE pid=? AND status='pending'", (me["id"],), one=True)))
    app.context_processor(lambda: dict(idv_types=idv_types, idv_status=idv_status, idv_pending=lambda: q("SELECT COUNT(*) n FROM idverify WHERE status='pending'", one=True)["n"]))

    @app.route("/verify", methods=["GET", "POST"])
    @pneed
    def verify_me():
        uid = session["uid"]; ps = profiles(uid)
        if not ps: flash("Register first: it happens when you choose your first doctor. Then you can verify your card."); return redirect("/home")
        pid = request.values.get("pid", type=int); me = next((x for x in ps if x["id"] == pid), ps[0])
        if request.method == "POST":
            kind, raw, f = request.form.get("doc_type", ""), request.form.get("number", ""), request.files.get("photo")
            def back(m): flash(m); return redirect(f"/verify?pid={me['id']}")
            if not request.form.get("consent"): return back("Please tick the consent box to continue.")
            if q("SELECT COUNT(*) n FROM idverify WHERE owner_id=? AND created>=?", (uid, ts()[:10]), one=True)["n"] >= 5: return back("Daily limit reached (5 submissions). Try tomorrow or visit the reception.")
            num, msg = idcheck.check_number(kind, raw)
            if not num: return back(msg)
            data = f.read(4_000_001) if f and f.filename else b""
            if not data or len(data) > 4_000_000: return back("Upload a clear photo of the card (JPG or PNG, up to 4 MB).")
            try: im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB"); im.thumbnail((1600, 1600))   # re-encode: strips EXIF / GPS, rejects non-images
            except Exception: return back("That file is not a valid image. Upload a JPG or PNG photo.")
            fn = secrets.token_hex(16) + ".jpg"; path = os.path.join(ROOT, fn); im.save(path, "JPEG", quality=85)
            text = idcheck.ocr_text(path); nf = idcheck.number_found(num, text); sc = idcheck.name_score(me["name"], text); h = H(kind, num)
            dup = 1 if q("SELECT 1 FROM idverify WHERE num_hash=? AND pid<>? AND status IN ('pending','verified')", (h, me["id"]), one=True) else 0
            q("INSERT INTO idverify(pid,owner_id,doc_type,masked,num_hash,ocr_ran,num_found,name_score,dup,status,file,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              (me["id"], uid, kind, idcheck.mask(num), h, 0 if text is None else 1, None if nf is None else int(nf), sc, dup, "pending", fn, ts()), commit=True)
            audit(who(), "ID_SUBMIT", f"{kind} {idcheck.mask(num)}"); return back("Submitted. Reception will check it against your photo ID. You can also show the card at the counter.")
        return render_template("verify.html", me=me, profs=ps, rows=q("SELECT * FROM idverify WHERE pid=? ORDER BY id DESC LIMIT 10", (me["id"],)), label=LABEL)

    @app.route("/verify/file/<int:i>")
    def verify_file(i):
        r = q("SELECT * FROM idverify WHERE id=?", (i,), one=True); role = session.get("role")
        if not r or not r["file"] or role not in ("patient", "reception", "admin") or (role == "patient" and r["owner_id"] != session["uid"]): abort(404)
        return send_file(os.path.join(ROOT, r["file"]), mimetype="image/jpeg", max_age=0)

    @app.route("/admin/verify")
    @need("reception")
    def verify_queue():
        rows = q("SELECT v.*,p.name pname,p.uhid,p.phone FROM idverify v JOIN patients p ON p.id=v.pid WHERE v.status='pending' ORDER BY v.id")
        done = q("SELECT v.*,p.name pname,p.uhid FROM idverify v JOIN patients p ON p.id=v.pid WHERE v.status<>'pending' ORDER BY v.id DESC LIMIT 15")
        return render_template("verify_admin.html", rows=rows, done=done, label=LABEL)

    @app.route("/admin/verify/<int:i>", methods=["POST"])
    @need("reception")
    def verify_decide(i):
        r = q("SELECT * FROM idverify WHERE id=? AND status='pending'", (i,), one=True)
        if not r: abort(404)
        ok = request.form.get("decision") == "approve"; reason = clip(request.form.get("reason"))
        if not ok and not reason: flash("Write a short reason for rejecting."); return redirect("/admin/verify")
        if r["file"]:
            try: os.remove(os.path.join(ROOT, r["file"]))
            except OSError: pass
        q("UPDATE idverify SET status=?,reason=?,file=NULL,decided_by=?,decided_ts=? WHERE id=?", ("verified" if ok else "rejected", reason, who(), ts(), i), commit=True)
        audit(who(), "ID_VERIFIED" if ok else "ID_REJECTED", f"id{i} {r['doc_type']} {r['masked']}")
        sms(None, (f"SGMH: your {LABEL[r['doc_type']]} is verified." if ok else f"SGMH: your {LABEL[r['doc_type']]} could not be verified: {reason}"), r["owner_id"]); flash("Approved." if ok else "Rejected."); return redirect("/admin/verify")
