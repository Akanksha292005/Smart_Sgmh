import { useState } from "react";
import { Link, useNavigate, useParams, useLocation } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { api, getAuth, setAuth } from "./api";
import { useT } from "./i18n";
import { motion, AnimatePresence } from "framer-motion";
import QRCode from "react-qr-code";
import { Check, Printer, Clock } from "lucide-react";
import { Page, Card, Btn, Err, Skeleton } from "./ui";



export const HELPLINE = "07662-241655"; // hospital main number (individual doctor numbers are not public)
// Official photo from the hospital website; falls back to initials if the image can't load
const slug = (n) => n.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
function Avatar({ d }) {
  // 1) local file (download_photos.py)  2) official site URL  3) initials
  const srcs = [`${import.meta.env.BASE_URL}doctors/${slug(d.name)}.jpg`, d.photo && encodeURI(d.photo)].filter(Boolean);
  const [i, setI] = useState(0);
  const ini = d.name.replace(/^Dr\.?\s*/i, "").split(" ").map((w) => w[0]).slice(0, 2).join("");
  return i >= srcs.length
    ? <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center font-bold shrink-0">{ini}</div>
    : <img key={i} src={srcs[i]} alt={d.name} referrerPolicy="no-referrer" onError={() => setI(i + 1)} className="w-16 h-16 rounded-full object-cover object-top shrink-0 bg-slate-100" />;
}
export function DoctorCard({ d, selected, onSelect }) {
  const off = d.code === "leave";
  return (
    <div onClick={() => !off && onSelect?.(d.id)}
      className={"flex gap-3 border rounded-xl p-3 bg-white " + (onSelect && !off ? "cursor-pointer hover:border-emerald-500 " : "") + (selected ? "border-emerald-600 ring-2 ring-emerald-200 " : "") + (off ? "opacity-50" : "")}>
      <Avatar d={d} />
      <div className="text-sm min-w-0">
        <div className="font-semibold text-base">{d.name}</div>
        <div className="text-emerald-700">{d.dept} · {d.designation}</div>
        <div className="text-slate-600">{d.degree}</div>
        <div className="text-slate-600">OPD {d.days || "Mon–Sat"}, {d.dept === "Paediatrics" ? "8:30 AM–1:30 PM" : "8 AM–4 PM"} · <span style={{ color: d.color }}>{d.label}</span></div>
        {d.room && <div className="text-slate-600">Sits in: <b>{d.room}</b></div>}
        {d.nxt && <div className="text-slate-600">Next free slot: <b>{d.nxt.when} {d.nxt.slot}</b></div>}
        <a href={"tel:" + HELPLINE.replace(/-/g, "")} onClick={(e) => e.stopPropagation()} className="text-emerald-700 underline">☎ {HELPLINE}</a>
      </div>
    </div>);
}

// Public page (no login): all doctors grouped by department
export function Doctors() {
  const { data } = useQuery({ queryKey: ["docs-all"], queryFn: () => api("/doctors") });
  const [dept, setDept] = useState("All");
  const depts = ["All", ...new Set(data?.map((d) => d.dept))];
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Our doctors</h1>
      <div className="flex flex-wrap gap-2">{depts.map((x) => (
        <button key={x} onClick={() => setDept(x)} className={"px-3 py-1 rounded-full border text-sm " + (dept === x ? "bg-emerald-600 text-white" : "bg-white")}>{x}</button>))}</div>
      <div className="grid sm:grid-cols-2 gap-3">{data?.filter((d) => dept === "All" || d.dept === dept).map((d) => <DoctorCard key={d.id} d={d} />)}</div>
      <p className="text-xs text-slate-500">Names, designations, degrees and photos are taken from the official hospital website. Slots shown are from this app's booking system. Call the hospital number for exact OPD schedules.</p>
    </div>);
}

