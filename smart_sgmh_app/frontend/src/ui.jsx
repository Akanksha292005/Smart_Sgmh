import { motion } from "framer-motion";
export const Page = ({ children }) => <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>{children}</motion.div>;
export const Card = ({ children, className = "", ...p }) => <div {...p} className={"bg-white rounded-2xl shadow-sm border border-slate-200/70 p-5 " + className}>{children}</div>;
export const Btn = ({ variant, className = "", ...p }) => (
  <button {...p} className={"inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 font-medium transition active:scale-95 disabled:opacity-40 disabled:active:scale-100 " +
    (variant === "ghost" ? "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 " : "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow hover:shadow-md ") + className} />);
export const Skeleton = ({ className = "" }) => <div className={"animate-pulse bg-slate-200 rounded-xl " + className} />;
export const Err = ({ e }) => (e ? <p className="text-red-600 text-sm mt-2">{e.message}</p> : null);
