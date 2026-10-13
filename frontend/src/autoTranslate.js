// Site-wide Hindi/English switch: translates every visible text node (and placeholder/title/alt) using the dictionary in hi.js,
// and keeps translating text that React adds later (route changes, API data). Switching back to English restores the originals.
import { useEffect } from "react";
import { HI, PREFIX, REGEX, TOKENS } from "./hi";

const TOKEN_RE = new RegExp("\\b(" + Object.keys(TOKENS).join("|") + ")\\b", "g");
const ATTRS = ["placeholder", "title", "alt", "aria-label"];
const orig = new WeakMap(), written = new WeakMap(); // text node -> English / the Hindi we wrote

function translate(s) {
  if (HI[s]) return HI[s];
  for (const [re, to] of REGEX) if (re.test(s)) return s.replace(re, to);
  for (const [p, h] of PREFIX) if (s.startsWith(p)) return h + s.slice(p.length);
  return s.replace(TOKEN_RE, (m) => TOKENS[m]);
}
function doText(n) {
  const p = n.parentElement; if (!p || ["SCRIPT", "STYLE", "TEXTAREA"].includes(p.tagName)) return;
  const cur = n.nodeValue; if (written.get(n) === cur) return;   // already our Hindi
  const core = cur.replace(/\s+/g, " ").trim(); if (!core) return;
  const out = translate(core); orig.set(n, cur);
  if (out !== core) { n.nodeValue = cur.match(/^\s*/)[0] + out + cur.match(/\s*$/)[0]; written.set(n, n.nodeValue); }
}
function doAttrs(el) {
  for (const a of ATTRS) { const v = el.getAttribute?.(a); if (!v) continue; const en = el.dataset["en" + a] ?? v, out = translate(en.trim());
    if (out !== en.trim()) { el.dataset["en" + a] = en; el.setAttribute(a, out); } }
}
function walk(root) {
  if (root.nodeType === 3) return doText(root);
  if (root.nodeType !== 1) return;
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) doText(n);
  doAttrs(root); root.querySelectorAll?.("[placeholder],[title],[alt],[aria-label]").forEach(doAttrs);
}
function restore() {
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) if (written.get(n) === n.nodeValue && orig.has(n)) { n.nodeValue = orig.get(n); written.delete(n); }
  document.querySelectorAll("*").forEach((el) => ATTRS.forEach((a) => { const k = "en" + a; if (el.dataset?.[k] !== undefined) { el.setAttribute(a, el.dataset[k]); delete el.dataset[k]; } }));
}
export function useAutoTranslate(lang) {
  useEffect(() => {
    document.documentElement.lang = lang;
    if (lang !== "hi") { restore(); document.title = "Arogya Path · Sanjay Gandhi Memorial Hospital, Rewa"; return; }
    document.title = "आरोग्य पथ · संजय गांधी स्मारक चिकित्सालय, रीवा"; walk(document.body);
    const mo = new MutationObserver((ms) => ms.forEach((m) => (m.type === "characterData" ? doText(m.target) : m.addedNodes.forEach(walk))));
    mo.observe(document.body, { childList: true, subtree: true, characterData: true });
    return () => mo.disconnect();
  }, [lang]);
}