export function Login({ staffOnly = false }) {
  const [f, setF] = useState({ phone: "", password: "" }), nav = useNavigate();
  const m = useMutation({ mutationFn: () => api("/login", f), onSuccess: (d) => {
    if (staffOnly && d.user.role === "patient") { setAuth(null); return; }
    setAuth(d);
    // Staff dashboards are served by Flask on this same server; patients stay in the React portal.
    if (d.user.role === "doctor") window.location.assign("/doctor");
    else if (d.user.role === "admin") window.location.assign("/admin");
    else if (["reception", "lab", "pharmacy", "nurse"].includes(d.user.role)) window.location.assign(({ reception: "/reception", lab: "/lab", pharmacy: "/pharmacy", nurse: "/vitals" })[d.user.role]);
    else nav("/me");
  } });
  if (!staffOnly) return <Card className="max-w-lg mx-auto mt-10 space-y-4">
    <h1 className="text-xl font-bold">Patient login / registration</h1>
    <p className="text-sm text-slate-600">Patients use the secure OTP-based login and registration flow. Staff accounts cannot sign in from this public page.</p>
    <a href="/start" className="block text-center rounded-xl bg-emerald-700 text-white font-semibold px-4 py-3">Continue to patient OTP login</a>
    <p className="text-xs text-slate-500">For privacy, patient records are available only after verifying your identity.</p>
  </Card>;
  return <Card className="max-w-sm mx-auto mt-10 space-y-3">
    <h1 className="text-xl font-bold">Authorized staff sign-in</h1>
    <p className="text-sm text-slate-500">Private access for approved hospital staff. This page is not linked from the public navigation.</p>
    <input autoComplete="username" className="border rounded w-full p-2" placeholder="Registered staff phone" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
    <input autoComplete="current-password" className="border rounded w-full p-2" type="password" placeholder="Password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} onKeyDown={(e) => { if (e.key === "Enter") m.mutate(); }} />
    <Btn onClick={() => m.mutate()} className="w-full">Sign in</Btn><Err e={m.error} />
  </Card>;
}

export function Home() {
  const { t } = useT(), { user } = getAuth();
  const { data } = useQuery({ queryKey: ["mine"], queryFn: () => api("/appointments"), enabled: user.role === "patient" });
  if (user.role !== "patient") return <Card>Welcome, {user.name}. {user.role === "admin" ? <Link className="text-emerald-700 underline" to="/admin">Open dashboard</Link> : "Staff screens for this role are still on the Flask pages (port 5000)."}</Card>;
  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center"><h1 className="text-xl font-bold">{t("my_appts")}</h1><Link to="/book"><Btn>+ Book OPD</Btn></Link></div>
      {data?.map((a) => (
        <Link key={a.code} to={"/visit/" + a.code}><Card className="flex justify-between hover:border-emerald-600 mb-2">
          <div><b>{a.doctor}</b><div className="text-sm text-slate-500">{a.dept} · {a.date} {a.slot}</div></div>
          <span className="text-sm bg-emerald-50 text-emerald-800 rounded px-2 py-1 h-fit">{a.status}</span></Card></Link>))}
      {data?.length === 0 && <p className="text-slate-500">No appointments yet.</p>}
    </div>);
}

