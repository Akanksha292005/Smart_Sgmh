"""Indoor hospital map + wayfinding (/navigate, /api/map).
IMPORTANT: the floor layout below is a SAMPLE schematic (which department sits on which floor/room is NOT taken from the hospital).
Replace the numbers in ROOMS with the real plan: one line per place -> floor, side of the corridor (N/S), x-range on the 0..1000 grid.
Doctor names come from the app's doctor table (real SGMH faculty list), shown under their department's OPD room."""
from flask import render_template, jsonify, session

FLOORS = [("G", "Ground Floor", "भूतल"), ("1", "First Floor", "प्रथम तल"), ("2", "Second Floor", "द्वितीय तल")]
CORR_Y, N_Y, S_Y, ROW_H = 280, 50, 325, 185   # corridor centre line, north row top, south row top, row height (map units)
UNIT_M = 0.12                                 # 1 map unit = 0.12 m  (map is 120 m long)

# (id, floor, side, x0, x1, category, English name, Hindi name, keywords, [department names used by the doctor table])
ROOMS = [
 ("reg",   0, "N",  50, 190, "service",   "Registration & Reception", "पंजीकरण एवं रिसेप्शन", "registration parchi card token counter new patient reception", []),
 ("med",   0, "N", 190, 310, "opd",       "Medicine OPD", "मेडिसिन ओपीडी", "fever bukhar sugar diabetes bp general physician", ["Medicine"]),
 ("surg",  0, "N", 310, 430, "opd",       "General Surgery OPD", "सर्जरी ओपीडी", "surgery operation hernia", ["General Surgery"]),
 ("core0", 0, "N", 440, 560, "core",      "Lifts & Stairs", "लिफ्ट एवं सीढ़ियाँ", "lift elevator stairs", []),
 ("path",  0, "N", 570, 690, "diag",      "Pathology Lab (Blood / Urine Tests)", "पैथोलॉजी लैब (खून/पेशाब जाँच)", "pathology lab blood test urine report sample collection jaanch", []),
 ("bb",    0, "N", 690, 810, "diag",      "Blood Bank", "ब्लड बैंक", "blood bank donate donor khoon rakt", []),
 ("er",    0, "N", 820, 960, "emergency", "Emergency & Trauma (24x7)", "इमरजेंसी एवं ट्रॉमा (24x7)", "emergency casualty trauma accident ambulance", []),
 ("pharm", 0, "S",  50, 190, "pharmacy",  "Pharmacy / Medical Store", "फार्मेसी / मेडिकल स्टोर", "pharmacy medicine dawai dawa chemist medical store", []),
 ("enq",   0, "S", 190, 290, "service",   "Enquiry & Help Desk", "पूछताछ एवं सहायता", "enquiry help desk information puchtachh", []),
 ("radio", 0, "S", 290, 430, "diag",      "Radio-diagnosis (X-ray, CT, USG)", "रेडियो-डायग्नोसिस (एक्स-रे, सीटी, सोनोग्राफी)", "xray x-ray ct scan usg sonography imaging mri", ["Radio-diagnosis"]),
 ("wc0",   0, "S", 440, 520, "service",   "Toilets", "शौचालय", "toilet washroom bathroom", []),
 ("ortho", 0, "S", 530, 660, "opd",       "Orthopaedics OPD", "हड्डी रोग (ऑर्थो) ओपीडी", "bone haddi fracture joint ortho", ["Orthopaedics"]),
 ("ent",   0, "S", 660, 790, "opd",       "ENT OPD", "ईएनटी (कान-नाक-गला) ओपीडी", "ear nose throat kaan naak gala", ["ENT"]),
 ("wait",  0, "S", 800, 960, "service",   "Waiting Hall & Canteen", "प्रतीक्षालय एवं कैंटीन", "canteen food tea waiting hall", []),
 ("card",  1, "N",  50, 190, "opd",       "Cardiology OPD (Doctors' chambers)", "कार्डियोलॉजी ओपीडी (डॉक्टर कक्ष)", "cardiology heart dil seene chest pain cardiologist", ["Cardiology"]),
 ("ecg",   1, "N", 190, 290, "diag",      "ECG / Echo / TMT Room", "ईसीजी / इको / टीएमटी कक्ष", "ecg echo tmt heart test", []),
 ("paed",  1, "N", 290, 430, "opd",       "Paediatrics OPD", "बाल रोग ओपीडी", "child baby bachcha kids paediatric vaccine", ["Paediatrics"]),
 ("core1", 1, "N", 440, 560, "core",      "Lifts & Stairs", "लिफ्ट एवं सीढ़ियाँ", "lift elevator stairs", []),
 ("obg",   1, "N", 570, 710, "opd",       "Obstetrics & Gynaecology OPD", "प्रसूति एवं स्त्री रोग ओपीडी", "pregnancy garbh delivery mahila women gynae", ["Gynaecology", "Obstetrics & Gynaecology"]),
 ("eye",   1, "N", 710, 830, "opd",       "Ophthalmology (Eye) OPD", "नेत्र रोग ओपीडी", "eye aankh ophthalmology", ["Ophthalmology"]),
 ("skin",  1, "N", 830, 960, "opd",       "Dermatology (Skin) OPD", "त्वचा रोग ओपीडी", "skin twacha dermatology rash", ["Dermatology (Skin)"]),
 ("dent",  1, "S",  50, 170, "opd",       "Dentistry OPD", "दंत रोग ओपीडी", "dental dentist teeth daant", ["Dentistry"]),
 ("neuro", 1, "S", 170, 300, "opd",       "Neurosurgery OPD", "न्यूरोसर्जरी ओपीडी", "brain nerve spine neuro head injury", ["Neurosurgery"]),
 ("tb",    1, "S", 300, 430, "opd",       "TB & Chest OPD", "टीबी एवं छाती रोग ओपीडी", "tb chest cough breathing asthma", ["TB & Chest"]),
 ("wc1",   1, "S", 440, 520, "service",   "Toilets", "शौचालय", "toilet washroom bathroom", []),
 ("psy",   1, "S", 530, 660, "opd",       "Psychiatry OPD", "मनोरोग ओपीडी", "psychiatry mental stress depression", ["Psychiatry"]),
 ("bill",  1, "S", 660, 800, "service",   "Cash & Billing Counter", "कैश एवं बिलिंग काउंटर", "cash billing payment", []),
 ("icu",   2, "N",  50, 210, "critical",  "ICU (Intensive Care Unit)", "आईसीयू (गहन चिकित्सा इकाई)", "icu intensive care critical ventilator", []),
 ("ccu",   2, "N", 210, 330, "critical",  "CCU (Cardiac Care Unit)", "सीसीयू (हृदय गहन चिकित्सा)", "ccu cardiac care heart attack", []),
 ("nicu",  2, "N", 330, 430, "critical",  "NICU / PICU (Newborn & Child ICU)", "एनआईसीयू / पीआईसीयू (नवजात/बाल आईसीयू)", "nicu picu newborn baby child icu", []),
 ("core2", 2, "N", 440, 560, "core",      "Lifts & Stairs", "लिफ्ट एवं सीढ़ियाँ", "lift elevator stairs", []),
 ("ot",    2, "N", 570, 740, "critical",  "Operation Theatres", "ऑपरेशन थिएटर", "ot operation theatre surgery", []),
 ("rec",   2, "N", 740, 860, "critical",  "Post-op Recovery", "पोस्ट-ऑप रिकवरी", "recovery post operative", []),
 ("pre",   2, "N", 860, 960, "critical",  "Pre-op / Anaesthesia Room", "प्री-ऑप / एनेस्थीसिया कक्ष", "pre op anaesthesia", []),
 ("mw",    2, "S",  50, 210, "ward",      "Male Ward", "पुरुष वार्ड", "ward male admitted bed", []),
 ("fw",    2, "S", 210, 340, "ward",      "Female Ward", "महिला वार्ड", "ward female admitted bed", []),
 ("mat",   2, "S", 340, 430, "ward",      "Maternity Ward", "प्रसूति वार्ड", "maternity delivery ward labour", []),
 ("wc2",   2, "S", 440, 520, "service",   "Toilets", "शौचालय", "toilet washroom bathroom", []),
 ("pw",    2, "S", 530, 660, "ward",      "Paediatric Ward", "बाल वार्ड", "paediatric child ward", []),
 ("prv",   2, "S", 660, 800, "ward",      "Private Rooms", "प्राइवेट रूम", "private room cabin", []),
 ("duty",  2, "S", 800, 960, "service",   "Doctors' & Nurses' Duty Room", "डॉक्टर/नर्स ड्यूटी रूम", "duty room nurse station", []),
]
GATES = [("gate_main", 0, 30, "Main Entrance", "मुख्य प्रवेश द्वार", "entrance gate main parking"), ("gate_er", 0, 975, "Emergency Gate", "इमरजेंसी गेट", "emergency gate ambulance")]
FLOOR_OF_CATEGORY = {}

