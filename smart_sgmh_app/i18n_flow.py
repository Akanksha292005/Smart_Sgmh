"""Hindi text for the start page, welcome home, registration step, history and records (flow.py).
FLOW_HI = exact text nodes (added only when not already translated). FLOW_PAT = phrases inside text that also holds data (dates, names stay as they are)."""
import re

FLOW_HI = {
 "Family Planning (daily)": "परिवार नियोजन (प्रतिदिन)", "Unit I": "यूनिट I", "Unit II": "यूनिट II", "Unit III": "यूनिट III",
 "Sits in": "बैठते हैं",
 "Dentistry": "दंत रोग", "Dermatology (Skin)": "त्वचा रोग (डर्मेटोलॉजी)", "General Surgery": "सामान्य शल्य चिकित्सा", "Neurosurgery": "न्यूरो सर्जरी", "Ophthalmology": "नेत्र रोग", "Paediatric Surgery": "बाल शल्य चिकित्सा", "Plastic Surgery": "प्लास्टिक सर्जरी", "Psychiatry": "मनोरोग", "Urology": "मूत्र रोग (यूरोलॉजी)",

 "You can look at every doctor and department without logging in.": "आप बिना लॉगिन किए हर डॉक्टर और विभाग देख सकते हैं।", "Login or registration is asked only when you press": "लॉगिन या रजिस्ट्रेशन सिर्फ़ तब माँगा जाता है जब आप दबाते हैं:", "Book OPD": "OPD बुक करें",
 "OPD is for a doctor consultation without staying in hospital.": "OPD बिना अस्पताल में रुके डॉक्टर से परामर्श के लिए है।", "If the patient has to stay in hospital, use": "यदि मरीज़ को अस्पताल में रुकना है, तो उपयोग करें:", "IPD admission": "IPD भर्ती", "(a separate process).": "(यह अलग प्रक्रिया है)।",
 "Choose your doctor": "अपना डॉक्टर चुनें", "All departments": "सभी विभाग", "Find a doctor": "डॉक्टर खोजें", "Book by department": "विभाग से बुक करें", "IPD is for patients who need to stay in hospital.": "IPD उन मरीज़ों के लिए है जिन्हें अस्पताल में रुकना है।",
 "For a doctor consultation without staying, use": "रुके बिना डॉक्टर से परामर्श के लिए उपयोग करें:", "(a separate process). You can read everything here without logging in; login is asked when you send the admission request.": "(यह अलग प्रक्रिया है)। यह सब बिना लॉगिन पढ़ सकते हैं; भर्ती का अनुरोध भेजते समय लॉगिन माँगा जाता है।",

 # start page
 "Arogya Path - SGMH Rewa": "आरोग्य पथ - SGMH रीवा", "Welcome to": "आपका स्वागत है", "Arogya Path": "आरोग्य पथ",
 "Book your doctor, track your visit, and keep your health history in one place.": "डॉक्टर बुक करें, अपनी विज़िट ट्रैक करें और अपना स्वास्थ्य इतिहास एक ही जगह रखें।",
 "Enter your name and mobile number, then the OTP": "अपना नाम और मोबाइल नंबर डालें, फिर OTP डालें",
 "Choose a doctor. Your details are asked once, at this step": "डॉक्टर चुनें। आपकी जानकारी इसी चरण में, सिर्फ़ एक बार माँगी जाती है",
 "Visit the hospital with your QR. Every visit is saved in your history": "अपने QR के साथ अस्पताल आएँ। हर विज़िट आपके इतिहास में सहेजी जाती है",
 "Emergency 24x7: 112 / 108": "इमरजेंसी 24x7: 112 / 108", "Login or Register": "लॉगिन या रजिस्टर करें", "New or returning patient: use the same steps.": "नए या पुराने मरीज़: यही चरण अपनाएँ।",
 "Your name": "आपका नाम", "Send OTP": "OTP भेजें", "Hospital website": "अस्पताल की वेबसाइट", "Staff login": "स्टाफ लॉगिन", "Name as on your ID": "नाम जैसा आपके पहचान पत्र पर है", "10-digit mobile": "10 अंकों का मोबाइल",
 "Enter the OTP": "OTP डालें", "OTP sent to": "OTP भेजा गया:", "Demo mode: no SMS gateway yet. Your OTP is": "डेमो मोड: अभी SMS गेटवे नहीं है। आपका OTP है", "OTP": "OTP", "Your password": "आपका पासवर्ड",
 "This account is protected. Nobody can open it without the OTP and your password.": "यह खाता सुरक्षित है। OTP और आपके पासवर्ड के बिना इसे कोई नहीं खोल सकता।", "Change number": "नंबर बदलें", "6 digits": "6 अंक", "Login": "लॉगिन", "Continue": "आगे बढ़ें", "Send a new OTP": "नया OTP भेजें",
 # nav
 "My home": "मेरा होम", "History": "इतिहास", "My records": "मेरे रिकॉर्ड", "Login / Register": "लॉगिन / रजिस्टर",
 # flashes
 "Enter a valid 10-digit mobile number.": "सही 10 अंकों का मोबाइल नंबर डालें।", "Please enter your name (letters only).": "कृपया अपना नाम डालें (सिर्फ़ अक्षर)।",
 "This number belongs to hospital staff. Please use Staff login.": "यह नंबर अस्पताल के स्टाफ का है। कृपया स्टाफ लॉगिन का उपयोग करें।", "Too many wrong attempts. Please try again after 15 minutes.": "बहुत ज़्यादा गलत प्रयास। कृपया 15 मिनट बाद फिर कोशिश करें।",
 "Please enter your name and mobile number again.": "कृपया अपना नाम और मोबाइल नंबर फिर से डालें।", "The OTP or password is not correct.": "OTP या पासवर्ड सही नहीं है।", "Patients log in with an OTP on the start page.": "मरीज़ शुरुआती पेज पर OTP से लॉगिन करते हैं।",
 "Registration complete. Now choose a time for your appointment.": "रजिस्ट्रेशन पूरा हुआ। अब अपनी अपॉइंटमेंट का समय चुनें।", "Give the record a short name, for example Old prescription.": "रिकॉर्ड को छोटा नाम दें, जैसे पुरानी पर्ची।",
 "Enter the date of the record.": "रिकॉर्ड की तारीख डालें।", "Choose a PDF, JPG or PNG file.": "PDF, JPG या PNG फ़ाइल चुनें।", "The file is larger than 5 MB.": "फ़ाइल 5 MB से बड़ी है।", "Only PDF, JPG or PNG files are allowed.": "सिर्फ़ PDF, JPG या PNG फ़ाइलें मान्य हैं।",
 "Saved. Your doctor can see this record at your next visit.": "सहेज लिया। आपके अगली बार आने पर डॉक्टर यह रिकॉर्ड देख सकेंगे।", "Record deleted.": "रिकॉर्ड हटा दिया गया।",
 # home
 "Registration complete": "रजिस्ट्रेशन पूरा हुआ", "You are logged in": "आप लॉगिन हैं", "Welcome,": "स्वागत है,", "Your UHID is issued when you choose your first doctor.": "पहला डॉक्टर चुनने पर आपका UHID जारी होता है।",
 "You are checked in": "आपका चेक-इन हो गया है", "Follow your queue position live.": "अपनी कतार की स्थिति लाइव देखें।", "Your next appointment": "आपकी अगली अपॉइंटमेंट", "Show the QR at reception.": "रिसेप्शन पर QR दिखाएँ।",
 "Need another checkup?": "दोबारा जाँच करानी है?", "Your last visit was on": "आपकी पिछली विज़िट थी", "with": "के साथ", "Next step: book your first appointment": "अगला कदम: अपनी पहली अपॉइंटमेंट बुक करें",
 "Choose a department and a doctor. We ask for your details once, at that step.": "विभाग और डॉक्टर चुनें। आपकी जानकारी उसी चरण में, एक बार माँगी जाती है।",
 "Track my visit": "मेरी विज़िट ट्रैक करें", "Open appointment": "अपॉइंटमेंट खोलें", "Book an appointment": "अपॉइंटमेंट बुक करें", "Your journey": "आपकी यात्रा",
 "Log in with OTP": "OTP से लॉगिन", "Choose a doctor and a time": "डॉक्टर और समय चुनें", "Registration: your details and password (asked once, when you choose a doctor)": "रजिस्ट्रेशन: आपकी जानकारी और पासवर्ड (डॉक्टर चुनते समय, एक बार)",
 "Visit day: show the QR at reception, wait for your token, see the doctor, tests, medicines": "विज़िट का दिन: रिसेप्शन पर QR दिखाएँ, टोकन का इंतज़ार करें, डॉक्टर से मिलें, जाँच और दवाइयाँ",
 "History is saved: date, doctor, advice and reports are here the next time": "इतिहास सहेजा जाता है: तारीख, डॉक्टर, सलाह और रिपोर्ट अगली बार यहीं मिलेंगी", "Open": "खोलें",
 "Doctors you have consulted": "आपने जिन डॉक्टरों को दिखाया", "visit(s)": "विज़िट", "last": "आखिरी", "Book a follow-up": "फ़ॉलो-अप बुक करें",
 "None yet. The doctors you visit are listed here, with the date of your last visit.": "अभी कोई नहीं। आप जिन डॉक्टरों को दिखाएँगे वे यहाँ आखिरी विज़िट की तारीख के साथ दिखेंगे।", "Recent visits": "हाल की विज़िट", "See all visits": "सभी विज़िट देखें",
 "My records (old prescriptions and reports)": "मेरे रिकॉर्ड (पुरानी पर्चियाँ और रिपोर्ट)", "Upload / view all": "अपलोड करें / सभी देखें", "Nothing uploaded yet. Add an old prescription so your doctor can see it.": "अभी कुछ अपलोड नहीं हुआ। पुरानी पर्ची जोड़ें ताकि डॉक्टर उसे देख सकें।",
 "My visits": "मेरी विज़िट", "Reports": "रिपोर्ट", "My family": "मेरा परिवार", "Blood bank": "ब्लड बैंक",
 # history / records
 "My history": "मेरा इतिहास", "Every visit: the date, the doctor, and what was checked.": "हर विज़िट: तारीख, डॉक्टर और क्या जाँच हुई।", "Problem:": "समस्या:", "What was found:": "क्या पाया गया:", "Tests done:": "की गई जाँचें:", "Medicines:": "दवाइयाँ:", "Follow-up:": "फ़ॉलो-अप:",
 "The doctor's advice will appear here after the doctor approves it.": "डॉक्टर की मंज़ूरी के बाद उनकी सलाह यहाँ दिखेगी।", "No visits yet. After your first visit, the date, doctor and what was checked will be saved here.": "अभी कोई विज़िट नहीं। पहली विज़िट के बाद तारीख, डॉक्टर और की गई जाँच यहाँ सहेजी जाएगी।",
 "My records": "मेरे रिकॉर्ड", "Upload old prescriptions and reports (PDF, JPG or PNG, up to 5 MB). Your doctor can see them when you come for a checkup. Only you and hospital doctors and staff can open them.": "पुरानी पर्चियाँ और रिपोर्ट अपलोड करें (PDF, JPG या PNG, 5 MB तक)। जाँच के लिए आने पर आपके डॉक्टर इन्हें देख सकते हैं। इन्हें केवल आप और अस्पताल के डॉक्टर व स्टाफ खोल सकते हैं।",
 "Add a record": "रिकॉर्ड जोड़ें", "Name of the record": "रिकॉर्ड का नाम", "Date of the record (optional)": "रिकॉर्ड की तारीख (वैकल्पिक)", "For whom": "किसके लिए", "File": "फ़ाइल", "Note (optional)": "नोट (वैकल्पिक)", "Upload": "अपलोड करें",
 "e.g. Old prescription": "जैसे पुरानी पर्ची", "e.g. Dr. Sharma, fever, Jan 2026": "जैसे डॉ. शर्मा, बुखार, जनवरी 2026", "For": "किसके लिए", "Added": "जोड़ा गया", "View": "देखें", "Delete": "हटाएँ", "No records yet.": "अभी कोई रिकॉर्ड नहीं।",
 # booking additions
 "UHID is issued at registration": "UHID रजिस्ट्रेशन पर जारी होता है", "You have seen this doctor before": "आप इन डॉक्टर को पहले दिखा चुके हैं", "Found:": "पाया गया:", "Tests:": "जाँचें:", "Book as a follow-up visit": "फ़ॉलो-अप विज़िट के रूप में बुक करें",
 # registration step
 "1 Login": "1 लॉगिन", "2 Doctor chosen": "2 डॉक्टर चुना", "3 Registration": "3 रजिस्ट्रेशन", "4 Choose time": "4 समय चुनें", "You are booking with": "आप बुक कर रहे हैं:",
 "The hospital needs these details once.": "अस्पताल को ये जानकारी एक बार चाहिए।", "You also set a password, so nobody else can open your account.": "आप पासवर्ड भी सेट करते हैं, ताकि आपका खाता कोई और न खोल सके।",
 "After you save, you get your UHID and go straight to choosing a time.": "सहेजने के बाद आपको UHID मिलता है और आप सीधे समय चुनने पर पहुँचते हैं।", "Set your password": "अपना पासवर्ड सेट करें",
 "Next time you log in with your mobile number, an OTP and this password.": "अगली बार आप मोबाइल नंबर, OTP और इस पासवर्ड से लॉगिन करेंगे।", "Save and continue": "सहेजें और आगे बढ़ें",
 # appointment: what next
 "What happens next": "आगे क्या होगा", "Come on the date and time shown above. Carry a photo ID.": "ऊपर दी गई तारीख और समय पर आएँ। फ़ोटो पहचान पत्र साथ लाएँ।", "Show this QR at reception. You get a token number.": "रिसेप्शन पर यह QR दिखाएँ। आपको टोकन नंबर मिलेगा।",
 "Wait.": "इंतज़ार करें।", "Track your visit live": "अपनी विज़िट लाइव ट्रैक करें", ": queue position, lab and medicine steps.": ": कतार की स्थिति, लैब और दवाई के चरण।", "See the doctor. Tests, if any, are done at the lab.": "डॉक्टर से मिलें। जाँचें, यदि हों, लैब में होती हैं।",
 "Your advice and reports are saved. See them on": "आपकी सलाह और रिपोर्ट सहेजी जाती हैं। इन्हें यहाँ देखें:", "Home": "होम", "and in": "और यहाँ", "seen": "देखे गए", "ready": "तैयार", "Patient's uploaded records": "मरीज़ के अपलोड किए रिकॉर्ड", "(old prescriptions and reports)": "(पुरानी पर्चियाँ और रिपोर्ट)", "Comment (optional)": "टिप्पणी (वैकल्पिक)",
}
DESIG = {"Professor": "प्रोफेसर", "Associate Professor": "एसोसिएट प्रोफेसर", "Assistant Professor": "असिस्टेंट प्रोफेसर", "Senior Resident": "सीनियर रेज़िडेंट", "Junior Resident": "जूनियर रेज़िडेंट", "Consultant": "कंसल्टेंट", "Resident": "रेज़िडेंट", "Medical Officer": "चिकित्सा अधिकारी"}
FLOW_HI.update(DESIG)
_D = lambda p, r, f=0: (re.compile(p, f), r)
_REL = {"Self": "स्वयं", "Wife": "पत्नी", "Husband": "पति", "Son": "बेटा", "Daughter": "बेटी", "Father": "पिता", "Mother": "माता", "Brother": "भाई", "Sister": "बहन", "Friend": "मित्र", "Other": "अन्य", "Relative": "रिश्तेदार"}
_ST = {"ready": "तैयार", "pending": "लंबित", "collected": "लिया गया", "received": "प्राप्त", "reported": "रिपोर्ट आई"}
FLOW_PAT = [
 _D(r"\bRoom (\d+)", r"कक्ष \1"),
 _D(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", lambda m: {"Mon": "सोम", "Tue": "मंगल", "Wed": "बुध", "Thu": "गुरु", "Fri": "शुक्र", "Sat": "शनि", "Sun": "रवि"}[m.group(1)]),
 _D(r"8:30 AM - 1:30 PM", "सुबह 8:30 - दोपहर 1:30 बजे"), _D(r"8 AM - 4 PM", "सुबह 8 - शाम 4 बजे"),
 *[_D(re.escape(k), v) for k, v in FLOW_HI.items() if k.startswith(("Log in with OTP", "Choose a doctor and a time", "Registration: your details", "Visit day:", "History is saved"))],
 _D(r"^Registration:", "रजिस्ट्रेशन:"),
 _D(r"\((" + "|".join(_REL) + r")\)", lambda m: "(" + _REL[m.group(1)] + ")"),
 _D(r"\((" + "|".join(_ST) + r")\)", lambda m: "(" + _ST[m.group(1)] + ")"),
 _D(r"\((" + "|".join(sorted(DESIG, key=len, reverse=True)) + r")\)", lambda m: "(" + DESIG[m.group(1)] + ")"),
 _D(r"^Earliest available:", "सबसे जल्दी उपलब्ध:"), _D(r"^Problem:", "समस्या:"),
]
