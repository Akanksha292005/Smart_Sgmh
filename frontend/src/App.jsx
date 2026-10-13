import { Routes, Route, Navigate, NavLink, Link, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { HeartPulse, Phone, Mail } from "lucide-react";
import { H, LINKS, DEPT_GROUPS } from "./data/hospital";
import { getAuth, setAuth } from "./api";
import { useT } from "./i18n";
import Landing from "./landing";
import { useAutoTranslate } from "./autoTranslate";
import { Triage } from "./ai";
import { Login, Home, Book, Visit, Assistant, Doctors } from "./pages";
import { Admin } from "./admin";
import { Track, LabServices, MedicalStore } from "./portal";

function Guard({ roles, children }) {
  const a = getAuth();
  if (!a) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(a.user.role)) return <Navigate to="/me" replace />;
  return children;
}
export default function App() {
  const loc = useLocation();
  useEffect(() => { if (loc.hash) setTimeout(() => document.getElementById(loc.hash.slice(1))?.scrollIntoView({ behavior: "smooth" }), 80); else window.scrollTo(0, 0); }, [loc]);
  const a = getAuth(), nav = useNavigate(), { t, lang, setLang } = useT();
  useAutoTranslate(lang);
  const L = ({ to, children }) => to.includes("#") ? <Link to={to} className="px-3 py-1.5 rounded-lg whitespace-nowrap text-slate-600 hover:bg-white/10 hover:text-white transition">{children}</Link> : <NavLink to={to} end className={({ isActive }) => "px-3 py-1.5 rounded-lg whitespace-nowrap transition " + (isActive ? "bg-emerald-50 text-emerald-700 font-medium" : "text-slate-600 hover:bg-slate-100")}>{children}</NavLink>;
  return (
    <div className="min-h-screen bg-grid text-slate-800 flex flex-col">
      <header className="sticky top-0 z-20 shadow-sm">
        <div className="bg-emerald-900 text-emerald-50 text-xs"><div className="max-w-6xl mx-auto px-4 py-1.5 flex flex-wrap items-center gap-x-5 gap-y-1">
          <span className="flex items-center gap-1"><Phone size={12} />{H.phone}</span><span className="hidden sm:flex items-center gap-1"><Mail size={12} />{H.email}</span>
          <span className="text-amber-300 font-medium">Emergency 112 / 108</span>
          <button onClick={() => setLang(lang === "en" ? "hi" : "en")} className="ml-auto border border-emerald-400/50 rounded px-2 py-0.5 hover:bg-white/10">{lang === "en" ? "हिन्दी" : "English"}</button>
          {a ? <button onClick={() => { setAuth(null); nav("/"); }} className="hover:text-amber-300">{t("logout")}</button> : <Link to="/login" className="hover:text-amber-300">Login / Register</Link>}</div></div>
        <div className="backdrop-blur bg-white/95 border-b"><div className="max-w-6xl mx-auto px-4 py-2.5 flex items-center gap-3 text-sm">
          <Link to="/" className="flex items-center gap-2 shrink-0"><span className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-600 to-teal-500 text-white flex items-center justify-center"><HeartPulse /></span>
            <span className="leading-tight"><b className="text-emerald-800 block">SGMH Rewa</b><span className="text-[11px] text-slate-500">Arogya Path · OPD + IPD</span></span></Link>
          <nav className="flex gap-1 overflow-x-auto ml-2">
            <L to="/">Home</L><L to="/#about">About</L><L to="/#departments">Departments</L><L to="/doctors">{t("nav_doctors")}</L><L to="/triage">AI Triage</L><L to="/#facilities">Facilities</L><L to="/#timings">OPD Timings</L><L to="/#contact">Contact</L>
            <L to="/assistant">{t("nav_assistant")}</L>{a?.user.role === "patient" && <L to="/me">{t("nav_mine")}</L>}{a?.user.role === "admin" && <L to="/admin">{t("nav_admin")}</L>}</nav>
          <Link to={a ? "/book" : "/login"} className="ml-auto shrink-0 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl px-4 py-2 font-medium shadow hover:shadow-md">{t("nav_book")}</Link></div></div>
      </header>
      <main className="max-w-6xl w-full mx-auto p-4 flex-1">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/me" element={<Guard><Home /></Guard>} />
          <Route path="/book" element={<Guard roles={["patient"]}><Book /></Guard>} />
          <Route path="/visit/:code" element={<Visit />} />
          <Route path="/track" element={<Track />} />
          <Route path="/lab-services" element={<LabServices />} />
          <Route path="/medical-store" element={<MedicalStore />} />
          <Route path="/admin" element={<Guard roles={["admin"]}><Admin /></Guard>} />
          <Route path="/triage" element={<Triage />} />
          <Route path="/doctors" element={<Doctors />} />
          <Route path="/assistant" element={<Assistant />} />
        </Routes>
      </main>
      <footer className="bg-emerald-950 text-emerald-100 text-sm mt-10"><div className="max-w-6xl mx-auto px-4 py-10 grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
        <div><div className="font-bold text-white text-base">Sanjay Gandhi Memorial Hospital, Rewa</div><p className="mt-2 text-emerald-200/80">{H.address}</p><p className="mt-2">☎ {H.phone}<br />✉ {H.email}</p></div>
        <div><div className="font-semibold text-white mb-2">Quick links</div><ul className="space-y-1"><li><Link to="/book">Book OPD</Link></li><li><Link to="/doctors">Doctors</Link></li><li><Link to="/assistant">AI assistant</Link></li><li><Link to="/#timings">OPD timings</Link></li><li><Link to="/#contact">How to reach</Link></li></ul></div>
        <div><div className="font-semibold text-white mb-2">Departments</div><ul className="space-y-1">{DEPT_GROUPS["OPD departments"].slice(0, 6).map((d) => <li key={d}>{d}</li>)}</ul></div>
        <div><div className="font-semibold text-white mb-2">Important links</div><ul className="space-y-1">{LINKS.map(([n, u]) => <li key={u}><a href={u} target="_blank" rel="noreferrer">{n}</a></li>)}</ul></div></div>
        <div className="border-t border-white/10 text-center text-xs text-emerald-300/70 py-4 px-4">Arogya Path is a prototype built for SGMH Rewa and is not an official hospital website or a medical tool. Hospital facts are taken from the official hospital website. Emergency: 112 / 108.</div></footer>
    </div>);
}