export function Book() {
  const { t } = useT(), nav = useNavigate(), today = new Date().toISOString().slice(0, 10);
  const [step, setStep] = useState(0), [reason, setReason] = useState(useLocation().state?.reason || ""), [doc, setDoc] = useState(null), [date, setDate] = useState(today), [slot, setSlot] = useState("");
  const sug = useQuery({ queryKey: ["sug", reason], queryFn: () => api("/suggest?reason=" + encodeURIComponent(reason)), enabled: reason.length > 2 });
  const docs = useQuery({ queryKey: ["docs", sug.data?.dept], queryFn: () => api("/doctors" + (sug.data?.dept ? "?dept=" + sug.data.dept : "")) });
  const slots = useQuery({ queryKey: ["slots", doc, date], queryFn: () => api(`/slots?doctor=${doc}&date=${date}`), enabled: !!doc });
  const m = useMutation({ mutationFn: () => api("/book", { reason, doctor: doc, date, slot }), onSuccess: (d) => nav("/visit/" + d.code) });
  const chosen = docs.data?.find((d) => d.id === doc);
  const can = [reason.length > 2 && !sug.data?.emergency, !!doc, !!slot, true][step];
  const labels = [t("s_problem"), t("s_doctor"), t("s_slot"), t("s_confirm")];
  return (
    <Page><div className="opd-book space-y-5 max-w-4xl mx-auto">
      <div className="opd-book-hero"><div><span className="opd-eyebrow">SGMH REWA · AROGYA PATH</span><h1>Book your OPD visit</h1><p>Choose a department, select your doctor and reserve a convenient time slot.</p></div><div className="opd-hero-icon">✚</div></div>
      <div className="opd-steps">{labels.map((l, i) => (
        <div key={l} className={"opd-step " + (i === step ? "is-active " : "") + (i < step ? "is-done" : "")}><span className="opd-step-number">{i < step ? "✓" : i + 1}</span><span>{l}</span></div>))}</div>
      <AnimatePresence mode="wait"><motion.div key={step} initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} transition={{ duration: 0.2 }}>
        {step === 0 && <Card className="opd-panel"><h2 className="opd-panel-title">{t("problem_q")}</h2><p className="opd-help">Describe the main concern in a few words. This suggestion is not a diagnosis.</p>
          <textarea rows={4} className="opd-field opd-textarea border rounded-xl w-full p-3 focus:ring-2 ring-emerald-200 outline-none" placeholder="bukhar, chest pain, bache ko khansi…" value={reason} onChange={(e) => setReason(e.target.value)} />
          {sug.data?.emergency && <p className="mt-3 bg-red-50 text-red-700 border border-red-200 p-3 rounded-xl">Possible emergency: go to the SGMH Emergency gate or call 112 now.</p>}
          {sug.data?.dept && !sug.data.emergency && <p className="mt-3 text-sm bg-emerald-50 text-emerald-800 rounded-xl p-3">Suggested department: <b>{sug.data.dept}</b></p>}</Card>}
        {step === 1 && <div className="opd-doctor-step space-y-3"><div className="opd-section-heading"><div><span className="opd-eyebrow">STEP 02</span><h2>{t("choose_doc")}</h2></div><span className="opd-count">{docs.data?.length || 0} doctors</span></div>
          {docs.isLoading && <Skeleton className="h-24" />}
          <div className="grid sm:grid-cols-2 gap-3">{docs.data?.map((d) => <DoctorCard key={d.id} d={d} selected={doc === d.id} onSelect={(id) => { setDoc(id); setSlot(""); }} />)}</div></div>}
        {step === 2 && <Card className="opd-panel"><h2 className="opd-panel-title">{t("pick_slot")}</h2>
          <label className="opd-label" htmlFor="opd-date">Appointment date</label><input id="opd-date" type="date" min={today} value={date} onChange={(e) => { setDate(e.target.value); setSlot(""); }} className="opd-field border rounded-xl p-2 mb-4" />
          <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">{slots.data?.map((s) => (
            <button key={s.slot} disabled={s.state !== "free"} onClick={() => setSlot(s.slot)}
              className={"py-2 rounded-lg border text-sm transition disabled:opacity-30 disabled:line-through " + (slot === s.slot ? "bg-emerald-600 text-white border-emerald-600" : "hover:border-emerald-500")}>{s.slot}</button>))}</div></Card>}
        {step === 3 && <Card className="opd-panel space-y-3"><span className="opd-eyebrow">FINAL STEP</span><h2 className="opd-panel-title">{t("s_confirm")}</h2>
          <p><b>{chosen?.name}</b> · {chosen?.dept}</p><p className="flex items-center gap-2"><Clock size={16} /> {date} · {slot}</p><p className="text-slate-500 text-sm">“{reason}”</p></Card>}
      </motion.div></AnimatePresence>
      <div className="opd-actions flex justify-between"><Btn variant="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>{t("back")}</Btn>
        {step < 3 ? <Btn disabled={!can} onClick={() => setStep(step + 1)}>{t("next")}</Btn> : <Btn disabled={m.isPending} onClick={() => m.mutate()}>{t("confirm")}</Btn>}</div>
      <Err e={m.error} />
    </div></Page>);
}

