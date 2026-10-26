// Safe language hook. Do not rewrite React-managed text nodes: direct DOM mutation can
// desynchronise React and blank the app on a language switch. Visible React labels use i18n.jsx.
import { useEffect } from "react";
export function useAutoTranslate(lang) {
  useEffect(() => {
    document.documentElement.lang = lang === "hi" ? "hi" : "en";
    document.title = lang === "hi"
      ? "आरोग्य पथ · संजय गांधी स्मारक चिकित्सालय, रीवा"
      : "Arogya Path · Sanjay Gandhi Memorial Hospital, Rewa";
  }, [lang]);
}
