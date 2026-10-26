import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Brain, Siren, ArrowRight, Sparkles } from "lucide-react";
import { api } from "./api";
import { Page, Card, Btn } from "./ui";
import { useT } from "./i18n";

const EX = ["bache ko bukhar aur khansi", "seene me dard, saans phoolna", "ghutne me dard chalne par", "kaan me dard", "periods late, pet dard", "sugar badh gaya, kamzori"];
export function Triage() {
  const { t } = useT(), nav = useNavigate(), [text, setText] = useState(""), [dq, setDq] = useState("");
  useEffect(() => { const id = setTimeout(() => setDq(text), 350); return () => clearTimeout(id); }, [text]);
  const { data } = useQuery({ queryKey: ["triage", dq], queryFn: () => api("/suggest?reason=" + encodeURIComponent(dq)), enabled: dq.trim().length > 2 });
  return (
    <Page><div className="max-w-2xl mx-auto space-y-4">
      <div className="flex items-center gap-3"><div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-600 to-amber-500 text-white flex items-center justify-center"><Brain size={24} /></div>
        <div><h1 className="text-2xl font-bold">AI symptom triage</h1><p className="text-sm text-slate-500">Describe the problem in Hindi, English or Hinglish. We suggest the right OPD.</p></div></div>
      <Card><textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. bache ko bukhar aur khansi hai" className="border rounded-xl w-full p-3 outline-none focus:ring-2 ring-emerald-200" />
        <div className="flex flex-wrap gap-2 mt-3">{EX.map((x) => <button key={x} onClick={() => setText(x)} className="text-xs rounded-full border px-3 py-1 hover:border-emerald-500 hover:text-emerald-700">{x}</button>)}</div></Card>
      {data?.emergency && <div className="flex gap-3 bg-red-50 border border-red-200 text-red-700 rounded-2xl p-4"><Siren className="shrink-0" /><div><b>Possible emergency.</b> Go to the Emergency gate now or call 112 / 108. Do not wait for an appointment.</div></div>}
      {data?.ranked?.length > 0 && !data.emergency && (
        <Card><div className="flex items-center gap-2 mb-3 font-semibold"><Sparkles size={18} className="text-amber-500" />Suggested department</div>
          {data.ranked.map((r, i) => (
            <div key={r.dept} className="mb-3"><div className="flex justify-between text-sm"><span className={i === 0 ? "font-semibold" : "text-slate-500"}>{r.dept}</span><span>{Math.round(r.prob * 100)}%</span></div>
              <div className="h-2.5 rounded-full bg-slate-100 overflow-hidden"><motion.div className={"h-full " + (i === 0 ? "bg-gradient-to-r from-emerald-500 to-amber-400" : "bg-slate-300")} initial={{ width: 0 }} animate={{ width: r.prob * 100 + "%" }} transition={{ duration: 0.6 }} /></div></div>))}
          {data.ranked[0].prob < 0.4 && <p className="text-sm text-amber-700">Not very sure. General Medicine OPD is a safe starting point.</p>}
          <Btn className="mt-2" onClick={() => nav("/book", { state: { reason: text } })}>{t("book_for")} {data.ranked[0].dept} <ArrowRight size={16} /></Btn></Card>)}
      {data && !data.emergency && !data.ranked?.length && <Card className="text-sm text-slate-600">Could not match this confidently. Please describe the problem in a few more words, or book General Medicine OPD.</Card>}
      <Card className="text-sm text-slate-600"><b>How it works:</b> your text is converted to TF-IDF character n-gram features (so spelling variants like "bukhar/bukhaar" still match) and a Logistic Regression model, trained on a small sample, gives a probability for each department. A rule-based red-flag check for emergencies always overrides the model. <span className="text-slate-400">{data?.model}</span><br /><span className="text-xs text-slate-400">This only routes you to an OPD. It is not a diagnosis.</span></Card>
    </div></Page>);
}
