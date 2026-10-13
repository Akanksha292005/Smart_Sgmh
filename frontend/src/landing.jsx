import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Info, Brain, Sparkles, Camera, CalendarCheck, Stethoscope, Search, FlaskConical, Pill, Bot, Siren, Clock, MapPin, Building2, UserRound, ClipboardList, Droplets, BedDouble, Activity,
  Scan, HeartPulse, Phone, Mail, ChevronDown, ArrowRight } from "lucide-react";
import { api, getAuth } from "./api";
import { useT } from "./i18n";
import { Page } from "./ui";
import { H, NOTICES, DEPT_GROUPS, FACILITIES, FAQS } from "./data/hospital";

const BASE = import.meta.env.BASE_URL;
const Sec = ({ id, title, sub, children }) => (
  <section id={id} className="scroll-mt-28">
    <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-60px" }}>
      <div className="mb-5"><h2 className="text-2xl font-bold text-slate-800">{title}</h2><div className="h-1 w-14 bg-emerald-500 rounded mt-2" />{sub && <p className="text-slate-500 mt-2 max-w-2xl">{sub}</p>}</div>
      {children}</motion.div></section>);

const SERVICES = [ // [icon, label, hint, to, colour]
  [CalendarCheck, "Book OPD", "Choose doctor & slot", "/book", "teal"], [Search, "Track patient", "Where is my patient?", "/track", "sky"],
  [UserRound, "Find a doctor", "Photos, degrees, slots", "/doctors", "indigo"], [ClipboardList, "My visits", "Queue, QR, advice", "/me", "emerald"],
  [FlaskConical, "Lab services", "Tests & preparation", "/lab-services", "violet"], [Pill, "Medical store", "Medicine stock", "/medical-store", "amber"],
  [Brain, "AI triage", "Which OPD should I visit?", "/triage", "cyan"], [Siren, "Emergency 24x7", "Call 112 / 108", "tel:112", "red"],
  [Clock, "OPD timings", "Mon–Sat, 8 AM–4 PM", "/#timings", "orange"], [Building2, "Departments", "All clinical departments", "/#departments", "blue"],
  [Info, "Help & FAQ", "Quick answers", "/#faq", "rose"], [MapPin, "How to reach", "Open in Google Maps", H.map, "lime"]];
const tone = { teal: "bg-emerald-50 text-emerald-700", sky: "bg-sky-50 text-sky-700", indigo: "bg-indigo-50 text-indigo-700", emerald: "bg-emerald-50 text-emerald-700", violet: "bg-violet-50 text-violet-700",
  amber: "bg-amber-50 text-amber-700", cyan: "bg-teal-50 text-teal-700", red: "bg-red-50 text-red-700", orange: "bg-orange-50 text-orange-700", blue: "bg-blue-50 text-blue-700", rose: "bg-rose-50 text-rose-700", lime: "bg-lime-50 text-lime-700" };
const A = ({ to, ...p }) => (/^(https?:|tel:)/.test(to) ? <a href={to} {...p} /> : <Link to={to} {...p} />);

