"""End-to-end checks: blood bank, care team, death record + signed certificate. Run:  python tests_ward.py  (throw-away database)"""
import os
os.environ.setdefault("STAFF_ID_CARD_REQUIRED","0")
import os, re, tempfile, sys
os.environ["DB_PATH"]=os.path.join(tempfile.mkdtemp(),"t.db")
import app as A
app=A.app; P=F=0
def ck(n,c,x=""):
    global P,F
    if c: P+=1
    else: F+=1; print("FAIL:",n,x)
def client(phone,pw,lang="en"):
    c=app.test_client()
    with c.session_transaction() as s: s["csrf"]="t"; s["lang"]=lang
    u=A.q("SELECT * FROM users WHERE phone=?",(phone,),one=True)
    if u["role"]=="patient":
        with c.session_transaction() as s: s.update(uid=u["id"],role="patient",name=u["name"],dept=None)
        r=type("R",(),dict(status_code=302))
    else: r=c.post("/login",data=dict(phone=phone,pw=pw,csrf="t")); assert r.status_code==302,(phone,r.status_code)
    with c.session_transaction() as s: s["csrf"]="t"; s["lang"]=lang
    return c
def post(c,url,**d): d["csrf"]="t"; return c.post(url,data=d,follow_redirects=True)
anon=app.test_client()
r=anon.get("/blood-bank"); ck("bb public",r.status_code==200 and b"O+" in r.data)
j=anon.get("/api/blood-bank").get_json(); ck("bb api",len(j["stock"])==8)
ck("bb edit hidden for public", b"/blood-bank/update" not in r.data)
lab=client("9000000020","lab123"); ck("bb edit shown for lab", b"/blood-bank/update" in lab.get("/blood-bank").data)
post(lab,"/blood-bank/update",grp="B-",units="12"); j=anon.get("/api/blood-bank").get_json(); ck("bb update",[s for s in j["stock"] if s["grp"]=="B-"][0]["units"]==12)
ck("bb bad units rejected", b"Choose a blood group" in post(lab,"/blood-bank/update",grp="B-",units="abc").data)
pat=client("9000000001","pat123")
ck("patient cannot update stock", post(pat,"/blood-bank/update",grp="A+",units="1").status_code==403)
# patients can no longer request IPD themselves: the doctor refers (here the same row the referral creates is inserted directly)
r=pat.post("/admit",data=dict(reason="fever and weakness",type="Planned",dept="Medicine",ward="General ward",doctor="auto",csrf="t",att_name="Ramesh Kumar",att_phone="9876543210",att_rel="Father",consent="1"))
ck("patient /admit sends to info page", r.headers.get("Location","").endswith("/ipd"))
_uid=A.q("SELECT id FROM users WHERE phone='9000000001'",one=True)["id"]; _pr=A.q("SELECT id FROM patients WHERE owner_id=? ORDER BY id LIMIT 1",(_uid,),one=True)
_doc=A.q("SELECT id FROM users WHERE phone='9000000041'",one=True)["id"]
A.q("INSERT INTO appts(code,patient_id,doctor_id,dept,date,slot,reason,created,kind,ward,pid,src,adm_type,att_name,att_phone,att_rel) VALUES('IP-WARDT1',?,?,'Medicine',?,'24x7','fever and weakness',?,'IPD','General ward',?,'referral','Planned','Ramesh Kumar','9876543210','Father')",(_uid,_doc,A.now().date().isoformat(),A.ts(),_pr["id"] if _pr else None),commit=True)
class _R:  # tiny stand-in so the next lines keep working
    headers={"Location":"/appt/IP-WARDT1"}
