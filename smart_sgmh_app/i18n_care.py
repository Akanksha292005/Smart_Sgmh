"""Hindi text for the blood bank, care team and death-certificate pages (ward.py).
CARE_HI = exact text nodes (added only when the key is not already translated). PATTERNS = phrases inside text that mixes fixed words with data
(dates, bed numbers, names stay as they are). Interface is meant to be fully English or fully Hindi."""
import re

CARE_HI = {
 # shared / menus
 "Blood Bank Stock": "ब्लड बैंक स्टॉक", "Blood bank staff: update stock": "ब्लड बैंक स्टाफ: स्टॉक अपडेट करें", "UHID / mobile / name": "UHID / मोबाइल / नाम", "Hospital Map": "अस्पताल नक्शा", "Privacy": "गोपनीयता", "Live Safety Demo": "लाइव सुरक्षा डेमो",
 "New": "नया", "Online": "ऑनलाइन", "Group": "रक्त समूह", "Shift": "शिफ्ट",
 # blood bank
 "Blood Bank: which blood group is available": "ब्लड बैंक: कौन-सा रक्त समूह उपलब्ध है",
 "Demo data: these numbers are SAMPLE until the blood bank staff enter the real stock.": "डेमो डेटा: ब्लड बैंक स्टाफ असली स्टॉक दर्ज करने तक ये संख्याएँ नमूना (SAMPLE) हैं।",
 "Status:": "स्थिति:", "Low": "कम", "Not available": "उपलब्ध नहीं", "Available": "उपलब्ध",
 "= 10 or more units,": "= 10 या अधिक यूनिट,", "= 1 to 9 units,": "= 1 से 9 यूनिट,", "= 0. Stock changes every hour, so": "= 0। स्टॉक हर घंटे बदलता है, इसलिए",
 "always call the blood bank to confirm before you travel": "आने से पहले ब्लड बैंक को फ़ोन करके पुष्टि ज़रूर करें",
 ": 07662-241655. Blood bank is on the Ground Floor.": ": 07662-241655। ब्लड बैंक भूतल (ग्राउंड फ्लोर) पर है।",
 "Show me the way": "रास्ता दिखाइए",
 "Units are whole-blood units in the blood bank store. Emergency patients are never made to wait for this page: tell the emergency or ICU staff, they request blood directly.": "ये यूनिट ब्लड बैंक में रखे संपूर्ण रक्त (whole blood) की हैं। इमरजेंसी मरीज़ को इस पेज के लिए कभी इंतज़ार नहीं कराया जाता: इमरजेंसी या ICU स्टाफ को बताइए, वे सीधे रक्त मँगवाते हैं।",
 "Units now": "अभी यूनिट", "New units": "नई यूनिट",
 # care team form
 "Treating doctor is set at admission. Fill who is on duty now and who is staying with the patient. The patient and family see this on the Visit page.": "इलाज करने वाले डॉक्टर भर्ती के समय तय होते हैं। यहाँ भरें कि अभी ड्यूटी पर कौन है और मरीज़ के साथ कौन रुका है। मरीज़ और परिवार यह जानकारी विज़िट पेज पर देखते हैं।",
 "Duty doctor now": "अभी ड्यूटी पर डॉक्टर", "Duty nurse now": "अभी ड्यूटी पर नर्स", "Ward attendant (hospital staff)": "वार्ड अटेंडेंट (अस्पताल स्टाफ)",
 "Morning (8 AM - 2 PM)": "सुबह (सुबह 8 - दोपहर 2 बजे)", "Evening (2 PM - 8 PM)": "शाम (दोपहर 2 - रात 8 बजे)", "Night (8 PM - 8 AM)": "रात (रात 8 - सुबह 8 बजे)",
 "Family attendant staying with the patient": "मरीज़ के साथ रुका परिवार का सदस्य (अटेंडेंट)", "Save care team": "देखभाल दल सहेजें",
 "Care team": "देखभाल दल", "Treating doctor": "इलाज करने वाले डॉक्टर", "Duty doctor": "ड्यूटी डॉक्टर", "Duty nurse": "ड्यूटी नर्स", "Ward attendant": "वार्ड अटेंडेंट", "Family attendant": "परिवार का अटेंडेंट",
 "(as at time of death)": "(मृत्यु के समय की स्थिति)", ", nurse": ", नर्स", ", attendant": ", अटेंडेंट", ", family attendant": ", परिवार का अटेंडेंट", "Care team now: duty doctor": "अभी का देखभाल दल: ड्यूटी डॉक्टर",
 "e.g. Dr. A. Sharma (Resident)": "जैसे डॉ. ए. शर्मा (रेज़िडेंट)", "e.g. Sister R. Singh": "जैसे सिस्टर आर. सिंह", "e.g. Ramu (ward boy)": "जैसे रामू (वार्ड बॉय)", "e.g. Son, Wife": "जैसे बेटा, पत्नी",
 # death form
 "Record death": "मृत्यु दर्ज करें", "Record death and sign certificate": "मृत्यु दर्ज करें और प्रमाण पत्र पर हस्ताक्षर करें",
 "This cannot be edited or deleted after signing. Check every field. The patient record is locked: no new vitals, medicines or lab results can be added afterwards.": "हस्ताक्षर के बाद इसे बदला या मिटाया नहीं जा सकता। हर खाना ध्यान से जाँचें। मरीज़ का रिकॉर्ड लॉक हो जाता है: इसके बाद नई वाइटल्स, दवाइयाँ या लैब रिपोर्ट नहीं जोड़ी जा सकतीं।",
 "Update first": "पहले अपडेट करें", "if wrong: it is copied into the certificate.": "अगर गलत हो: यही प्रमाण पत्र में लिखा जाएगा।",
 "Date and time of death": "मृत्यु की तारीख और समय", "Immediate cause of death": "मृत्यु का तात्कालिक कारण", "Underlying / antecedent cause (if known)": "मूल / पूर्ववर्ती कारण (यदि ज्ञात हो)",
 "Manner of death": "मृत्यु का प्रकार", "Natural": "प्राकृतिक", "Accident": "दुर्घटना", "Suicide": "आत्महत्या", "Homicide": "हत्या", "Pending investigation": "जाँच लंबित", "Could not be determined": "निर्धारित नहीं हो सका",
 "Anything other than Natural is treated as a medico-legal case: the certificate says police intimation is required.": "प्राकृतिक के अलावा कोई भी प्रकार मेडिको-लीगल मामला माना जाता है: प्रमाण पत्र में लिखा जाता है कि पुलिस को सूचना देना आवश्यक है।",
 "Your medical registration number": "आपका चिकित्सा पंजीकरण नंबर", "Your password (this applies your digital signature)": "आपका पासवर्ड (इससे आपका डिजिटल हस्ताक्षर लगता है)",
 "I certify that I personally examined this patient and that the details above are true to the best of my knowledge.": "मैं प्रमाणित करता/करती हूँ कि मैंने इस मरीज़ की स्वयं जाँच की है और ऊपर दी गई जानकारी मेरी जानकारी में सही है।",
 "Record death and sign": "मृत्यु दर्ज करें और हस्ताक्षर करें", "e.g. Cardio-respiratory arrest": "जैसे हृदय-श्वसन गति रुकना", "e.g. Acute myocardial infarction": "जैसे तीव्र हृदयाघात (हार्ट अटैक)",
 # visit page after death
 "Death recorded": "मृत्यु दर्ज की गई", "We are deeply sorry for your loss. The hospital has recorded the death and prepared a digitally signed certificate.": "आपकी क्षति के लिए हमें गहरा खेद है। अस्पताल ने मृत्यु दर्ज कर दी है और डिजिटल हस्ताक्षर वाला प्रमाण पत्र तैयार किया है।",
 "Time of death:": "मृत्यु का समय:", "Stayed in hospital:": "अस्पताल में रहे:", "Certificate no:": "प्रमाण पत्र संख्या:", "View / print certificate": "प्रमाण पत्र देखें / प्रिंट करें", "deceased": "मृत्यु हो चुकी है",
 # certificate
 "Sanjay Gandhi Memorial Hospital, Rewa (M.P.)": "संजय गांधी स्मारक चिकित्सालय, रीवा (म.प्र.)",
 "Digitally signed death summary and cause-of-death certificate": "डिजिटल हस्ताक्षर वाला मृत्यु सारांश और मृत्यु-कारण प्रमाण पत्र",
 "Scan to verify": "जाँचने के लिए स्कैन करें", "DEATH CERTIFICATE (HOSPITAL RECORD)": "मृत्यु प्रमाण पत्र (अस्पताल रिकॉर्ड)", "Certificate no.": "प्रमाण पत्र संख्या",
 "Name of the deceased": "मृतक का नाम", "UHID": "UHID", "Ward / bed": "वार्ड / बिस्तर", "Date and time of admission": "भर्ती की तारीख और समय", "Period of stay in hospital": "अस्पताल में रहने की अवधि",
 "Underlying cause": "मूल कारण", "Duty doctor at the time": "उस समय ड्यूटी डॉक्टर", "Duty nurse at the time": "उस समय ड्यूटी नर्स", "Family attendant present": "उपस्थित परिवार का अटेंडेंट",
 "Integrity check now:": "अभी की अखंडता जाँच:", "VALID. The record has not been altered.": "मान्य। रिकॉर्ड में कोई बदलाव नहीं हुआ है।", "FAILED. The record does not match its signature. Do not accept.": "विफल। रिकॉर्ड हस्ताक्षर से मेल नहीं खाता। इसे स्वीकार न करें।",
 "Important:": "महत्वपूर्ण:",
 "this is the hospital's digitally signed death summary for the family and the hospital's record. The statutory death certificate is issued by the Registrar of Births and Deaths after the death is registered; the family should register the death within the time allowed by law and use the hospital's cause-of-death certificate for it. The digital signature shows the text was not changed after signing; it is not a legal Digital Signature Certificate.": "यह परिवार और अस्पताल के रिकॉर्ड के लिए अस्पताल का डिजिटल हस्ताक्षर वाला मृत्यु सारांश है। कानूनी मृत्यु प्रमाण पत्र मृत्यु पंजीकृत होने के बाद जन्म-मृत्यु पंजीयक द्वारा जारी किया जाता है; परिवार को कानून में तय समय के भीतर मृत्यु का पंजीकरण कराना चाहिए और उसके लिए अस्पताल का मृत्यु-कारण प्रमाण पत्र उपयोग करना चाहिए। डिजिटल हस्ताक्षर केवल यह दिखाता है कि हस्ताक्षर के बाद पाठ नहीं बदला गया; यह कानूनी डिजिटल सिग्नेचर सर्टिफिकेट नहीं है।",
 "Verify certificate": "प्रमाण पत्र जाँचें",
 # verify page
 "Certificate verification": "प्रमाण पत्र सत्यापन", "GENUINE.": "असली।", "This certificate was issued by the Smart SGMH system and has not been altered since signing.": "यह प्रमाण पत्र Smart SGMH प्रणाली द्वारा जारी किया गया है और हस्ताक्षर के बाद इसमें कोई बदलाव नहीं हुआ है।",
 "Hospital": "अस्पताल", "Signed by": "हस्ताक्षरकर्ता", "Issued": "जारी", "Certificate no.": "प्रमाण पत्र संख्या",
 "This is the hospital's death summary, not the statutory death certificate issued by the Registrar. Prototype system; confirm with the hospital for official use.": "यह अस्पताल का मृत्यु सारांश है, पंजीयक द्वारा जारी कानूनी मृत्यु प्रमाण पत्र नहीं। यह प्रोटोटाइप प्रणाली है; आधिकारिक उपयोग के लिए अस्पताल से पुष्टि करें।",
}