export default function Landing() {
  const { t } = useT(), a = getAuth(), [open, setOpen] = useState(0);
  const { data } = useQuery({ queryKey: ["docs-all"], queryFn: () => api("/doctors") });
  const nDept = Object.values(DEPT_GROUPS).flat().length;
  const icons = [BedDouble, Activity, Droplets, Scan];
  return (
    <Page><div className="space-y-14">
      <div className="overflow-hidden rounded-xl bg-emerald-950/70 border border-emerald-400/20 text-emerald-50 text-sm py-2"><motion.div className="whitespace-nowrap flex gap-16 w-max" animate={{ x: ["0%", "-50%"] }} transition={{ duration: 30, repeat: Infinity, ease: "linear" }}>
        {[...NOTICES, ...NOTICES].map((n, i) => <span key={i} className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-amber-300" />{n}</span>)}</motion.div></div>

      <section className="rounded-3xl bg-emerald-950/80 border border-emerald-400/20 shadow-[0_0_90px_-25px_rgba(16,185,129,.55)] text-white p-8 sm:p-14 relative overflow-hidden">
        <div className="absolute inset-0 bg-cover bg-center opacity-30" style={{ backgroundImage: `url(${BASE}hospital/hero.jpg)` }} />
        <div className="absolute -right-24 -top-24 w-96 h-96 rounded-full bg-amber-400/25 blur-3xl" /><div className="absolute -left-20 bottom-0 w-96 h-96 rounded-full bg-emerald-400/20 blur-3xl" />
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="hidden lg:block absolute right-10 top-16 w-72 rounded-2xl border border-white/15 bg-black/30 backdrop-blur-xl p-4 shadow-2xl">
          <div className="flex items-center gap-2 text-xs text-emerald-200"><Brain size={14} className="text-amber-300" />AI triage · live example</div>
          <div className="mt-2 text-sm bg-white/10 rounded-lg p-2">“bache ko bukhar aur khansi”</div>
          {[["Paediatrics", 91], ["Medicine", 4], ["ENT", 2]].map(([d, v], i) => (<div key={d} className="mt-3"><div className="flex justify-between text-xs"><span>{d}</span><span>{v}%</span></div>
            <div className="h-1.5 rounded-full bg-white/10 mt-1"><motion.div className={"h-full rounded-full " + (i ? "bg-white/30" : "bg-gradient-to-r from-emerald-400 to-amber-300")} initial={{ width: 0 }} animate={{ width: v + "%" }} transition={{ delay: 0.8, duration: 0.8 }} /></div></div>))}
          <div className="mt-3 text-[10px] text-emerald-200/70">Assistive routing, not a diagnosis</div></motion.div>
        <div className="relative">
        <span className="inline-flex items-center gap-2 text-xs bg-white/10 border border-white/20 backdrop-blur rounded-full px-3 py-1"><Stethoscope size={14} className="text-amber-300" />{t("hero_tag")}</span>
        <h1 className="text-3xl sm:text-6xl font-extrabold mt-5 max-w-3xl leading-[1.1]">Sanjay Gandhi <span className="bg-gradient-to-r from-amber-300 to-orange-400 bg-clip-text text-transparent">Memorial Hospital</span>, Rewa</h1>
        <p className="mt-4 max-w-xl text-emerald-50/90">{t("hero_title")}</p>
        <div className="mt-7 flex flex-wrap gap-3">
          <Link to={a ? "/book" : "/login"} className="bg-gradient-to-r from-amber-400 to-orange-500 text-emerald-950 font-bold rounded-xl px-6 py-3 inline-flex items-center gap-2 hover:shadow-lg hover:shadow-amber-500/30 transition">{t("book_cta")} <ArrowRight size={18} /></Link>
          <Link to="/triage" className="border border-white/30 bg-white/10 backdrop-blur rounded-xl px-6 py-3 inline-flex items-center gap-2 hover:bg-white/20 transition"><Brain size={18} />Try AI triage</Link></div>
        <div className="mt-10 grid grid-cols-2 sm:grid-cols-4 gap-3">{[["1100", "Beds"], [nDept + "+", "Departments"], [data?.length ?? "-", "Doctors on app"], ["24x7", "Emergency"]].map(([n, l]) => (
          <div key={l} className="bg-white/10 border border-white/15 backdrop-blur rounded-2xl p-4"><div className="text-3xl font-bold text-amber-300">{n}</div><div className="text-xs text-emerald-100">{l}</div></div>))}</div></div>
      </section>

      <Sec id="services" title="Quick services" sub="Everything a patient or family needs, one tap away.">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">{SERVICES.map(([I, l, h, to, c], i) => (
          <motion.div key={l} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: (i % 4) * 0.06 }}>
            <A to={to} className="group block h-full bg-white rounded-2xl border border-slate-200 p-4 hover:-translate-y-1 hover:shadow-lg hover:border-emerald-300 transition">
              <div className={"w-12 h-12 rounded-2xl flex items-center justify-center mb-3 group-hover:scale-110 transition " + tone[c]}><I size={24} /></div>
              <div className="font-semibold">{l}</div><div className="text-xs text-slate-500 mt-0.5">{h}</div></A></motion.div>))}</div>
      </Sec>

      <Sec id="ai" title="AI-powered care" sub="Machine learning that works quietly in the background to save time. Assistive only, never a diagnosis.">
        <div className="grid md:grid-cols-3 gap-4">{[[Brain, "AI symptom triage", "ML model reads Hindi/English/Hinglish symptoms and suggests the right OPD with a confidence score.", "/triage"],
          [Sparkles, "Delay-risk alerts", "Compares each patient's time at a stage with the usual time and flags unusual waits to the supervisor.", "/admin"],
          [Camera, "Smart assistant", "Answers hospital questions only from approved information, with emergency red-flag handling.", "/assistant"]].map(([I, n, d, to]) => (
          <Link key={n} to={to} className="group rounded-2xl p-5 bg-gradient-to-br from-emerald-900 to-emerald-950 text-white hover:-translate-y-1 hover:shadow-xl transition"><div className="w-11 h-11 rounded-xl bg-amber-400/20 text-amber-300 flex items-center justify-center mb-3"><I size={22} /></div>
            <div className="font-semibold">{n}</div><p className="text-sm text-emerald-100/80 mt-1">{d}</p></Link>))}</div>
      </Sec>

      <Sec id="gallery" title="Our hospital" sub="A look around the hospital.">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">{["Hospital building", "Emergency entrance", "OPD hall", "Wards", "Laboratory", "Blood bank"].map((c, i) => (
          <div key={c} className={"relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#0f5f4a] to-[#06281f] " + (i === 0 ? "md:col-span-2 md:row-span-2 min-h-56 md:min-h-80" : "min-h-36")}>
            <div className="absolute inset-0 flex items-center justify-center text-emerald-200/30"><Camera size={40} /></div>
            <img src={`${BASE}hospital/${i + 1}.jpg`} alt={c} loading="lazy" onError={(e) => (e.currentTarget.style.display = "none")} className="absolute inset-0 w-full h-full object-cover hover:scale-105 transition duration-500" />
            <div className="absolute bottom-0 inset-x-0 p-3 text-sm font-medium text-white bg-gradient-to-t from-black/70 to-transparent">{c}</div></div>))}</div>
      </Sec>

      <Sec id="about" title={"About " + H.name}>
        <div className="grid md:grid-cols-3 gap-6">
          <p className="md:col-span-2 text-slate-600 leading-relaxed">{H.name} is a 1100-bed government hospital in Rewa, Madhya Pradesh. It provides 24x7 emergency and trauma care, outpatient departments across all major specialities, a blood bank and laboratory services. Arogya Path adds online booking, a live queue, QR check-in and AI-assisted triage so that patients and families spend less time waiting and guessing.</p>
          <div className="bg-white rounded-2xl border p-4 text-sm space-y-2"><div className="font-semibold">At a glance</div>
            <p className="flex gap-2"><Clock size={16} className="mt-0.5 shrink-0" />OPD & IPD: Mon–Sat, 8 AM–4 PM</p><p className="flex gap-2"><Siren size={16} className="mt-0.5 shrink-0" />Emergency: 24x7</p><p className="flex gap-2"><Phone size={16} className="mt-0.5 shrink-0" />{H.phone}</p></div></div>
      </Sec>

      <Sec id="departments" title="Departments" sub={`${nDept} OPD departments, all in one hospital.`}>
        <div className="space-y-6">{Object.entries(DEPT_GROUPS).map(([g, ds]) => (
          <div key={g}><h3 className="font-semibold text-emerald-800 mb-2">{g}</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">{ds.map((d) => (
              <Link key={d} to="/doctors" className="flex items-center gap-2 bg-white border rounded-xl px-3 py-2.5 text-sm hover:border-emerald-500 hover:text-emerald-700 transition"><Stethoscope size={16} className="text-emerald-600 shrink-0" />{d}</Link>))}</div></div>))}</div>
      </Sec>

      <Sec id="timings" title="OPD & IPD timings">
        <div className="grid sm:grid-cols-2 gap-4">{[["General OPD & IPD", "Monday to Saturday", "8:00 AM – 4:00 PM"], ["Emergency & Trauma", "Every day", "24 x 7"]].map(([n, d, tm]) => (
          <div key={n} className="bg-white rounded-2xl border p-5"><div className="text-sm text-slate-500">{n}</div><div className="text-xl font-bold text-emerald-700 mt-1">{tm}</div><div className="text-sm mt-1">{d}</div></div>))}</div>
        <p className="text-sm text-slate-500 mt-3">Sunday: OPD and IPD closed. Emergency stays open.</p>
      </Sec>

      <Sec id="facilities" title="Facilities">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">{FACILITIES.map(([n, d], i) => { const I = icons[i % 4]; return (
          <div key={n} className="flex gap-3 bg-white rounded-2xl border p-4 hover:shadow-md transition"><div className="w-11 h-11 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0"><I size={22} /></div>
            <div><div className="font-semibold">{n}</div><div className="text-sm text-slate-500">{d}</div></div></div>); })}</div>
      </Sec>

      <Sec id="faq" title="Frequently asked questions">
        <div className="space-y-2 max-w-3xl">{FAQS.map(([q, ans], i) => (
          <div key={q} className="bg-white rounded-xl border"><button onClick={() => setOpen(open === i ? -1 : i)} className="w-full flex justify-between items-center p-4 text-left font-medium">{q}<ChevronDown size={18} className={"transition " + (open === i ? "rotate-180" : "")} /></button>
            <AnimatePresence initial={false}>{open === i && <motion.p initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="px-4 pb-4 text-slate-600 text-sm overflow-hidden">{ans}</motion.p>}</AnimatePresence></div>))}</div>
      </Sec>

      <Sec id="contact" title="Contact & how to reach">
        <div className="grid md:grid-cols-2 gap-4"><div className="bg-white rounded-2xl border p-5 space-y-3 text-sm">
          <p className="flex gap-3"><MapPin size={18} className="text-emerald-600 shrink-0" />{H.address}</p><p className="flex gap-3"><Phone size={18} className="text-emerald-600" /><a href={"tel:" + H.phone.replace(/-/g, "")}>{H.phone}</a> (Fax {H.fax})</p>
          <p className="flex gap-3"><Mail size={18} className="text-emerald-600" />{H.email}</p></div>
          <a href={H.map} target="_blank" rel="noreferrer" className="rounded-2xl bg-gradient-to-br from-emerald-100 to-teal-100 border flex flex-col items-center justify-center p-8 hover:shadow-md transition text-emerald-800"><MapPin size={36} /><span className="font-semibold mt-2">Open in Google Maps</span></a></div>
      </Sec>
    </div></Page>);
}