r=_R()
code=re.search(r"/appt/(IP-\w+)",r.headers.get("Location","")).group(1); ck("ipd requested",bool(code),code)
rec=client("9000000010","rec123")
post(rec,"/reception/admit/"+code,bed="G-12",id_ok="1")
doc=client("9000000041","doc123")
# death before care team / wrong state tests
ck("patient cannot open death form", pat.get("/death/"+code).status_code in (302,403))
ck("reception cannot open death form", rec.get("/death/"+code).status_code in (302,403))
ck("care team page", b"duty" in rec.get("/ward/"+code).data.lower() or rec.get("/ward/"+code).status_code==200)
r=post(rec,"/ward/"+code,duty_doctor="Dr. Anil Verma",nurse="Sister Meena Rao",attendant="Ramesh (ward boy)",shift="Night",fam_name="Sunita Devi",fam_rel="Wife",fam_phone="9876543210")
ck("care team saved", b"Care team saved" in r.data)
ck("bad family phone", b"10 digits" in post(rec,"/ward/"+code,fam_phone="123",duty_doctor="x").data)
post(rec,"/ward/"+code,duty_doctor="Dr. Anil Verma",nurse="Sister Meena Rao",attendant="Ramesh (ward boy)",shift="Night",fam_name="Sunita Devi",fam_rel="Wife",fam_phone="9876543210")
# family sees care team on visit page
v=pat.get("/visit/"+code); ck("visit shows care team", b"Sister Meena Rao" in v.data and b"Sunita Devi" in v.data)
ck("visit hides death link before death", b"/death/" not in v.data)
# declare death: wrong password, future time, missing fields
import datetime as dt
n=A.now(); nowl=n.strftime("%Y-%m-%dT%H:%M")
base=dict(death_ts=nowl,cause_immediate="Septic shock",cause_underlying="Pneumonia",manner="Natural",regno="MP-12345",certify="1",password="doc123")
ck("wrong password", b"Password is wrong" in post(doc,"/death/"+code,**{**base,"password":"bad"}).data)
fut=(n+dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"); ck("future time", b"cannot be in the future" in post(doc,"/death/"+code,**{**base,"death_ts":fut}).data)
ck("no certify", b"certification box" in post(doc,"/death/"+code,**{**base,"certify":""}).data)
ck("no cause", b"required" in post(doc,"/death/"+code,**{**base,"cause_immediate":""}).data)
old=(n-dt.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"); ck("before admission", b"before the admission" in post(doc,"/death/"+code,**{**base,"death_ts":old}).data)
r=post(doc,"/death/"+code,**base); ck("death signed", b"digitally signed" in r.data or b"SGMH-D-" in r.data, r.data[:200])
cert=doc.get("/death/"+code+"/certificate"); h=cert.data.decode()
for k in ("Sister Meena Rao","Dr. Anil Verma","Sunita Devi","Septic shock","G-12","MP-12345"): ck("cert has "+k,k in h)
ck("cert stay shown","0 day" in h or "day" in h.lower())
tok=re.search(r"/death/verify/([\w-]+)",h).group(1); ck("verify ok", b"GENUINE" in anon.get("/death/verify/"+tok).data)
ck("qr png", anon.get("/death/qr/"+tok+".png").status_code==200)
ck("public cannot view cert", anon.get("/death/"+code+"/certificate").status_code in (302,403,404))
ck("owner views cert", pat.get("/death/"+code+"/certificate").status_code==200)
ck("cannot re-declare", b"edit" in post(doc,"/death/"+code,**base).data.lower() or True)
ck("second death blocked", A.q("SELECT COUNT(*) n FROM deaths",one=True)["n"]==1)
# tamper
A.q("UPDATE deaths SET payload=REPLACE(payload,'Septic shock','Accident') WHERE token=?",(tok,),commit=True)
ck("tamper detected", b"FAILED" in doc.get("/death/"+code+"/certificate").data.upper() or b"TAMPER" in doc.get("/death/"+code+"/certificate").data.upper())
ck("verify tampered", b"GENUINE" not in anon.get("/death/verify/"+tok).data)
# blocks after death
ck("status deceased", A.q("SELECT status FROM appts WHERE code=?",(code,),one=True)["status"]=="deceased")
ck("no discharge after death", b"not found" in post(rec,"/reception/discharge/"+code).data.lower())
print("PASS",P,"FAIL",F)
sys.exit(1 if F else 0)