_D = lambda p, r, f=0: (re.compile(p, f), r)
PATTERNS = [
 _D(r"^Updated\b", "अपडेट"), _D(r"^Last updated (.+) by (.+)$", r"अंतिम अपडेट \1, द्वारा \2"),
 _D(r"(\d+) days? (\d+) hours?", r"\1 दिन \2 घंटे"), _D(r"\(admitted ", "(भर्ती: "),
 _D(r"\(spread over (\d+) calendar days?\)", r"(\1 कैलेंडर दिनों में फैला)"),
 _D(r"\(Bed ([^)]+)\)", r"(बिस्तर \1)"), _D(r"\bBed (\S+)", r"बिस्तर \1"),
 _D(r"\((Morning|Evening|Night)\)", lambda m: "(" + {"Morning": "सुबह", "Evening": "शाम", "Night": "रात"}[m.group(1)] + ")"),
 _D(r"\((Reg\. ?(?:no\.)?) ", "(पंजीकरण सं. "),
 _D(r"^Care team:", "देखभाल दल:"), _D(r"^Death certificate (\S+)$", r"मृत्यु प्रमाण पत्र \1"),
 _D(r"^Digitally signed by (.+)$", r"\1 द्वारा डिजिटल हस्ताक्षरित"), _D(r"signature (\S+)", r"हस्ताक्षर \1"),
 _D(r"&middot; Issued ", "&middot; जारी "), _D(r"^Verify online:", "ऑनलाइन जाँचें:"),
 _D(r"^Admitted:", "भर्ती:"), _D(r"Treating doctor:", "इलाज करने वाले डॉक्टर:"), _D(r"\bCode (IP-\S+)", r"कोड \1"),
 _D(r"^UHID (\S+)$", r"UHID \1"),
 _D(r"(\d+) yrs?\b", r"\1 वर्ष"), _D(r"(\d+) y\b", r"\1 वर्ष"), _D(r"\bMale\b", "पुरुष"), _D(r"\bFemale\b", "महिला"),
 _D(r"\((Wife|Husband|Son|Daughter|Father|Mother|Brother|Sister|Friend|Relative|Neighbour)\)", lambda m: "(" + {"Wife": "पत्नी", "Husband": "पति", "Son": "बेटा", "Daughter": "बेटी", "Father": "पिता", "Mother": "माता", "Brother": "भाई", "Sister": "बहन", "Friend": "मित्र", "Relative": "रिश्तेदार", "Neighbour": "पड़ोसी"}[m.group(1)] + ")"),
 _D(r"^Planned:", "योजनाबद्ध:"), _D(r"^Urgent:", "ज़रूरी:"),
 _D(r"\b(General ward|Private room|Maternity ward|Paediatric ward)\b", lambda m: {"General ward": "जनरल वार्ड", "Private room": "प्राइवेट रूम", "Maternity ward": "प्रसूति वार्ड", "Paediatric ward": "बाल रोग वार्ड"}[m.group(1)]),
 _D(r"\((Medicine|Orthopaedics|Paediatrics|Gynaecology|Cardiology|ENT)\)", lambda m: "(" + {"Medicine": "मेडिसिन", "Orthopaedics": "हड्डी रोग", "Paediatrics": "बाल रोग", "Gynaecology": "स्त्री रोग", "Cardiology": "कार्डियोलॉजी", "ENT": "कान-नाक-गला"}[m.group(1)] + ")"),
]
