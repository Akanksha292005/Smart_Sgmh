# v21: colours + doctor locations
- Colours: only green, white and grey everywhere (React site and Flask pages). Red stays only for emergency / critical alerts.
- ONE server: run `python app.py` and open http://127.0.0.1:5000 (React at /app/, Flask pages and API on the same port). Do NOT open the Vite dev port (5173) unless you run `npm run dev`; the dev proxy now forwards the Flask pages too.
- Doctor room + floor: shown under every doctor on the React Doctors / booking pages and on the Flask doctor cards, and a searchable "Find a doctor" table is at the top of /navigate.
- Floor layout is still a SAMPLE (hospital_map.py).

# v19: judge-ready fixes
- Why "alerts never came": /demo needed a nurse/doctor login and nothing led there. Now `/demo/start` signs in as the demo nurse in one click (set DEMO_MODE=0 to disable). Links: top bar of the React home ("Live Demo"), floating red button, and the Flask pages. /demo has a 2-minute judge guide.
- Real flow also works: nurse /vitals/<code> -> critical alert -> doctor/nurse pop-up and /alerts page.
- Login on the React site now also signs in the Flask pages (IPD admission, staff screens). React logout signs both out.
- Map: route spans several floors -> floor shortcuts; gate labels no longer cut; new "Doctors and where they sit" and "Tests, pharmacy, ICU and emergency" lists with a Show directions button. Layout is still a SAMPLE (hospital_map.py).
- Theme: mid-tone (React navy/teal lightened; Flask pages soft sage, no OS dark mode). React: IPD button + top-bar links, header says OPD + IPD, ticker says IPD admission 24x7, college dean email removed.
- Tested: every GET route for 8 roles (no 5xx), React login -> Flask session, demo actions, nurse vitals -> doctor alert.

# v18: lighter theme + Live Safety Demo + Hospital Map
- Theme: mid navy instead of near-black (src/index.css and built dist CSS patched; no rebuild needed).
- /demo (login admin/nurse/doctor): judge console. Vitals presets, wrong lab sample, expired / wrong / allergy / duplicate medicine -> real safety checks -> red full-screen alert, acknowledge, escalation fast-forward, reset. Staff pages also show an alert toast.
- /navigate (public): indoor map, 3 floors. Pick where you are + where to go (ICU, blood bank, cardiology, pharmacy, pathology, doctor name) -> route + step-by-step directions. Hindi supported. ?from=icu&to=pharm links work.
- The floor layout is a SAMPLE. Edit hospital_map.py (ROOMS) with the real plan.
- Floating buttons on React pages come from frontend/public/nav-extras.js. Restart the server after updating templates.

# Smart SGMH (Arogya Path): merged project (v17)
One project = B (React portal + REST API + IPD + AI/ML + real SGMH doctors + full Hindi) + A (patient-safety layer).
Run: `pip install -r requirements.txt` then `python app.py` (or start.bat) -> http://127.0.0.1:5000  (React app at /app/, staff screens are Flask pages).
New login: nurse 9000000060 / nurse123 (other demo logins below). Delete smartsgmh.db to reset.

## v17: what was merged
From A: safety.py with vitals + early-warning score (sample thresholds), alerts with agent steps and escalation to supervisor (ESCALATE_MIN, default 10 min),
verified lab report entry (blocks a report if the sample barcode belongs to another patient), verified dispensing (prescription, expiry, allergy, duplicate, stock checks),
patient summary page /patient/<code> (vitals chart, reports, medicines given, doctor-approved diet), allergy field, Alerts badge in the menu.
Fixes while merging: IPD (admitted) patients now appear in the vitals list; the two new lab/pharmacy forms were missing the CSRF token (would have failed with 400), now fixed;
A's status badge class renamed to .lvl so it does not clash with the new theme's .pill chips; Hindi strings for the safety pages added.
Not done: the safety screens are Flask pages (staff), not React screens. The React patient portal links stay as before. Alerts escalate while a staff page is open (production needs a scheduler).
Tested: 39 automated checks (login per role, vitals alert, ack, lab mismatch block, verified dispensing, duplicate block, summary access, IPD in vitals, ML triage, assistant, admin insights, Hindi page).

---- earlier history (project B) ----
Run: python -m venv venv; venv\Scripts\activate; pip install -r requirements.txt; python app.py -> http://127.0.0.1:5000
Demo logins (phone/password): patient 9000000001/pat123, reception 9000000010/rec123, doctor 9000000041/doc123 (Medicine; 9000000042.. other depts),
lab 9000000020/lab123, pharmacy 9000000030/ph123, admin 9000000000/admin123. Delete smartsgmh.db to reset.
Optional: ANTHROPIC_API_KEY enables AI rewording of the doctor's note (doctor still approves). STUCK_MIN=1 to demo stuck alerts.
SAMPLE/SIMULATED: doctors, medicine batches, hospital/lab/pharmacy integration. Password login stands in for OTP.

## v2 upgrades
Live updates without reload (4 sec), queue position + wait estimate, emergency red-flag screening on booking, appointment cancel,
printable advice (Print / Save as PDF), admin: charts, add doctors and medicine batches, CSRF protection, security headers.
Wait time is an ESTIMATE (CONSULT_MIN env, default 8 min per patient). Red-flag list is a simple keyword safety net, not a medical triage tool.

## v3: Hindi/English + more pages
Language toggle (top right: हिन्दी / English). Public pages (no login): /departments, /department/<name>, /doctors (who is available), /lab-services (pathology tests),
/medical-store (medicine stock), /help. Doctors set Available / Break / Leave; admin can too (/admin/manage). Lab orders, patient reports (/reports), pharmacy dispensing.
Hindi covers page text and form labels. Live-timeline text (updated by JavaScript) and pop-up messages are still English.
Doctors, lab tests and medicine stock are SAMPLE data.

