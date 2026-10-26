/* Extra links on every React page (no rebuild needed): Hospital Map, Live Safety Demo, admission info. Also keeps the Flask session in sync on logout. */
(function () {
  if (window.__sgmhX) return; window.__sgmhX = 1;
  var s = document.createElement("style");
  s.textContent = "#sgmh-fab{position:fixed;right:16px;bottom:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;align-items:flex-end}#sgmh-fab a{display:flex;align-items:center;gap:8px;text-decoration:none;font:600 14px Inter,system-ui,sans-serif;color:#fff;padding:11px 18px;border-radius:999px;box-shadow:0 8px 24px rgba(0,0,0,.3);transition:.15s}#sgmh-fab a:hover{transform:translateY(-2px);filter:brightness(1.08)}#sgmh-fab .m{background:linear-gradient(135deg,#1f6fb8,#0a3569)}#sgmh-fab .d{background:linear-gradient(135deg,#0a3569,#0a3569)}#sgmh-t{display:none}@media(max-width:768px){#sgmh-fab{right:12px;bottom:calc(12px + env(safe-area-inset-bottom,0px));max-width:calc(100vw - 24px)}#sgmh-fab a{display:none;padding:12px 16px;font-size:14px;min-height:44px}#sgmh-fab.open a{display:flex}#sgmh-t{display:flex;align-items:center;justify-content:center;width:48px;height:48px;border-radius:50%;border:0;background:#0a3569;color:#fff;font-size:22px;box-shadow:0 8px 24px rgba(0,0,0,.35);cursor:pointer;padding:0}}";
  document.head.appendChild(s);
  var d = document.createElement("div"); d.id = "sgmh-fab";
  d.innerHTML = '<a class="m" href="/navigate">\uD83D\uDDFA\uFE0F Hospital Map / \u0905\u0938\u094D\u092A\u0924\u093E\u0932 \u0928\u0915\u094D\u0936\u093E</a><a class="m" href="/blood-bank">\uD83E\uDE78 Blood Bank / \u092C\u094D\u0932\u0921 \u092C\u0948\u0902\u0915</a><a class="d" href="/demo/start">\uD83D\uDEA8 Live Safety Demo</a>';
  var tg = document.createElement("button"); tg.id = "sgmh-t"; tg.type = "button"; tg.setAttribute("aria-label", "Quick links"); tg.textContent = "\uD83E\uDDED"; d.appendChild(tg);
  tg.addEventListener("click", function (e) { e.stopPropagation(); d.classList.toggle("open"); tg.textContent = d.classList.contains("open") ? "\u2715" : "\uD83E\uDDED"; });
  document.addEventListener("click", function (e) { if (!d.contains(e.target) && d.classList.contains("open")) { d.classList.remove("open"); tg.textContent = "\uD83E\uDDED"; } });
  document.body.appendChild(d);
  var HI = { "How admission works": "\u092D\u0930\u094D\u0924\u0940 \u0915\u0948\u0938\u0947 \u0939\u094B\u0924\u0940 \u0939\u0948", "How it works": "\u092F\u0939 \u0915\u0948\u0938\u0947 \u0915\u093E\u092E \u0915\u0930\u0924\u093E \u0939\u0948", "New patient? Register here": "\u0928\u092F\u093E \u092E\u0930\u0940\u091C\u093C? \u092F\u0939\u093E\u0901 \u092A\u0902\u091C\u0940\u0915\u0930\u0923 \u0915\u0930\u0947\u0902", "How admission works": "IPD \u092D\u0930\u094D\u0924\u0940", "Hospital Map": "\u0905\u0938\u094D\u092A\u0924\u093E\u0932 \u0928\u0915\u094D\u0936\u093E", "Blood Bank": "\u092C\u094D\u0932\u0921 \u092C\u0948\u0902\u0915", "Live Demo": "\u0932\u093E\u0907\u0935 \u0921\u0947\u092E\u094B", "Request IPD admission": "IPD \u092D\u0930\u094D\u0924\u0940 \u0915\u093E \u0905\u0928\u0941\u0930\u094B\u0927 \u0915\u0930\u0947\u0902" };
  function L(k) { return (localStorage.getItem("lang") === "hi" && HI[k]) || k; }
  function nav() {
    var bar = document.querySelector("header .bg-emerald-900 > div");
    if (bar) {
      var w = document.getElementById("sgmh-x");
      if (!w) {
        w = document.createElement("span"); w.id = "sgmh-x"; w.style.cssText = "display:inline-flex;gap:6px;align-items:center";
        var st = "color:#fff;font-weight:600;padding:2px 10px;border-radius:999px;background:rgba(255,255,255,.18);text-decoration:none";
        [["How admission works", "/ipd", st], ["Hospital Map", "/navigate", st], ["Beds & ICU", "/beds", st], ["How it works", "/workflow", st], ["Blood Bank", "/blood-bank", st], ["Live Demo", "/demo/start", st.replace("rgba(255,255,255,.18)", "#ffffff").replace("color:#fff", "color:#0a3569")]].forEach(function (x) { var a = document.createElement("a"); a.href = x[1]; a.setAttribute("data-k", x[0]); a.style.cssText = x[2]; w.appendChild(a); });
        var btn = bar.querySelector("button"); bar.insertBefore(w, btn || null);
      }
      w.querySelectorAll("a").forEach(function (a) { var t = L(a.getAttribute("data-k")); if (a.textContent !== t) a.textContent = t; });
    }
    var tri = Array.prototype.find.call(document.querySelectorAll("a"), function (a) { return /Try AI triage|AI \u091F\u094D\u0930\u093E\u092F\u0947\u091C/.test(a.textContent); });
    if (tri) {
      var c = document.getElementById("sgmh-ipd");
      if (!c) { c = document.createElement("a"); c.id = "sgmh-ipd"; c.href = "/ipd"; c.className = tri.className; tri.parentNode.insertBefore(c, tri.nextSibling); }
      var t2 = L("How admission works"); if (c.textContent !== t2) c.textContent = t2;
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
      var d = document.createElement("div"); d.className = "sgmh-loc"; d.setAttribute("data-l", tag); d.style.cssText = "font-size:12px;margin-top:4px;color:#165a9c;font-weight:600";
      d.innerHTML = "\uD83D\uDCCD " + (hi ? L.hi : L.name) + " &middot; " + (hi ? L.f.hi : L.f.name) + " &middot; <a href=\"/navigate?from=gate_main&to=" + L.id + "\" style=\"text-decoration:underline\">" + (hi ? "\u0930\u093E\u0938\u094D\u0924\u093E" : "Directions") + "</a>";
      el.insertAdjacentElement("afterend", d);
    });
  }
  var tm; new MutationObserver(function () { clearTimeout(tm); tm = setTimeout(badges, 350); }).observe(document.body, { childList: true, subtree: true }); badges();
  document.addEventListener("click", function (e) { var t = e.target.closest && e.target.closest("button,a"); if (t && /^(logout|\u0932\u0949\u0917 ?\u0906\u0909\u091F)/i.test(t.textContent.trim())) fetch("/logout", { credentials: "same-origin" }); }, true);

  /* sgmh-book-redirect: patient registration, family profiles and the smart booking flow live on the Flask pages (/register, /family, /book). Any move to /app/book goes there. */
  function toBook(u, st) {
    var p = String(u || "").replace(location.origin, "");
    if (!/^\/app\/book\/?(\?.*)?$/.test(p)) return false;
    var r = st && st.usr && st.usr.reason; location.href = (r ? "/book?reason=" + encodeURIComponent(r) : "/opd"); return true;
  }
  ["pushState", "replaceState"].forEach(function (k) { var o = history[k]; history[k] = function (st, t, u) { if (toBook(u, st)) return; return o.apply(this, arguments); }; });
  if (/^\/app\/book\/?$/.test(location.pathname)) location.replace("/opd");
  function regLink() {
    var st = Array.prototype.find.call(document.querySelectorAll("main a[href='/login']"), function (a) { return /Staff login/.test(a.textContent); });
    if (st && !document.getElementById("sgmh-reg")) {
      var p = document.createElement("p"); p.id = "sgmh-reg"; p.className = "text-sm text-center"; p.style.marginTop = "6px";
      var a = document.createElement("a"); a.href = "/register"; a.className = "text-emerald-700 underline"; a.setAttribute("data-k", "New patient? Register here"); p.appendChild(a); st.parentNode.parentNode.insertBefore(p, st.parentNode.nextSibling);
    }
    var r = document.getElementById("sgmh-reg"); if (r) { var a2 = r.firstChild, t = L("New patient? Register here"); if (a2.textContent !== t) a2.textContent = t; }
  }
  new MutationObserver(regLink).observe(document.body, { childList: true, subtree: true }); regLink();

  /* v26: live blood-bank strip on the homepage (reads /api/blood-bank; refreshes every minute) */
  (function () {
    var HIB = { t: "\u092C\u094D\u0932\u0921 \u092C\u0948\u0902\u0915: \u0905\u092D\u0940 \u0915\u094C\u0928-\u0938\u093E \u0930\u0915\u094D\u0924 \u0938\u092E\u0942\u0939 \u0909\u092A\u0932\u092C\u094D\u0927 \u0939\u0948", ok: "\u0909\u092A\u0932\u092C\u094D\u0927", low: "\u0915\u092E", none: "\u0909\u092A\u0932\u092C\u094D\u0927 \u0928\u0939\u0940\u0902", u: "\u092F\u0942\u0928\u093F\u091F", more: "\u092A\u0942\u0930\u093E \u0938\u094D\u091F\u0949\u0915 \u0926\u0947\u0916\u0947\u0902", old: "\u0915\u0941\u091B \u0906\u0901\u0915\u0921\u093C\u0947 \u092A\u0941\u0930\u093E\u0928\u0947 \u0939\u094B \u0938\u0915\u0924\u0947 \u0939\u0948\u0902, \u0906\u0928\u0947 \u0938\u0947 \u092A\u0939\u0932\u0947 \u092B\u093C\u094B\u0928 \u0915\u0930\u0947\u0902" };
    var EN = { t: "Blood bank: which blood group is available now", ok: "Available", low: "Low", none: "Not available", u: "units", more: "View full stock", old: "Some numbers may be outdated, please call before you travel" };
    var DATA = null, el = null;
    function T() { return localStorage.getItem("lang") === "hi" ? HIB : EN; }
    function draw() {
      var q = document.querySelector(".fx-quick"); if (!q || !DATA) return;
      if (!el || !el.isConnected) { el = document.createElement("section"); el.id = "sgmh-blood"; el.className = "fx-blood"; q.insertAdjacentElement("afterend", el); }
      var t = T(), old = DATA.stock.some(function (s) { return s.stale; });
      el.innerHTML = '<div class="fx-b-head"><b>' + t.t + '</b><a href="/blood-bank">' + t.more + ' \u2192</a></div><div class="fx-b-grid">' +
        DATA.stock.map(function (s) { return '<div class="fx-b ' + s.level + '"><span class="g">' + s.grp + '</span><span class="n">' + s.units + ' ' + t.u + '</span><span class="l">' + t[s.level] + '</span></div>'; }).join("") + '</div>' + (old ? '<p class="fx-b-old">' + t.old + '</p>' : "");
    }
    function load() { fetch("/api/blood-bank").then(function (r) { return r.json(); }).then(function (d) { DATA = d; draw(); }).catch(function () {}); }
    load(); setInterval(load, 60000);
    new MutationObserver(function () { var q = document.querySelector(".fx-quick"); if (q && (!el || !el.isConnected)) draw(); var l = localStorage.getItem("lang"); if (el && el.getAttribute("data-l") !== l) { el.setAttribute("data-l", l || "en"); draw(); } }).observe(document.body, { childList: true, subtree: true });
  })();

  /* v27: patients always log in on /start (name, mobile, OTP); React pages reuse that login */
  (function () {
    var p = location.pathname;
    if (p === "/app/login" || p === "/app/login/" || p === "/app/register") { location.replace("/start"); return; }
    if (!localStorage.getItem("auth")) {
      fetch("/api/v1/me-token").then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
        if (d && d.token) { localStorage.setItem("auth", JSON.stringify({ token: d.token, user: d.user })); }
      }).catch(function () {});
    }
  })();
  /* v28: after login the patient lands on the full website with a welcome line; Book OPD goes to the OPD hub (see the doctors, then book) */
  (function () {
    var p = location.pathname; if (!/^\/app\/?$/.test(p)) return;
    var HIW = { w: "\u0938\u094D\u0935\u093E\u0917\u0924 \u0939\u0948,", h: "\u092E\u0947\u0930\u093E \u0939\u094B\u092E", hi: "\u092E\u0947\u0930\u093E \u0907\u0924\u093F\u0939\u093E\u0938", r: "\u092E\u0947\u0930\u0947 \u0930\u093F\u0915\u0949\u0930\u094D\u0921", o: "\u0938\u092C \u0915\u0941\u091B \u0916\u0941\u0932\u093E \u0939\u0948\u0964 \u0932\u0949\u0917\u093F\u0928 \u0938\u093F\u0930\u094D\u092B\u093C \u092C\u0941\u0915\u093F\u0902\u0917 \u092F\u093E \u0905\u092A\u0928\u0947 \u0930\u093F\u0915\u0949\u0930\u094D\u0921 \u0916\u094B\u0932\u0924\u0947 \u0938\u092E\u092F \u092E\u093E\u0901\u0917\u093E \u091C\u093E\u0924\u093E \u0939\u0948" };
    var EN = { w: "Welcome,", h: "My home", hi: "My history", r: "My records", o: "Everything is open. Login is asked only when you book or open your records" };
    function show(name) {
      if (document.getElementById("sgmh-welcome")) return;
      var m = document.querySelector("main"); if (!m) return;
      var t = localStorage.getItem("lang") === "hi" ? HIW : EN, e = document.createElement("div"); e.id = "sgmh-welcome"; e.className = "fx-welcome";
      e.innerHTML = '<div><b>' + t.w + ' ' + String(name).replace(/[<>&]/g, "") + '</b><span>' + t.o + '</span></div><div class="l"><a href="/home">' + t.h + '</a><a href="/history">' + t.hi + '</a><a href="/records">' + t.r + '</a></div>';
      m.insertBefore(e, m.firstChild);
    }
    function go() {
      var a = null; try { a = JSON.parse(localStorage.getItem("auth") || "null"); } catch (x) {}
      if (a && a.user && a.user.role === "patient") { show(a.user.name); return; }
      fetch("/api/v1/me-token").then(function (r) { return r.ok ? r.json() : null; }).then(function (d) { if (d && d.user) show(d.user.name); }).catch(function () {});
    }
    var n = 0, iv = setInterval(function () { if (document.querySelector("main") || ++n > 40) { clearInterval(iv); go(); } }, 150);
  })();

  /* sgmh-route-guard: routes missing from the built React bundle go to working pages instead of a blank screen */
  (function () {
    var p = location.pathname.replace(/\/+$/, "");
    var OK = /^\/app(\/(login|staff-access|me|book|doctors|triage|beds|assistant|track|lab-services|medical-store|admin|visit\/[^\/]+))?$/;
    if (p === "/app/beds") { location.replace("/beds"); return; }
    if (p === "/app/staff-access") { location.replace("/login"); return; }
    if (p.indexOf("/app") === 0 && !OK.test(p) && !/\.[a-z0-9]+$/i.test(p)) location.replace("/app/");
  })();
})();
