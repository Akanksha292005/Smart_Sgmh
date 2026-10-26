"""v29 checks: roster (weekday slots, rooms), workflow page, judge tour end to end (care team -> death -> certificate -> verify -> tamper)."""
import os
os.environ.setdefault("STAFF_ID_CARD_REQUIRED","0")
import os, re, sys
os.environ.setdefault("DB_PATH", "/tmp/tests_tour.db")
if os.path.exists(os.environ["DB_PATH"]): os.remove(os.environ["DB_PATH"])
import app as A
ok = bad = 0
def check(n, c, extra=""):
    global ok, bad
    if c: ok += 1
    else: bad += 1; print("FAIL", n, extra)
def tok(r): return re.search(r'name="csrf" value="([^"]+)"', r.get_data(as_text=True)).group(1)
c = A.app.test_client()

# --- roster
docs = A.get_docs()
check("roster doctors loaded", len(docs) > 60)
pl = next(d for d in docs if d["dept"] == "Plastic Surgery")
check("plastic surgery only Mon/Thu", pl["days"] == "Mon, Thu" and "Room 3" in pl["room"], pl)
check("off day has no free slots", not any(s["state"] == "free" for s in A.slot_states(pl["id"], "2026-10-20")))  # Tuesday
check("working day has free slots", any(s["state"] == "free" for s in A.slot_states(pl["id"], "2026-10-26")))   # Monday
pe = next(d for d in docs if d["name"] == "Dr. Deepak Dwivedi")
fr = [s["slot"] for s in A.slot_states(pe["id"], "2026-10-30") if s["state"] == "free"]
check("paediatrics hours 8:30-1:30", fr and fr[0] == "08:30" and fr[-1] == "13:30", fr[:2])
m = c.get("/api/map").get_json(); ids = {r["id"] for r in m["rooms"]}
check("map has real ground + first floor rooms", {"ortho", "psy", "eye", "skin", "surg", "reg", "bvk", "dent", "paed", "ent", "obg"} <= ids and {"bb", "path", "er", "icu", "pharm", "radio"} <= ids)
for u in ("/doctors", "/departments", "/navigate", "/department/Plastic%20Surgery"): check("GET " + u, c.get(u).status_code == 200)

# --- workflow + tour pages
check("workflow public", c.get("/workflow").status_code == 200 and "One patient" in c.get("/workflow").get_data(as_text=True))
h = c.get("/lang/hi", headers={"Referer": "http://localhost/workflow"}); w = c.get("/workflow").get_data(as_text=True)
check("workflow in Hindi", "एक मरीज़" in w and "सुरक्षा जाल" in w)
c.get("/lang/en")
t = c.get("/tour"); check("tour page", t.status_code == 200 and "Load story" in t.get_data(as_text=True))
check("tour step needs story", c.get("/tour/go/care").status_code == 302 and "/tour" in c.get("/tour/go/care").headers["Location"])
check("seed needs csrf", c.post("/tour/seed").status_code == 400)
r = c.post("/tour/seed", data=dict(csrf=tok(c.get("/tour")))); check("seed story", r.status_code == 302)
a = A.q("SELECT * FROM appts WHERE code='AP-TOUR1'", one=True); check("story admitted", a and a["status"] == "admitted" and a["kind"] == "IPD")
r = c.post("/tour/seed", data=dict(csrf=tok(c.get("/tour")))); check("re-seed is clean", A.q("SELECT COUNT(*) n FROM appts WHERE code='AP-TOUR1'", one=True)["n"] == 1)

# --- care team (nurse) + family sees it
c.get("/tour/go/care"); pg = c.get("/ward/AP-TOUR1"); check("nurse opens care team", pg.status_code == 200)
c.post("/tour/fill", data=dict(csrf=tok(c.get("/tour"))))
pg = c.get("/ward/AP-TOUR1").get_data(as_text=True); check("care team shows duty doctor, nurse, family attendant", all(x in pg for x in ("Pradeep Nigam", "Meena Tiwari", "Suresh Prasad")))
check("tour step ticks", "tstep done" in c.get("/tour").get_data(as_text=True))
c.get("/tour/as/patient"); fam = c.get("/home").get_data(as_text=True); check("patient home loads", c.get("/home").status_code == 200)

# --- doctor records death
dc = A.app.test_client(); dc.get("/tour/go/death"); frm = dc.get("/death/AP-TOUR1"); check("doctor opens death form", frm.status_code == 200)
base = dict(csrf=tok(frm), death_ts=A.now().strftime("%Y-%m-%dT%H:%M"), cause_immediate="Cardio-respiratory arrest", cause_underlying="Septic shock", manner="Natural", regno="MP-12345", certify="1")
r = dc.post("/death/AP-TOUR1", data={**base, "password": "wrong"}); check("wrong password rejected", A.q("SELECT status FROM appts WHERE code='AP-TOUR1'", one=True)["status"] == "admitted")
r = dc.post("/death/AP-TOUR1", data={**base, "password": "doc123"}); check("death signed", r.status_code == 302 and "certificate" in r.headers["Location"], r.headers.get("Location"))
cert = dc.get("/death/AP-TOUR1/certificate").get_data(as_text=True)
check("certificate has stay days + care team", all(x in cert for x in ("Pradeep Nigam", "Meena Tiwari", "Suresh Prasad")) and re.search(r"3\s*day", cert), cert[:200])
tk = A.q("SELECT token FROM deaths", one=True)["token"]
vp = c.get("/death/verify/" + tk).get_data(as_text=True); check("verify genuine", "GENUINE." in vp and "NOT GENUINE" not in vp.upper())
check("tour verify link", c.get("/tour/go/verify").status_code == 302 and "/death/verify/" in c.get("/tour/go/verify").headers["Location"])
check("after death blocked", A.q("SELECT status FROM appts WHERE code='AP-TOUR1'", one=True)["status"] == "deceased")
A.q("UPDATE deaths SET payload=replace(payload,'Natural','Homicide')", commit=True)
vp = c.get("/death/verify/" + tk).get_data(as_text=True); check("tamper detected", "NOT" in vp.upper() or "TAMPER" in vp.upper() or "FAILED" in vp.upper(), vp[:300])
check("tour ticks death step", "tstep done" in c.get("/tour").get_data(as_text=True))

# --- every role opens its home, tour bar visible, tour off in production
for role in ("patient", "reception", "nurse", "doctor", "lab", "pharmacy", "admin"):
    cc = A.app.test_client(); r = cc.get("/tour/as/" + role); p = cc.get(r.headers["Location"]); check("role " + role, r.status_code == 302 and p.status_code == 200 and "Judge tour" in p.get_data(as_text=True), p.status_code)
os.environ["DEMO_MODE"] = "0"
check("tour off when DEMO_MODE=0", A.app.test_client().get("/tour").status_code == 404 and "Judge tour" not in A.app.test_client().get("/workflow").get_data(as_text=True))
print(f"PASS {ok} FAIL {bad}"); sys.exit(1 if bad else 0)
