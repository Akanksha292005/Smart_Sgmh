import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Search, FlaskConical, Pill, Clock, Info } from "lucide-react";
import { api } from "./api";
import { Page, Card, Btn, Err, Skeleton } from "./ui";

const Head = ({ icon: I, title, sub }) => (
  <div className="flex items-center gap-3 mb-5"><div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-700 flex items-center justify-center"><I size={24} /></div>
    <div><h1 className="text-2xl font-bold">{title}</h1><p className="text-sm text-slate-500">{sub}</p></div></div>);
const SearchBox = ({ value, onChange, ph }) => (
  <div className="relative mb-5"><Search size={18} className="absolute left-3 top-3 text-slate-400" />
    <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={ph} className="w-full border rounded-xl pl-10 pr-3 py-2.5 bg-white focus:ring-2 ring-emerald-200 outline-none" /></div>);

// Family tracking without login: appointment code + last 4 digits of the patient's phone
export function Track() {
  const nav = useNavigate(), [f, setF] = useState({ code: "", last4: "" });
  const m = useMutation({ mutationFn: () => api("/track", f), onSuccess: (d) => { sessionStorage.setItem("trackToken", d.token); nav("/visit/" + d.code); } });
  return (
    <Page><div className="max-w-md mx-auto"><Head icon={Search} title="Track patient" sub="See where the patient is and what comes next." />
      <Card className="space-y-3">
        <input className="border rounded-xl w-full p-3 uppercase" placeholder="Appointment code (AP-XXXXX)" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} />
        <input className="border rounded-xl w-full p-3" inputMode="numeric" maxLength={4} placeholder="Last 4 digits of patient's phone" value={f.last4} onChange={(e) => setF({ ...f, last4: e.target.value })} />
        <Btn className="w-full" disabled={!f.code || f.last4.length < 4 || m.isPending} onClick={() => m.mutate()}>Track</Btn><Err e={m.error} />
        <p className="text-xs text-slate-500 flex gap-1.5"><Info size={14} className="shrink-0 mt-0.5" />The code is on the appointment page and QR slip.</p></Card></div></Page>);
}

export function LabServices() {
  const [q, setQ] = useState("");
  const { data, isLoading } = useQuery({ queryKey: ["lab", q], queryFn: () => api("/lab-services?q=" + encodeURIComponent(q)), placeholderData: (p) => p });
  return (
    <Page><Head icon={FlaskConical} title="Lab services" sub="Tests, preparation and expected report time. Times are estimates." />
      <SearchBox value={q} onChange={setQ} ph="Search a test, e.g. CBC, sugar, thyroid" />
      {isLoading && <Skeleton className="h-40" />}
      <div className="space-y-6">{data && Object.entries(data).map(([cat, ts]) => (
        <div key={cat}><h2 className="font-semibold text-emerald-800 mb-2">{cat}</h2>
          <div className="grid sm:grid-cols-2 gap-3">{ts.map((t) => (
            <Card key={t.name} className="!p-4"><div className="font-medium">{t.name}</div>
              <div className="text-sm text-slate-500 mt-1">{t.prep}</div><div className="text-xs mt-2 inline-flex items-center gap-1 bg-violet-50 text-violet-700 rounded-full px-2 py-0.5"><Clock size={12} />Report in {t.tat}</div></Card>))}</div></div>))}
        {data && !Object.keys(data).length && <p className="text-slate-500">No test found.</p>}</div>
      <p className="text-xs text-slate-400 mt-6">Sample catalogue for the prototype. Confirm tests and charges at the hospital lab.</p></Page>);
}

const tone = { "In stock": "bg-emerald-50 text-emerald-700", "Low stock": "bg-amber-50 text-amber-700", "Out of stock": "bg-red-50 text-red-700" };
export function MedicalStore() {
  const [q, setQ] = useState("");
  const { data, isLoading } = useQuery({ queryKey: ["meds", q], queryFn: () => api("/medicines?q=" + encodeURIComponent(q)), placeholderData: (p) => p });
  return (
    <Page><Head icon={Pill} title="Medical store" sub="Check if a medicine is available before you visit." />
      <SearchBox value={q} onChange={setQ} ph="Search a medicine, e.g. paracetamol" />
      {isLoading && <Skeleton className="h-40" />}
      <div className="grid sm:grid-cols-2 gap-3">{data?.map((m) => (
        <Card key={m.name} className="!p-4 flex justify-between items-center"><div><div className="font-medium">{m.name}</div><div className="text-xs text-slate-500">{m.category}</div></div>
          <span className={"text-xs rounded-full px-3 py-1 font-medium " + tone[m.status]}>{m.status}</span></Card>))}</div>
      {data && !data.length && <p className="text-slate-500">No medicine found.</p>}
      <p className="text-xs text-slate-400 mt-6">Sample stock data for the prototype. Expired batches are not counted.</p></Page>);
}
