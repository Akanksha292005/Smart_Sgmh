import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, CartesianGrid } from "recharts";
import { CalendarCheck, UserCheck, Stethoscope, Timer, ShieldCheck, ShieldAlert, AlertTriangle, TrendingUp, FlaskConical, Pill } from "lucide-react";
import { api } from "./api";
import { Page, Card, Skeleton } from "./ui";

const COLORS = ["#0f766e", "#0891b2", "#d97706", "#7c3aed", "#dc2626", "#65a30d", "#db2777"];
const Kpi = ({ icon: I, label, value, color }) => (
  <Card className="!p-4 flex items-center gap-3"><div className={"w-11 h-11 rounded-xl flex items-center justify-center " + color}><I size={22} /></div>
    <div><div className="text-2xl font-bold leading-none">{value}</div><div className="text-xs text-slate-500 mt-1">{label}</div></div></Card>);
const Panel = ({ title, icon: I, children, className = "" }) => (
  <Card className={className}><h2 className="font-semibold mb-3 flex items-center gap-2">{I && <I size={18} className="text-emerald-600" />}{title}</h2>{children}</Card>);
const Empty = ({ t }) => <p className="text-sm text-slate-400">{t}</p>;

export function Admin() {
  const { data: s } = useQuery({ queryKey: ["stats"], queryFn: () => api("/admin/stats"), refetchInterval: 10000 });
  if (!s) return <div className="grid sm:grid-cols-4 gap-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}</div>;
  const today = new Date().toISOString().slice(0, 10), soon = new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10);
  const dwell = Object.entries(s.insights.avg).map(([name, value]) => ({ name, value }));
  const alerts = s.meds.filter((m) => m.expiry < today || m.expiry <= soon || m.stock < 20);
  const unavailable = s.doctors.filter((d) => d.code !== "avail");
  return (
    <Page><div className="space-y-5">
      <div className="flex flex-wrap justify-between items-center gap-2"><h1 className="text-2xl font-bold">Admin dashboard</h1>
        <span className={"inline-flex items-center gap-1.5 text-sm rounded-full px-3 py-1 " + (s.chain_ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700")}>
          {s.chain_ok ? <ShieldCheck size={16} /> : <ShieldAlert size={16} />}Audit log {s.chain_ok ? "verified (tamper-evident)" : "TAMPERED"}</span></div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi icon={CalendarCheck} label="Booked today" value={s.today.booked} color="bg-emerald-50 text-emerald-700" /><Kpi icon={UserCheck} label="Arrived" value={s.today.arrived} color="bg-sky-50 text-sky-700" />
        <Kpi icon={Stethoscope} label="Seen by doctor" value={s.today.seen} color="bg-emerald-50 text-emerald-700" /><Kpi icon={Timer} label="Avg wait (min)" value={s.avg_wait ?? "-"} color="bg-amber-50 text-amber-700" /></div>

      <div className="grid md:grid-cols-2 gap-4">
        <Panel title="Patient flow funnel"><ResponsiveContainer height={240}><BarChart data={s.funnel}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" fontSize={10} /><YAxis allowDecimals={false} fontSize={11} /><Tooltip />
          <Bar dataKey="value" radius={[6, 6, 0, 0]}>{s.funnel.map((_, i) => <Cell key={i} fill={COLORS[0]} fillOpacity={1 - i * 0.07} />)}</Bar></BarChart></ResponsiveContainer></Panel>
        <Panel title="Appointments by department"><ResponsiveContainer height={240}><PieChart><Pie data={s.by_dept} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
          {s.by_dept.map((_, i) => <Cell key={i} fill={COLORS[i % 7]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">{s.by_dept.map((d, i) => <span key={d.name} className="flex items-center gap-1"><i className="w-2 h-2 rounded-full" style={{ background: COLORS[i % 7] }} />{d.name} ({d.value})</span>)}</div></Panel></div>

      <div className="grid md:grid-cols-3 gap-4">
        <Panel title="AI insight: tomorrow's load" icon={TrendingUp}><div className="text-4xl font-bold text-emerald-700">{s.insights.forecast ?? "-"}</div>
          <p className="text-sm text-slate-500 mt-1">expected appointments on {s.insights.day}</p><p className="text-xs text-slate-400 mt-2">Average of {s.insights.days} past day(s). A simple estimate, not a medical tool.</p></Panel>
        <Panel title="Avg time per stage (min)" className="md:col-span-2">{dwell.length ? <ResponsiveContainer height={150}><BarChart data={dwell}><XAxis dataKey="name" fontSize={10} /><YAxis fontSize={11} /><Tooltip /><Bar dataKey="value" fill="#0891b2" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer> : <Empty t="Not enough data yet. Move a few patients through the stages." />}</Panel></div>

      <div className="grid md:grid-cols-2 gap-4">
        <Panel title="Delay risk (predicted vs usual stage time)" icon={AlertTriangle}>{s.insights.risk.length ? <table className="w-full text-sm"><tbody>{s.insights.risk.map((r) => (
          <tr key={r.code} className="border-b last:border-0"><td className="py-1.5 font-medium">{r.code}</td><td>{r.cp}</td><td>{r.mins} min <span className="text-slate-400">(usual {r.base})</span></td>
            <td><span className={"text-xs rounded-full px-2 py-0.5 " + (r.level === "High" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700")}>{r.level}</span></td></tr>))}</tbody></table> : <Empty t="No patient is delayed right now." />}
          {s.stuck.length > 0 && <p className="text-sm text-red-600 mt-3">{s.stuck.length} patient(s) stuck over {s.mins} min: {s.stuck.map((x) => x.code).join(", ")}</p>}</Panel>
        <Panel title="Uncollected lab samples" icon={FlaskConical}>{s.insights.pend.length ? s.insights.pend.map((p) => <p key={p.code + p.test} className="text-sm py-1 border-b last:border-0">{p.code} · {p.test} <span className="text-amber-700">({p.mins} min)</span></p>) : <Empty t="No pending samples." />}</Panel></div>

      <div className="grid md:grid-cols-2 gap-4">
        <Panel title="Medicine stock alerts" icon={Pill}>{alerts.length ? alerts.map((m) => (
          <p key={m.batch} className="text-sm py-1 border-b last:border-0 flex justify-between"><span>{m.name} <span className="text-slate-400">({m.batch})</span></span>
            <span className={m.expiry < today ? "text-red-600" : "text-amber-700"}>{m.expiry < today ? "Expired" : m.expiry <= soon ? "Expires " + m.expiry : "Low: " + m.stock}</span></p>)) : <Empty t="All stock is healthy." />}</Panel>
        <Panel title="Doctor availability">{unavailable.length ? unavailable.map((d) => <p key={d.name} className="text-sm py-1 flex justify-between"><span>{d.name}</span><span style={{ color: d.color }}>{d.label}</span></p>) : <Empty t={`All ${s.doctors.length} doctors available.`} />}</Panel></div>

      <Panel title="Recent audit trail (hash-chained)"><div className="text-xs font-mono space-y-1 overflow-x-auto">{s.logs.map((l, i) => <p key={i} className="whitespace-nowrap"><span className="text-slate-400">{l.ts}</span> {l.actor} · <b>{l.action}</b> {l.detail}</p>)}</div></Panel>
    </div></Page>);
}