// Live patient journey: React Query re-fetches every 4 s
export function Visit() {
  const { t } = useT(), { code } = useParams();
  const { data: v, error } = useQuery({ queryKey: ["visit", code], queryFn: () => api("/visit/" + code), refetchInterval: 4000 });
  if (error) return <Err e={error} />;
  if (!v) return <div className="space-y-3"><Skeleton className="h-40" /><Skeleton className="h-64" /></div>;
  const done = new Set(v.events.map((e) => e.cp)), pct = Math.round((v.cps.filter((c) => done.has(c)).length / v.cps.length) * 100);
  return (
    <Page><div className="space-y-4 max-w-2xl mx-auto">
      <div className="rounded-2xl bg-gradient-to-br from-[#134a8a] to-[#0d3d75] text-white p-5 flex justify-between gap-4">
        <div>
          <span className="inline-flex items-center gap-1.5 text-xs bg-white/15 rounded-full px-2 py-0.5"><span className="w-2 h-2 rounded-full bg-green-300 animate-pulse" />{t("live")}</span>
          <h1 className="text-2xl font-bold mt-2">{v.doctor}</h1><p className="text-sm opacity-90">{v.dept} · {v.date} · {v.slot}</p><p className="text-xs opacity-70">{code} · Token {v.token ?? "-"}</p>
          {v.pos != null && <div className="mt-4 flex gap-8">
            <div><div className="text-4xl font-bold">{v.pos}</div><div className="text-xs opacity-80">{t("queue_pos")}</div></div>
            <div><div className="text-4xl font-bold">{v.est_min}<span className="text-lg"> min</span></div><div className="text-xs opacity-80">{t("est_wait")}</div></div></div>}
        </div>
        <div className="bg-[#ffffff] p-2 rounded-xl h-fit shrink-0"><QRCode value={code} size={92} /></div>
      </div>
      {v.stale && <p className="bg-amber-50 text-amber-800 border border-amber-200 rounded-xl p-3 text-sm">No update for a while. Please check at the reception.</p>}
      <Card><div className="flex justify-between items-center mb-3"><h2 className="font-semibold">{t("journey")}</h2><span className="text-sm text-emerald-700 font-medium">{pct}%</span></div>
        <div className="h-2 rounded-full bg-slate-100 overflow-hidden mb-5"><motion.div className="h-full bg-gradient-to-r from-emerald-500 to-teal-500" initial={{ width: 0 }} animate={{ width: pct + "%" }} transition={{ duration: 0.8 }} /></div>
        <ol>{v.cps.map((cp, i) => (
          <motion.li key={cp} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }} className="flex gap-3">
            <div className="flex flex-col items-center"><span className={"w-6 h-6 rounded-full flex items-center justify-center " + (done.has(cp) ? "bg-emerald-600 text-white" : "bg-slate-200")}>{done.has(cp) && <Check size={14} />}</span>
              {i < v.cps.length - 1 && <span className={"w-0.5 h-6 " + (done.has(cp) ? "bg-emerald-300" : "bg-slate-200")} />}</div>
            <span className={"pb-5 " + (done.has(cp) ? "font-medium" : "text-slate-400")}>{cp}</span></motion.li>))}</ol></Card>
      {v.samples?.length > 0 && <Card><h2 className="font-semibold mb-2">Lab tests</h2>{v.samples.map((s) => <p key={s.barcode} className="flex justify-between border-b last:border-0 py-1.5">{s.test}<b className="text-emerald-700">{s.status}</b></p>)}</Card>}
      {v.advice && <Card><h2 className="font-semibold mb-2">Doctor's advice</h2><pre className="whitespace-pre-wrap font-sans text-sm">{v.advice}</pre>
        <Btn variant="ghost" className="mt-3 print:hidden" onClick={() => window.print()}><Printer size={16} />{t("print")}</Btn></Card>}
    </div></Page>);
}

export function Assistant() {
  const [q, setQ] = useState(""), [log, setLog] = useState([]);
  const m = useMutation({ mutationFn: (t) => api("/ask", { q: t, lang: localStorage.getItem("lang") || "en" }), onSuccess: (d, t) => setLog((l) => [...l, { q: t, a: d.answer, emergency: d.emergency }]) });
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-bold">Hospital assistant</h1>
      <p className="text-sm text-slate-500">Answers only from hospital-approved information. No diagnosis. Emergency: call 112 / 108.</p>
      {log.map((x, i) => <Card key={i}><p className="font-medium">{x.q}</p><p className={"mt-1 " + (x.emergency ? "text-red-700" : "")}>{x.a}</p></Card>)}
      <div className="flex gap-2">
        <input className="border rounded p-2 flex-1" placeholder="Ask: OPD timing, blood bank…" value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && q && (m.mutate(q), setQ(""))} />
        <Btn onClick={() => { m.mutate(q); setQ(""); }} disabled={!q}>Ask</Btn></div>
    </div>);
}
