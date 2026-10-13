import { createContext, useContext, useState } from "react";
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
const Ctx = createContext();
export function LangProvider({ children }) {
  const [lang, setL] = useState(localStorage.getItem("lang") || "en");
  const setLang = (l) => { localStorage.setItem("lang", l); setL(l); };
  return <Ctx.Provider value={{ lang, setLang, t: (k) => D[lang][k] ?? D.en[k] ?? k }}>{children}</Ctx.Provider>;
}
export const useT = () => useContext(Ctx);
