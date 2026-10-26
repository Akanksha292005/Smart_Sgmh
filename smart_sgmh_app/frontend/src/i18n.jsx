import { createContext, useContext, useEffect, useState } from "react";
import { HI } from "./hi";
import { HI_EXTRA } from "./hi_extra";
const D = {
  en: { nav_home: "Home", nav_doctors: "Doctors", nav_assistant: "Assistant", nav_book: "Book OPD", nav_mine: "My visits", nav_admin: "Admin", logout: "Logout",
    hero_tag: "Sanjay Gandhi Memorial Hospital · Smart patient journey", hero_title: "No crowds. No guessing. Your care, on your phone.",
    hero_sub: "Book OPD, watch your place in the queue live, and get the doctor's advice in simple language.", book_cta: "Book OPD now", find_doc: "Meet our doctors",
    emergency: "Emergency? Go straight to the Emergency gate or call 112 / 108.",
    f1: "Live queue", f1d: "Your token and estimated wait, refreshed every few seconds.", f2: "QR check-in", f2d: "Show the QR at reception. No paper slips.",
    f3: "AI assistant", f3d: "Answers only from hospital-approved information. No diagnosis.", f4: "Hindi + English", f4d: "The full experience in your language.",
    depts: "Departments", doctors_count: "Doctors", s_problem: "Problem", s_doctor: "Doctor", s_slot: "Time", s_confirm: "Confirm", next: "Next", back: "Back",
    confirm: "Confirm booking", problem_q: "What is the problem?", choose_doc: "Choose a doctor", pick_slot: "Pick date and time", queue_pos: "Place in queue", est_wait: "Estimated wait",
    journey: "Your journey", print: "Print", live: "Live", my_appts: "My appointments", book_for: "Book OPD for" },
  hi: { nav_home: "होम", nav_doctors: "डॉक्टर", nav_assistant: "सहायक", nav_book: "OPD बुक करें", nav_mine: "मेरी विज़िट", nav_admin: "एडमिन", logout: "लॉगआउट",
    hero_tag: "SGMH रीवा · स्मार्ट पेशेंट जर्नी", hero_title: "न भीड़, न अनिश्चितता। आपका इलाज, आपके फ़ोन पर।",
    hero_sub: "OPD बुक करें, कतार में अपनी जगह लाइव देखें, और डॉक्टर की सलाह सरल भाषा में पाएँ।", book_cta: "अभी OPD बुक करें", find_doc: "हमारे डॉक्टर देखें",
    emergency: "आपातकाल? सीधे इमरजेंसी गेट जाएँ या 112 / 108 पर कॉल करें।",
    f1: "लाइव कतार", f1d: "आपका टोकन और अनुमानित प्रतीक्षा समय, हर कुछ सेकंड में अपडेट।", f2: "QR चेक-इन", f2d: "रिसेप्शन पर QR दिखाएँ, कागज़ की पर्ची नहीं चाहिए।",
    f3: "AI सहायक", f3d: "सिर्फ़ अस्पताल की मंज़ूर जानकारी से जवाब। कोई निदान नहीं।", f4: "हिन्दी + English", f4d: "पूरा अनुभव आपकी भाषा में।",
    depts: "विभाग", doctors_count: "डॉक्टर", s_problem: "समस्या", s_doctor: "डॉक्टर", s_slot: "समय", s_confirm: "पुष्टि", next: "आगे", back: "पीछे",
    confirm: "बुकिंग पक्की करें", problem_q: "आपको क्या परेशानी है?", choose_doc: "डॉक्टर चुनें", pick_slot: "तारीख और समय चुनें", queue_pos: "कतार में स्थान", est_wait: "अनुमानित प्रतीक्षा",
    journey: "आपकी यात्रा", print: "प्रिंट", live: "लाइव", my_appts: "मेरी अपॉइंटमेंट", book_for: "OPD बुक करें:" },
};

// Reuse the maintained site-wide Hindi dictionary instead of keeping a second
// duplicate-heavy dictionary here. Spread keeps future overrides easy to add.
const WORDS = { ...HI, ...HI_EXTRA,
  "AI Triage": "AI प्राथमिक जाँच",
  "Beds & ICU": "बेड और ICU",
  "OPD Timings": "OPD समय",
  "SGMH Rewa": "एसजीएमएच रीवा",
  "Arogya Path · OPD + IPD": "आरोग्य पथ · OPD + IPD",
  "Doctors on app": "ऐप पर डॉक्टर",
  "OPD: See a Doctor": "OPD: डॉक्टर से मिलें",
  "Choose doctor, then book": "डॉक्टर चुनें, फिर बुक करें",
  "IPD: Hospital Admission": "IPD: अस्पताल में भर्ती",
  "Separate admission process": "अलग भर्ती प्रक्रिया",
  "Track Patient": "मरीज़ की स्थिति देखें",
  "Live queue & location": "लाइव कतार और स्थान",
  "Call 112 / 108": "112 / 108 पर कॉल करें",
  "Everything a patient or family needs, one tap away.": "मरीज़ और परिवार की ज़रूरतें, बस एक टैप पर।",
  "Sanjay Gandhi Memorial Hospital, Rewa": "संजय गांधी स्मारक चिकित्सालय, रीवा",
  "Sanjay Gandhi Memorial Hospital, Rewa is a 1100-bed government hospital in Rewa, Madhya Pradesh. It provides 24x7 emergency and trauma care, outpatient departments across all major specialities, a blood bank and laboratory services. Arogya Path adds online booking, a live queue, QR check-in and AI-assisted triage so that patients and families spend less time waiting and guessing.": "संजय गांधी स्मारक चिकित्सालय, रीवा मध्य प्रदेश का 1100-बेड वाला सरकारी अस्पताल है। यहाँ 24×7 आपातकालीन और ट्रॉमा सेवाएँ, सभी प्रमुख विशेषज्ञताओं की OPD, ब्लड बैंक और प्रयोगशाला सेवाएँ उपलब्ध हैं। आरोग्य पथ ऑनलाइन बुकिंग, लाइव कतार, QR चेक-इन और AI-सहायता से सही OPD चुनने में मदद करता है, ताकि मरीज़ों और उनके परिवारों का प्रतीक्षा समय कम हो।",
};

const Ctx = createContext();
export function LangProvider({ children }) {
  const [lang, setL] = useState(() => localStorage.getItem("lang") === "hi" ? "hi" : "en");
  const setLang = (l) => { localStorage.setItem("lang", l); setL(l); };
  useEffect(() => { document.documentElement.lang = lang === "hi" ? "hi" : "en"; document.title = lang === "hi" ? "आरोग्य पथ · संजय गांधी स्मारक चिकित्सालय, रीवा" : "Arogya Path · Sanjay Gandhi Memorial Hospital, Rewa"; }, [lang]);
  const active = lang === "hi" ? "hi" : "en";
  const translate = (value) => {
    if (active !== "hi" || typeof value !== "string") return value;
    const exact = WORDS[value] ?? D.hi[value] ?? value;
    if (exact !== value) return exact;
    // Translate common labels regardless of capitalization at call sites.
    const key = Object.keys(WORDS).find((word) => word.toLowerCase() === value.toLowerCase());
    return key ? WORDS[key] : value;
  };
  return <Ctx.Provider value={{ lang: active, setLang, t: (k) => D[active][k] ?? D.en[k] ?? k, tx: translate }}>{children}</Ctx.Provider>;
}
export const useT = () => useContext(Ctx);
