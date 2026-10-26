"""OPD roster, rooms and services, transcribed from the signboards photographed inside the hospital (17 Oct 2026).
Sources: ground-floor roster board, surgery OPD board (rooms 1-4, 11), dental board, paediatrics board (Gandhi Smriti),
Obstetrics & Gynaecology board (rooms 8, 2, 5), Bal Vikas Kendra board, ground-floor and first-floor OPD floor plans.

Day index: 0=Mon ... 5=Sat (Sunday OPD closed).  Entry: (doctor name, designation, room)
Parts of some boards were covered by paper stickers or glare in the photos. Those places are marked  # CHECK  and should be
verified against the board before real use. Names follow the Hindi spelling on the boards, so spellings are best-effort."""

PROF, ASSOC, ASST, NOM = "Professor", "Associate Professor", "Assistant Professor", " (Nominated)"
SR, JR = "Senior Resident", "Junior Resident"

def day(*people): return list(people)

ROSTER = {
 "Psychiatry": {
  0: [("Dr. Nimisha Mishra", PROF, None), ("Dr. Ambareesh Mishra", ASST, None)],
  1: [("Dr. Sunil Kumar Ahuja", ASSOC, None), ("Dr. Dheerendra Mishra", ASSOC + NOM, None)],
  2: [("Dr. Dheerendra Mishra", ASSOC + NOM, None), ("Dr. Ambareesh Mishra", ASST, None)],
  3: [("Dr. Sunil Kumar Ahuja", ASSOC, None)],
  4: [("Dr. Nimisha Mishra", PROF, None), ("Dr. Ambareesh Mishra", ASST, None)],
  5: [("Dr. Ambareesh Mishra", ASST, None), ("Dr. Prashant Marathi", SR, None), ("Dr. Amarendra Kumar Singh", SR, None)],
 },
 "Orthopaedics": {
  0: [("Dr. Vidyabhushan Singh", PROF, None), ("Dr. Jitesh Gawande", ASSOC + NOM, None), ("Dr. Shubham Mishra", ASST, None)],
  1: [("Dr. Pradeep Kumar Verma", ASSOC, None), ("Dr. Rahul Kundan", ASSOC, None), ("Dr. Vimal Singh", ASST, None)],
  2: [("Dr. Vidyabhushan Singh", PROF, None), ("Dr. Jitesh Gawande", ASSOC + NOM, None), ("Dr. Shubham Mishra", ASST, None)],
  3: [("Dr. Pankaj Kumar Lakhtakia", PROF, None), ("Dr. Pradeep Kumar Verma", ASSOC, None), ("Dr. Dinesh Kumar", ASST, None), ("Dr. Vimal Singh", ASST, None)],  # CHECK row partly hidden by glare
  4: [("Dr. Amit Kumar Chaurasia", PROF, None), ("Dr. Jitesh Gawande", ASSOC + NOM, None), ("Dr. Shubham Mishra", ASST, None)],
  5: [("Dr. Pradeep Kumar Verma", ASSOC, None), ("Dr. Rahul Kundan", ASSOC, None), ("Dr. Dinesh Kumar", ASST, None), ("Dr. Vimal Singh", ASST, None)],
 },
 "Medicine": {
  0: [("Dr. M. Indurkar", PROF, None), ("Dr. D.K. Malviya", ASSOC, None), ("Dr. B.S. Deepankar", ASST, None)],
  1: [("Dr. P.K. Baghel", PROF, None), ("Dr. Keshav Singh", PROF, None), ("Dr. K.S. Kapoor", ASST, None)],
  2: [("Dr. M.H. Usmani", PROF, None), ("Dr. Rakesh Patel", ASSOC, None), ("Dr. Umesh Pratap Singh", ASST, None)],
  3: [("Dr. Pradeep Nigam", PROF, None), ("Dr. D.K. Malviya", ASSOC, None), ("Dr. K.S. Kapoor", ASST, None)],
  4: [("Dr. A. Chaurasia", PROF, None), ("Dr. R.P. Pandey", ASSOC, None), ("Dr. B.S. Deepankar", ASST, None)],
  5: [("Dr. H.O. Gupta", PROF, None), ("Dr. Mahendra Tilkar", ASSOC, None), ("Dr. Umesh Pratap Singh", ASST, None)],
 },
 "Ophthalmology": {
  0: [("Dr. Pankaj Choudhary", PROF, None), ("Dr. Anamika Tiwari", ASSOC, None)],
  1: [("Dr. Shashi Jain", PROF, None), ("Dr. Charudatta Chalisgaonkar", ASSOC, None)],
  2: [("Dr. Pankaj Choudhary", PROF, None), ("Dr. Sujata Lakhtakia", ASSOC, None)],
  3: [("Dr. Shashi Jain", PROF, None), ("Dr. Eva Tirkey", PROF, None)],
  4: [("Dr. Sujata Lakhtakia", ASSOC, None), ("Dr. Anamika Tiwari", ASSOC, None)],
  5: [("Dr. Eva Tirkey", PROF, None), ("Dr. Charudatta Chalisgaonkar", ASSOC, None)],
 },
 "General Surgery": {  # surgery OPD board: room 1 and room 2
  0: [("Dr. Atul Kumar Singh", PROF + NOM, "Room 1"), ("Dr. Varsha Shukla", ASST, "Room 1"), ("Dr. Lalmani Singh", ASSOC, "Room 2")],
  1: [("Dr. Vishnu Kumar Patel", PROF + NOM, "Room 1"), ("Dr. Mukund Pandey", ASST, "Room 2")],
  2: [("Dr. Priyank Sharma", PROF, "Room 1"), ("Dr. Ashish Pratap Singh", ASST, "Room 1"), ("Dr. Yogesh Kailasiya", ASSOC, "Room 2")],
  3: [("Dr. Vinod Yadalwar", PROF, "Room 1"), ("Dr. Piyush Kumar Shrivastava", ASSOC + NOM, "Room 1"), ("Dr. Abhilash Singh", ASST, "Room 2")],
  4: [("Dr. Rachna Gupta", PROF, "Room 1 (Breast Clinic 10 AM-12 PM)"), ("Dr. Shailendra Singh", ASST, "Room 1"), ("Dr. Vrijesh Singh", PROF + NOM, "Room 2")],
  5: [("Dr. Priyank Sharma", PROF, "Room 1"), ("Dr. Ashish Pratap Singh", ASST, "Room 1"), ("Dr. Yogesh Kailasiya", ASSOC, "Room 2")],
 },
 "Plastic Surgery": {  # room 3
  0: [("Dr. Saurabh Saxena", ASSOC, "Room 3"), ("Dr. Ajay Kumar Pathak", ASST, "Room 3")],
  3: [("Dr. Saurabh Saxena", ASSOC, "Room 3"), ("Dr. Ajay Kumar Pathak", ASST, "Room 3")],
 },
 "Neurosurgery": {  # room 4 (Mon/Thu: follow-up day, Wed/Sat: Neurosurgery Wed follow-up, Sat admission day)
  0: [("Dr. Dinesh Patel", ASST, "Room 4 (follow-up day)")],
  2: [("Dr. Sonpal Jindal", ASST, "Room 4 (follow-up day)")],  # CHECK name partly covered by sticker
  3: [("Dr. Dinesh Patel", ASST, "Room 4 (follow-up day)")],
  5: [("Dr. Sonpal Jindal", ASST, "Room 4 (admission day)")],  # CHECK name partly covered by sticker
 },
 "Paediatric Surgery": {  # room 11
  1: [("Dr. Puneet Singh Parihar", ASST, "Room 11 (follow-up day)")],
  4: [("Dr. Puneet Singh Parihar", ASST, "Room 11 (admission day)")],
 },
 "Urology": {  # ground-floor roster; room number not on the boards
  1: [("Dr. Pushpendra Kumar Shukla", ASST, None)],
  4: [("Dr. Pushpendra Kumar Shukla", ASST, None)],
 },
 "Dermatology (Skin)": {  # two doctors every day, Dr. Devesh Sarswat on Saturday (board)
  **{d: [("Dr. Anoop Kumar Mishra", ASSOC + " & HOD", None), ("Dr. Sunil Singh Sengar", ASST, None)] for d in range(6)},
 },
 "Dentistry": {  # dental board; junior rows 4-7 were hidden by stickers, so only the three faculty rows are used
  0: [("Dr. Geeta (Mishra) Tripathi", PROF + " & HOD", None)], 4: [("Dr. Geeta (Mishra) Tripathi", PROF + " & HOD", None)],
  1: [("Dr. Karuna Jindwani", PROF + NOM, None)], 5: [("Dr. Karuna Jindwani", PROF + NOM, None)],
  2: [("Dr. Santosh Mishra", ASST, None)], 3: [("Dr. Santosh Mishra", ASST, None)],
 },
 "Paediatrics": {  # board of Child & Newborn Health Dept, OPD 8:30 AM to 1:30 PM, unit based
  0: [("Dr. Jitendra Singh", None, "Unit II"), ("Dr. Gaurav Tripathi", None, "Unit II")],
  1: [("Dr. Shabd Singh Yadav", None, "Unit III"), ("Dr. Surendra Singh", None, "Unit III")],
  2: [("Dr. Meena Patel", None, "Unit I"), ("Dr. Saurabh Patel", None, "Unit I")],
  3: [("Dr. Karan Joshi", None, "Unit II"), ("Dr. Priyanka Shukla", None, "Unit II")],
  4: [("Dr. Deepak Dwivedi", None, "Unit III"), ("Dr. Surendra Singh", None, "Unit III")],
  5: [("Dr. Saurabh Patel", None, "Unit I"), ("Dr. Ravi Prakash Singh", None, "Unit I")],
 },
 "Gynaecology": {  # Obstetrics & Gynaecology board: Gynae OPD Room 8, ANC OPD Room 2, Special OPD Room 5
  0: [("Dr. Kalpana Yadav", None, "Gynae OPD Room 8"), ("Dr. Sheetal Patel", None, "Gynae OPD Room 8"), ("Dr. Shailja Soni", None, "Gynae OPD Room 8"),
      ("Dr. Neha Khatik", None, "ANC OPD Room 2"), ("Dr. Archana Pandey", None, "ANC OPD Room 2"), ("Dr. Priyanka Paroha", None, "ANC OPD Room 2"),
      ("Dr. Anuradha Mishra", None, "Special OPD Room 5: Infertility Clinic")],
  1: [("Dr. Beenu Singh", None, "Gynae OPD Room 8"), ("Dr. Sanghmitra Singh", None, "Gynae OPD Room 8"), ("Dr. Shailja Soni", None, "Gynae OPD Room 8"),
      ("Dr. Gunjan Goswami", None, "ANC OPD Room 2"), ("Dr. Archana Pandey", None, "ANC OPD Room 2"), ("Dr. Priyanka Paroha", None, "ANC OPD Room 2"),
      ("Dr. Kshama Vishwakarma", None, "Special OPD Room 5: Menopause Clinic")],
  2: [("Dr. Padma Shukla", None, "Gynae OPD Room 8"), ("Dr. Sarita Singh", None, "Gynae OPD Room 8"), ("Dr. Shailja Soni", None, "Gynae OPD Room 8"),
      ("Dr. Sonal Agrawal", None, "ANC OPD Room 2"), ("Dr. Archana Pandey", None, "ANC OPD Room 2"), ("Dr. Priyanka Paroha", None, "ANC OPD Room 2"),
      ("Dr. Pooja Gangwar", None, "Special OPD Room 5: STI Clinic")],
  3: [("Dr. Anuradha Mishra", None, "Gynae OPD Room 8"), ("Dr. Neha Khatik", None, "Gynae OPD Room 8"), ("Dr. Shailja Soni", None, "Gynae OPD Room 8"),
      ("Dr. Sheetal Patel", None, "ANC OPD Room 2"), ("Dr. Archana Pandey", None, "ANC OPD Room 2"), ("Dr. Priyanka Paroha", None, "ANC OPD Room 2"),
      ("Dr. Kalpana Yadav", None, "Special OPD Room 5: Adolescent Clinic")],
  4: [("Dr. Kshama Vishwakarma", None, "Gynae OPD Room 8"), ("Dr. Gunjan Goswami", None, "Gynae OPD Room 8"), ("Dr. Shailja Soni", None, "Gynae OPD Room 8"),
      ("Dr. Sanghmitra Singh", None, "ANC OPD Room 2"), ("Dr. Archana Pandey", None, "ANC OPD Room 2"), ("Dr. Priyanka Paroha", None, "ANC OPD Room 2"),
      ("Dr. Sheetal Patel", None, "Special OPD Room 5: Cancer Clinic")],
  5: [("Dr. Sonal Agrawal", None, "Gynae OPD Room 8"), ("Dr. Pooja Gangwar", None, "Gynae OPD Room 8"), ("Dr. Shailja Soni", None, "Gynae OPD Room 8"),
      ("Dr. Sarita Singh", None, "ANC OPD Room 2"), ("Dr. Archana Pandey", None, "ANC OPD Room 2"), ("Dr. Priyanka Paroha", None, "ANC OPD Room 2"),
      ("Dr. Padma Shukla", None, "Special OPD Room 5: Endocrine Clinic")],
 },
}
ROSTER["Dermatology (Skin)"][5].insert(0, ("Dr. Devesh Sarswat", PROF, None))
# Dr. Kiran Bala Mishra: Family Planning, every day (Obstetrics & Gynaecology board)
ROSTER["Gynaecology"] = {d: v + [("Dr. Kiran Bala Mishra", None, "Family Planning (daily)")] for d, v in ROSTER["Gynaecology"].items()}

