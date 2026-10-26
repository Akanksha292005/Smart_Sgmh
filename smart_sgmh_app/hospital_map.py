"""Indoor hospital map + wayfinding (/navigate, /api/map).
Ground and First floor OPD areas follow the hospital's own floor-plan boards (photographed 17 Oct 2026); corridor distances are approximate.
Second floor and rooms tagged [to be confirmed] are NOT on any photographed board: replace them when the real plan is available.
One line per place in ROOMS -> floor, side of the corridor (N/S), x-range on the 0..1000 grid.
Doctor names come from the app's doctor table (real SGMH faculty list), shown under their department's OPD room."""
from flask import render_template, jsonify, session

FLOORS = [("G", "Ground Floor", "भूतल"), ("1", "First Floor", "प्रथम तल"), ("2", "Second Floor", "द्वितीय तल")]
CORR_Y, N_Y, S_Y, ROW_H = 280, 50, 325, 185   # corridor centre line, north row top, south row top, row height (map units)
UNIT_M = 0.12                                 # 1 map unit = 0.12 m  (map is 120 m long)

# (id, floor, side, x0, x1, category, English name, Hindi name, keywords, [department names used by the doctor table])
ROOMS = [
 # ---- GROUND FLOOR: from the "Bahya Rog Vibhag (Bhu-tal)" floor plan board. Order along the corridor follows the board; distances are approximate.
 ("er",    0, "N",  50, 130, "emergency", "Emergency / Casualty (exit on the left)", "अकस्मिक चिकित्सा (बाईं ओर)", "emergency casualty trauma accident ambulance akasmik", []),
 ("ortho", 0, "N", 135, 230, "opd",       "Orthopaedics OPD (Asthi Rog)", "अस्थि रोग ओपीडी", "bone haddi fracture joint ortho", ["Orthopaedics"]),
 ("psy",   0, "N", 235, 320, "opd",       "Psychiatry OPD (Mansik Rog)", "मानसिक रोग ओपीडी", "psychiatry mental stress depression", ["Psychiatry"]),
 ("eye",   0, "N", 325, 435, "opd",       "Ophthalmology (Eye) OPD", "नेत्र रोग ओपीडी", "eye aankh ophthalmology netra", ["Ophthalmology"]),
 ("core0", 0, "N", 440, 560, "core",      "Stairs to First Floor", "प्रथम तल की सीढ़ियाँ", "lift elevator stairs", []),
 ("skin",  0, "N", 565, 690, "opd",       "Dermatology (Skin) OPD", "चर्म रोग ओपीडी", "skin twacha dermatology rash charm", ["Dermatology (Skin)"]),
 ("inj",   0, "N", 695, 780, "service",   "Injection Room", "इंजेक्शन रूम", "injection room dressing", []),
 ("pharm", 0, "N", 785, 960, "pharmacy",  "Medicine Distribution (Pharmacy)", "दवाई वितरण (फार्मेसी)", "pharmacy medicine dawai dawa chemist medical store distribution", []),
 ("radio", 0, "S",  50, 190, "diag",      "CT Scan & MRI Centre", "सीटी स्कैन एवं एम.आर.आई. सेन्टर", "xray x-ray ct scan usg sonography imaging mri", ["Radio-diagnosis"]),
 ("surg",  0, "S", 195, 335, "opd",       "Surgery OPD (Rooms 1-4, 11)", "सर्जरी ओपीडी (कमरा 1-4, 11)", "surgery operation hernia plastic neuro urology paediatric surgery breast clinic", ["General Surgery", "Plastic Surgery", "Neurosurgery", "Paediatric Surgery", "Urology"]),
 ("reg",   0, "S", 340, 470, "service",   "Registration Hall (Panjeeyan)", "पंजीयन हॉल", "registration parchi card token counter new patient reception", []),
 ("wc0",   0, "S", 480, 560, "service",   "Toilets & Drinking Water", "प्रसाधन एवं पीने का पानी", "toilet washroom bathroom drinking water prasadhan", []),
 ("enq",   0, "S", 570, 680, "service",   "Registration & Enquiry (Poochhtaachh)", "पंजीयन एवं पूछताछ", "enquiry help desk information puchtachh registration", []),
 ("med",   0, "S", 690, 830, "opd",       "Medicine OPD", "मेडिसिन ओपीडी", "fever bukhar sugar diabetes bp general physician medicine", ["Medicine"]),
 ("art",   0, "S", 835, 960, "service",   "ART Centre", "ए.आर.टी. सेन्टर", "art centre hiv aids", []),
 # ---- FIRST FLOOR: from the "Bahya Rog Vibhag (Prathan Tal)" floor plan board
 ("bvk",   1, "N",  50, 210, "service",   "Bal Vikas Kendra (Child Development Centre)", "बाल विकास केन्द्र", "child development hearing oae rop speech therapy physiotherapy newborn follow up", []),
 ("reg1",  1, "N", 215, 340, "service",   "Registration: Women & Child Diseases", "पंजीयन: स्त्री एवं शिशु रोग", "registration parchi women child", []),
 ("wc1b",  1, "N", 345, 430, "service",   "Toilets / Drinking Water", "प्रसाधन", "toilet washroom drinking water prasadhan", []),
 ("core1", 1, "N", 440, 560, "core",      "Stairs & Courtyard Side", "सीढ़ियाँ", "lift elevator stairs", []),
 ("obg",   1, "N", 570, 760, "opd",       "Obstetrics & Gynaecology OPD (Stri Rog: Rooms 8, 2, 5)", "स्त्री रोग ओपीडी (कमरा 8, 2, 5)", "pregnancy garbh delivery mahila women gynae anc infertility family planning", ["Gynaecology", "Obstetrics & Gynaecology"]),
 ("spt",   1, "N", 765, 860, "diag",      "Sputum Test Centre (Khakhar Jaanch)", "खखार जाँच केन्द्र", "sputum tb test khakhar", []),
 ("tb",    1, "N", 865, 960, "opd",       "Pulmonary Medicine & DOTS Centre", "पल्मोनरी मेडिसिन एवं डॉट्स सेन्टर", "tb chest cough breathing asthma dots pulmonary", ["TB & Chest", "Pulmonary Medicine"]),
 ("dent",  1, "S",  50, 170, "opd",       "Dentistry OPD (Dant Rog)", "दंत रोग ओपीडी", "dental dentist teeth daant", ["Dentistry"]),
 ("paed",  1, "S", 175, 335, "opd",       "Paediatrics OPD (Shishu Rog)", "शिशु रोग ओपीडी", "child baby bachcha kids paediatric vaccine shishu", ["Paediatrics"]),
 ("opdic", 1, "S", 340, 430, "service",   "OPD In-charge Room", "ओपीडी इंचार्ज रूम", "opd incharge office", []),
 ("wc1",   1, "S", 440, 520, "service",   "Toilets", "शौचालय", "toilet washroom bathroom", []),
 ("lec",   1, "S", 530, 660, "service",   "Lecture Hall", "लेक्चर हाल", "lecture hall", []),
 ("ent",   1, "S", 665, 960, "opd",       "ENT OPD (Naak Kaan Gala)", "नाक कान गला ओपीडी", "ear nose throat kaan naak gala ent", ["ENT"]),
 # ---- SECOND FLOOR: NOT on any photographed board. Sample layout, to be confirmed. Cardiology, labs and blood bank are also parked here until their real place is known.
 ("icu",   2, "N",  50, 210, "critical",  "ICU (Intensive Care Unit) [location to be confirmed]", "आईसीयू [स्थान की पुष्टि बाकी]", "icu intensive care critical ventilator", []),
 ("ccu",   2, "N", 210, 330, "critical",  "CCU (Cardiac Care Unit) [to be confirmed]", "सीसीयू [पुष्टि बाकी]", "ccu cardiac care heart attack", []),
 ("nicu",  2, "N", 330, 430, "critical",  "NICU / PICU [to be confirmed]", "एनआईसीयू / पीआईसीयू [पुष्टि बाकी]", "nicu picu newborn baby child icu", []),
 ("core2", 2, "N", 440, 560, "core",      "Lifts & Stairs", "लिफ्ट एवं सीढ़ियाँ", "lift elevator stairs", []),
 ("ot",    2, "N", 570, 700, "critical",  "Operation Theatres [to be confirmed]", "ऑपरेशन थिएटर [पुष्टि बाकी]", "ot operation theatre surgery", []),
 ("card",  2, "N", 705, 830, "opd",       "Cardiology OPD [to be confirmed]", "कार्डियोलॉजी ओपीडी [पुष्टि बाकी]", "cardiology heart dil seene chest pain cardiologist", ["Cardiology"]),
 ("ecg",   2, "N", 835, 960, "diag",      "ECG / Echo / TMT [to be confirmed]", "ईसीजी / इको / टीएमटी [पुष्टि बाकी]", "ecg echo tmt heart test", []),
 ("mw",    2, "S",  50, 210, "ward",      "Male Ward [to be confirmed]", "पुरुष वार्ड [पुष्टि बाकी]", "ward male admitted bed", []),
 ("fw",    2, "S", 210, 340, "ward",      "Female Ward [to be confirmed]", "महिला वार्ड [पुष्टि बाकी]", "ward female admitted bed", []),
 ("mat",   2, "S", 340, 430, "ward",      "Maternity Ward [to be confirmed]", "प्रसूति वार्ड [पुष्टि बाकी]", "maternity delivery ward labour", []),
 ("wc2",   2, "S", 440, 520, "service",   "Toilets", "शौचालय", "toilet washroom bathroom", []),
 ("path",  2, "S", 530, 690, "diag",      "Pathology Lab [to be confirmed]", "पैथोलॉजी लैब [पुष्टि बाकी]", "pathology lab blood test urine report sample collection jaanch", []),
 ("bb",    2, "S", 695, 810, "diag",      "Blood Bank [to be confirmed]", "ब्लड बैंक [पुष्टि बाकी]", "blood bank donate donor khoon rakt", []),
 ("pw",    2, "S", 815, 960, "ward",      "Paediatric Ward [to be confirmed]", "बाल वार्ड [पुष्टि बाकी]", "paediatric child ward", []),
]
GATES = [("gate_main", 0, 400, "Main Entrance (GMH Main Gate)", "मुख्य प्रवेश द्वार (जी.एम.एच. मेन गेट)", "entrance gate main parking pravesh dwar"), ("gate_er", 0, 30, "Emergency Gate", "इमरजेंसी गेट", "emergency gate ambulance akasmik")]
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
