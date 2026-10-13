/* Extra links on every React page (no rebuild needed): Hospital Map, Live Safety Demo, IPD admission. Also keeps the Flask session in sync on logout. */
(function () {
  if (window.__sgmhX) return; window.__sgmhX = 1;
  var s = document.createElement("style");
  s.textContent = "#sgmh-fab{position:fixed;right:16px;bottom:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;align-items:flex-end}#sgmh-fab a{display:flex;align-items:center;gap:8px;text-decoration:none;font:600 14px Inter,system-ui,sans-serif;color:#fff;padding:11px 18px;border-radius:999px;box-shadow:0 8px 24px rgba(0,0,0,.3);transition:.15s}#sgmh-fab a:hover{transform:translateY(-2px);filter:brightness(1.08)}#sgmh-fab .m{background:linear-gradient(135deg,#1f8a5f,#14543b)}#sgmh-fab .d{background:linear-gradient(135deg,#14543b,#14543b)}@media(max-width:600px){#sgmh-fab a{padding:10px 14px;font-size:13px}}";
  document.head.appendChild(s);
  var d = document.createElement("div"); d.id = "sgmh-fab";
  d.innerHTML = '<a class="m" href="/navigate">\uD83D\uDDFA\uFE0F Hospital Map / \u0905\u0938\u094D\u092A\u0924\u093E\u0932 \u0928\u0915\u094D\u0936\u093E</a><a class="d" href="/demo/start">\uD83D\uDEA8 Live Safety Demo</a>';
  document.body.appendChild(d);
  var HI = { "IPD Admission": "IPD \u092D\u0930\u094D\u0924\u0940", "Hospital Map": "\u0905\u0938\u094D\u092A\u0924\u093E\u0932 \u0928\u0915\u094D\u0936\u093E", "Live Demo": "\u0932\u093E\u0907\u0935 \u0921\u0947\u092E\u094B", "Request IPD admission": "IPD \u092D\u0930\u094D\u0924\u0940 \u0915\u093E \u0905\u0928\u0941\u0930\u094B\u0927 \u0915\u0930\u0947\u0902" };
  function L(k) { return (localStorage.getItem("lang") === "hi" && HI[k]) || k; }
  function nav() {
    var bar = document.querySelector("header .bg-emerald-900 > div");
    if (bar) {
      var w = document.getElementById("sgmh-x");
      if (!w) {
        w = document.createElement("span"); w.id = "sgmh-x"; w.style.cssText = "display:inline-flex;gap:6px;align-items:center";
        var st = "color:#fff;font-weight:600;padding:2px 10px;border-radius:999px;background:rgba(255,255,255,.18);text-decoration:none";
        [["IPD Admission", "/admit", st], ["Hospital Map", "/navigate", st], ["Live Demo", "/demo/start", st.replace("rgba(255,255,255,.18)", "#ffffff").replace("color:#fff", "color:#14543b")]].forEach(function (x) { var a = document.createElement("a"); a.href = x[1]; a.setAttribute("data-k", x[0]); a.style.cssText = x[2]; w.appendChild(a); });
        var btn = bar.querySelector("button"); bar.insertBefore(w, btn || null);
      }
      w.querySelectorAll("a").forEach(function (a) { var t = L(a.getAttribute("data-k")); if (a.textContent !== t) a.textContent = t; });
    }
    var tri = Array.prototype.find.call(document.querySelectorAll("a"), function (a) { return /Try AI triage|AI \u091F\u094D\u0930\u093E\u092F\u0947\u091C/.test(a.textContent); });
    if (tri) {
      var c = document.getElementById("sgmh-ipd");
      if (!c) { c = document.createElement("a"); c.id = "sgmh-ipd"; c.href = "/admit"; c.className = tri.className; tri.parentNode.insertBefore(c, tri.nextSibling); }
      var t2 = L("Request IPD admission"); if (c.textContent !== t2) c.textContent = t2;
    }
  }
  new MutationObserver(nav).observe(document.body, { childList: true, subtree: true }); nav();
  var LOC = null, busy = 0;
  function loadLoc(cb) { fetch("/api/map").then(function (r) { return r.json(); }).then(function (D) { var m = {}; D.rooms.forEach(function (r) { (r.doctors || []).forEach(function (d) { m[d.name.trim()] = { id: r.id, name: r.name, hi: r.hi, f: D.floors[r.floor] }; }); }); LOC = m; cb(); }).catch(function () { LOC = {}; }); }
  function badges() {
    if (!LOC) { if (!busy) { busy = 1; loadLoc(badges); } return; }
    var hi = localStorage.getItem("lang") === "hi", w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT), n, todo = [];
    while ((n = w.nextNode())) { var t = n.nodeValue.trim(); if (t.length > 4 && LOC[t] && n.parentElement && !n.parentElement.closest("#sgmh-fab")) todo.push([n.parentElement, LOC[t]]); }
    todo.forEach(function (x) {
      var el = x[0], L = x[1], nx = el.nextElementSibling, tag = hi ? "hi" : "en";
      if (nx && nx.classList.contains("sgmh-loc")) { if (nx.getAttribute("data-l") === tag) return; nx.remove(); }
      var d = document.createElement("div"); d.className = "sgmh-loc"; d.setAttribute("data-l", tag); d.style.cssText = "font-size:12px;margin-top:4px;color:#1c7d58;font-weight:600";
      d.innerHTML = "\uD83D\uDCCD " + (hi ? L.hi : L.name) + " &middot; " + (hi ? L.f.hi : L.f.name) + " &middot; <a href=\"/navigate?from=gate_main&to=" + L.id + "\" style=\"text-decoration:underline\">" + (hi ? "\u0930\u093E\u0938\u094D\u0924\u093E" : "Directions") + "</a>";
      el.insertAdjacentElement("afterend", d);
    });
  }
  var tm; new MutationObserver(function () { clearTimeout(tm); tm = setTimeout(badges, 350); }).observe(document.body, { childList: true, subtree: true }); badges();
  document.addEventListener("click", function (e) { var t = e.target.closest && e.target.closest("button,a"); if (t && /^(logout|\u0932\u0949\u0917 ?\u0906\u0909\u091F)/i.test(t.textContent.trim())) fetch("/logout", { credentials: "same-origin" }); }, true);
})();