## v4: AI layer + SGMH branding
/assistant: hospital-approved RAG assistant (local retrieval over ai.py KB; ANTHROPIC_API_KEY optional for phrasing, emergency keywords short-circuit to 112/108). Admin: AI insights (delay prediction vs. per-stage averages, uncollected-sample signals, next-day load forecast). /about: SGMH facts from ssmcrewa.ac.in. Logo: put the official file at static/img/sgmh-logo.png (falls back to hotlinking ssmcrewa.ac.in).

## v7: React frontend + REST API
Backend: `api.py` adds JSON endpoints under `/api/v1` (signed bearer-token login, doctors, slots, book, appointments, live visit, assistant, admin stats). Old Flask pages still work.
Run backend: `python app.py` (port 5000). Run frontend: `cd frontend; npm install; npm run dev` -> http://localhost:5173 (Vite proxies /api to Flask).
Stack: React 18, Vite, React Router (role-guarded routes), TanStack Query (4 s live polling), Tailwind v4, Recharts.
Screens in React: login, patient home, booking (symptom -> department suggestion + red-flag alert), live visit tracker, assistant, admin dashboard.

## v8: real SGMH doctors
`doctors_data.py` holds 11 real faculty profiles (Medicine, Orthopaedics, Paediatrics, Gynaecology, Cardiology, ENT) copied from the public department pages of ssmcrewa.ac.in: name, designation, degree, official photo URL. Existing databases are migrated automatically on start (no need to delete smartsgmh.db).
Individual phone numbers and per-doctor OPD timings are not public, so the UI shows the hospital number 07662-241655, OPD hours (Mon-Sat 8-4) and the next free slot from this app. Doctor LOGIN phones (9000000041...) are still demo accounts, not the doctors' real numbers.
React: new public page /doctors, and photo cards in the booking flow.

## Photos
Run once on a PC with internet: `python download_photos.py` -> saves official photos to frontend/public/doctors/. The app shows local photo first, then the official URL, then initials.

## v10: UI upgrade
Landing page, sticky glass header, Hindi/English toggle (src/i18n.jsx), 4-step booking wizard with animated transitions, live tracker with QR code + progress bar + timeline (framer-motion, lucide-react, react-qr-code), skeleton loaders. After the update run `npm install` in frontend/ once.

## v11: hospital portal home page
Government-portal style home: utility bar (helpline, email, language), notice ticker, hero, 12 quick-service cards, About, 3 department groups (24 depts), official Super Speciality OPD time-table, OPD/IPD timings, facilities, FAQ accordion, contact + Google Maps, and a full footer with official links. Content lives in frontend/src/data/hospital.js (facts from ssmcrewa.ac.in only). Cards for Track patient / Lab services / Medical store open the Flask pages on port 5000 (keep the backend running).

## v12: more pages in React
New React pages: /track (family tracking with code + last 4 digits, no login), /lab-services (searchable test catalogue), /medical-store (searchable stock with status). New API: POST /api/v1/track (guest token limited to that one visit), GET /api/v1/lab-services, GET /api/v1/medicines.
Admin dashboard v2: KPI cards, funnel + department donut, AI insights (tomorrow's load, avg time per stage, delay risk, uncollected samples), stock/expiry alerts, doctor availability, audit-chain verification badge and recent audit trail.


## v13: ONE server (Flask serves the React app)
Run only the backend: `python app.py` (or double-click start.bat), then open http://127.0.0.1:5000 . Flask serves the built React app at /app/ (the home page / redirects there), the JSON API at /api/v1, and the older Flask pages (staff screens) at their old paths (/reception, /doctor, /lab, /pharmacy, /login ...).
frontend/dist is already built, so Node.js is NOT needed to run. Only if you change React code: `cd frontend && npm install && npm run build` (restart not needed, just refresh).
Development with hot reload (optional, two servers): `npm run dev` in frontend/ and open http://localhost:5173/app/ (Vite proxies /api to Flask).
Doctor photos: `python download_photos.py` (saves into frontend/public/doctors and frontend/dist/doctors).

## v14: AI/ML + new look
ml.py: symptom -> department triage (TF-IDF char n-grams + Logistic Regression, scikit-learn, trained at start-up on a small hand-written sample; red-flag rules always override). Used by /api/v1/suggest, the Book form and the /app/triage page. If scikit-learn is missing the app falls back to the keyword matcher.
UI: green + saffron theme, dark hero, AI section, photo gallery. Hospital photos: see frontend/public/hospital/README.txt (hero.jpg, 1.jpg to 6.jpg).
Install new dependency once: pip install -r requirements.txt (start.bat does this).

## v15: Sanjay Gandhi Memorial Hospital only + dark tech-fest theme
Removed the Super Speciality hospital content (timetable, section, card, notices). Departments now = the hospital's own OPD list (14). Theme: dark glass UI with grid/glow background, emerald + saffron accents, Space Grotesk headings (src/index.css inverts the slate scale, so existing classes stay the same).

## v16: full-site Hindi / English
The language button (top right) switches the WHOLE React site. src/hi.js holds the English->Hindi dictionary; src/autoTranslate.js translates every visible text node, placeholder and title, including text that appears later (API data, route changes), and restores English when you switch back. To translate a new string, add one line to src/hi.js. The assistant answers in Hindi when Hindi is selected. Footer/contact now show only "Sanjay Gandhi Memorial Hospital, Rewa (M.P.) 486001".