# Board spelling -> name already in doctors_data.py (the same person). Only clear matches.
ALIASES = {
 "Dr. M. Indurkar": "Dr. Manoj Indurkar", "Dr. P.K. Baghel": "Dr. Praveen Kumar Baghel",
 "Dr. Beenu Singh": "Dr. Beenu Kushwah Singh",
}
# Departments that exist only because of the boards (not in the older doctors list)
NEW_DEPTS = ["Plastic Surgery", "Paediatric Surgery", "Urology"]

# OPD hours per department when they differ from the default 8:00-16:00 slot grid
DEPT_HOURS = {"Paediatrics": ("08:30", "13:30")}   # board: 8:30 AM to 1:30 PM

DAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
DAYS_HI = ["सोम", "मंगल", "बुध", "गुरु", "शुक्र", "शनि"]

# Services that are not doctor rosters
BAL_VIKAS_KENDRA = ["Newborn follow-up clinic", "ROP screening", "Hearing test (OAE)", "Developmental assessment", "Laser therapy",
                    "Speech therapy", "Physiotherapy", "Early stimulation", "Occupational therapy", "Play therapy"]
BAL_VIKAS_KENDRA_HI = ["नवजात शिशु फॉलोअप क्लीनिक", "आर.ओ.पी. स्क्रीनिंग", "श्रवण जाँच (O.A.E)", "विकास की जाँच", "लेजर थेरेपी",
                       "स्पीच थेरेपी", "फिजियो थेरेपी", "अरली स्टीमुलेशन", "ऑक्यूपेशनल थेरेपी", "प्ले थेरेपी"]
DENTAL_RESIDENTS_NOTE = "Senior and junior resident rows on the dental board were covered by stickers; verify before publishing."