def build(doctors):
    rooms = []
    for rid, fl, side, x0, x1, cat, name, hi, kw, depts in ROOMS:
        rooms.append(dict(id=rid, floor=fl, side=side, x=x0, w=x1 - x0, y=N_Y if side == "N" else S_Y, h=ROW_H, cx=(x0 + x1) // 2, cat=cat, name=name, hi=hi, kw=kw,
                          doctors=[d for d in doctors if d["dept"] in depts]))
    gates = [dict(id=i, floor=f, x=x, y=CORR_Y, name=n, hi=h, kw=k) for i, f, x, n, h, k in GATES]
    return dict(floors=[dict(id=i, name=n, hi=h) for i, n, h in FLOORS], rooms=rooms, gates=gates, corrY=CORR_Y, unitM=UNIT_M, w=1000, h=560)

def register(ns):
    app, q = ns["app"], ns["q"]
    def doctors():
        return [dict(name=r["name"], dept=r["dept"], desig=r["designation"] or "", degree=r["degree"] or "")
                for r in q("SELECT name,dept,designation,degree FROM users WHERE role='doctor' AND designation IS NOT NULL ORDER BY dept,id")]

    @app.context_processor
    def _map_helpers():  # used by appointment / status pages: department -> room id on the map
        def room_info(dept):
            r = next((x for x in ROOMS if dept in (x[9] or [])), None)
            if not r: return None
            hi = session.get("lang") == "hi"
            return dict(id=r[0], name=r[7] if hi else r[6], floor=FLOORS[r[1]][2] if hi else FLOORS[r[1]][1])
        return dict(room_for=lambda dept: next((r[0] for r in ROOMS if dept in (r[9] or [])), None), room_info=room_info)

    @app.route("/navigate")
    def navigate(): return render_template("navigate.html")

    @app.route("/api/map")
    def api_map(): return jsonify(build(doctors()))
