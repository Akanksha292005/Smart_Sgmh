import { Routes, Route, Navigate, NavLink, Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { HeartPulse, Phone, Mail, Menu, X } from "lucide-react";
import { H, LINKS, DEPT_GROUPS } from "./data/hospital";
import { getAuth, setAuth } from "./api";
import { useT } from "./i18n";
import Landing from "./landing";
import { Triage } from "./ai";
import { Login, Home, Book, Visit, Assistant, Doctors } from "./pages";
import { Admin } from "./admin";
import { Track, LabServices, MedicalStore } from "./portal";
import Beds from "./Beds";

function Guard({ roles, children }) {
  const a = getAuth();
  if (!a) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(a.user.role)) return <Navigate to="/me" replace />;
  return children;
}
export default function App() {
  const loc = useLocation();
  useEffect(() => { if (loc.hash) setTimeout(() => document.getElementById(loc.hash.slice(1))?.scrollIntoView({ behavior: "smooth" }), 80); else window.scrollTo(0, 0); }, [loc]);
  const a = getAuth(), nav = useNavigate(), { t, tx, lang, setLang } = useT();
  const [open, setOpen] = useState(false);
  useEffect(() => { setOpen(false); }, [loc.pathname, loc.hash]);
  const L = ({ to, children, m }) => { const mc = m ? "block px-3 py-3 text-base " : "px-3 py-1.5 whitespace-nowrap "; return to.includes("#") ? <Link to={to} onClick={() => setOpen(false)} className={mc + "rounded-lg text-slate-600 hover:bg-slate-100 transition"}>{children}</Link> : <NavLink to={to} end onClick={() => setOpen(false)} className={({ isActive }) => mc + "rounded-lg transition " + (isActive ? "bg-emerald-50 text-emerald-700 font-medium" : "text-slate-600 hover:bg-slate-100")}>{children}</NavLink>; };
  const NavLinks = ({ m }) => (<><L m={m} to="/">{tx("Home")}</L><L m={m} to="/#about">{tx("About")}</L><L m={m} to="/#departments">{tx("Departments")}</L><L m={m} to="/doctors">{t("nav_doctors")}</L><L m={m} to="/triage">{tx("AI Triage")}</L><L m={m} to="/beds">{tx("Beds & ICU")}</L><L m={m} to="/#facilities">{tx("Facilities")}</L><L m={m} to="/#timings">{tx("OPD Timings")}</L><L m={m} to="/#contact">{tx("Contact")}</L><L m={m} to="/assistant">{t("nav_assistant")}</L>{a?.user.role === "patient" && <L m={m} to="/me">{t("nav_mine")}</L>}{a?.user.role === "admin" && <L m={m} to="/admin">{t("nav_admin")}</L>}</>);
  return (
    <div className="min-h-screen bg-grid text-slate-800 flex flex-col">
      <header className="sticky top-0 z-20 shadow-sm">
        <div className="bg-emerald-900 text-emerald-50 text-xs"><div className="max-w-6xl mx-auto px-4 py-1.5 flex flex-wrap items-center gap-x-5 gap-y-1">
          <span className="flex items-center gap-1"><Phone size={12} />{H.phone}</span><span className="hidden sm:flex items-center gap-1"><Mail size={12} />{H.email}</span>
          <span className="text-amber-300 font-medium">{tx("Emergency 112 / 108")}</span>
          <button onClick={() => setLang(lang === "en" ? "hi" : "en")} className="ml-auto border border-emerald-400/50 rounded px-2 py-0.5 hover:bg-white/10">{lang === "en" ? "हिन्दी" : "English"}</button>
          {a ? <button onClick={() => { setAuth(null); nav("/"); }} className="hover:text-amber-300">{t("logout")}</button> : <Link to="/login" className="hidden lg:inline hover:text-amber-300">{tx("Login / Register")}</Link>}</div></div>
        <div className="backdrop-blur bg-white/95 border-b"><div className="max-w-6xl mx-auto px-4 py-2.5 flex items-center gap-3 text-sm">
          <Link to="/" className="flex items-center gap-2 shrink-0"><span className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-600 to-teal-500 text-white flex items-center justify-center"><HeartPulse /></span>
            <span className="leading-tight"><b className="text-emerald-800 block">{tx("SGMH Rewa")}</b><span className="hidden min-[380px]:block text-[11px] text-slate-500">{tx("Arogya Path · Smart OPD")}</span></span></Link>
          <nav className="hidden lg:flex gap-1 ml-2"><NavLinks /></nav>
          <a href="/opd" className="ml-auto shrink-0 whitespace-nowrap bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl px-3 sm:px-4 py-2.5 font-medium shadow hover:shadow-md">{t("nav_book")}</a>
          <button type="button" aria-label="Menu" aria-expanded={open} onClick={() => setOpen(!open)} className="lg:hidden shrink-0 w-11 h-11 rounded-xl border border-slate-200 flex items-center justify-center text-slate-700">{open ? <X size={22} /> : <Menu size={22} />}</button></div>
        {open && <div id="sgmh-drawer" className="lg:hidden border-t bg-white max-h-[70vh] overflow-y-auto"><div className="max-w-6xl mx-auto px-3 py-2 grid">
          <NavLinks m />
          <div className="my-1 border-t" />
          {[["Bed Availability / ICU", "/beds"], ["How admission works", "/ipd"], ["Hospital Map", "/navigate"], ["How it works", "/workflow"], ["Blood Bank", "/blood-bank"]].map(([n, u]) => <a key={u} href={u} className="block px-3 py-3 text-base rounded-lg text-slate-600 hover:bg-slate-100">{n}</a>)}
          {a ? <button onClick={() => { setAuth(null); nav("/"); }} className="text-left px-3 py-3 text-base rounded-lg text-slate-600 hover:bg-slate-100">{t("logout")}</button> : <Link to="/login" className="block px-3 py-3 text-base rounded-lg font-medium text-emerald-700 hover:bg-slate-100">{tx("Login / Register")}</Link>}</div></div>}</div>
      </header>
      <main className="max-w-6xl w-full mx-auto p-4 flex-1">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/staff-access" element={<Login staffOnly />} />
          <Route path="/me" element={<Guard><Home /></Guard>} />
          <Route path="/book" element={<Guard roles={["patient"]}><Book /></Guard>} />
          <Route path="/visit/:code" element={<Visit />} />
          <Route path="/track" element={<Track />} />
          <Route path="/lab-services" element={<LabServices />} />
          <Route path="/medical-store" element={<MedicalStore />} />
          <Route path="/admin" element={<Guard roles={["admin"]}><Admin /></Guard>} />
          <Route path="/triage" element={<Triage />} />
          <Route path="/beds" element={<Beds />} />
          <Route path="/doctors" element={<Doctors />} />
          <Route path="/assistant" element={<Assistant />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <footer className="bg-emerald-950 text-emerald-100 text-sm mt-10"><div className="max-w-6xl mx-auto px-4 py-10 grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
        <div><div className="font-bold text-white text-base">{tx("Sanjay Gandhi Memorial Hospital, Rewa")}</div><p className="mt-2 text-emerald-200/80">{H.address}</p><p className="mt-2">☎ {H.phone}<br />✉ {H.email}</p></div>
        <div><div className="font-semibold text-white mb-2">{tx("Quick links")}</div><ul className="space-y-1"><li><Link to="/book">{tx("Book OPD")}</Link></li><li><Link to="/beds">{tx("Bed availability / ICU")}</Link></li><li><Link to="/doctors">{tx("Doctors")}</Link></li><li><Link to="/assistant">{tx("AI assistant")}</Link></li><li><Link to="/#timings">{tx("OPD timings")}</Link></li><li><Link to="/#contact">{tx("How to reach")}</Link></li></ul></div>
        <div><div className="font-semibold text-white mb-2">{tx("Departments")}</div><ul className="space-y-1">{DEPT_GROUPS["OPD departments"].slice(0, 6).map((d) => <li key={d}>{d}</li>)}</ul></div>
        <div><div className="font-semibold text-white mb-2">{tx("Important links")}</div><ul className="space-y-1">{LINKS.map(([n, u]) => <li key={u}><a href={u} target="_blank" rel="noreferrer">{n}</a></li>)}</ul></div></div>
        <div className="border-t border-white/10 text-center text-xs text-emerald-300/70 py-4 px-4">{tx("Arogya Path is a prototype built for SGMH Rewa and is not an official hospital website or a medical tool. Hospital facts are taken from the official hospital website. Emergency: 112 / 108.")}</div></footer>
    </div>);
}
