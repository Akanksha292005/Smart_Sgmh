# v34: no direct IPD admission on the home page + Hindi / English on the admission pages
- **Home pages:** the "Admission info" tile and the "IPD: Admission Info" quick card are removed from the React home page (`src/landing.jsx` and the built `dist`). The Flask menu no longer shows an "IPD" link to patients or the public (staff still see it); "How admission works" stays in the Services menu as information only. Wording changed from "IPD admission: 24x7" to "Emergency admission: 24x7" in the top bar, footer, About, Help, React notices, facilities and FAQ. Admission itself is unchanged: only the DOCTOR (OPD note page) or the emergency team can admit; `/admit` still only redirects to the info page.
- **Hindi / English:** new `i18n_admit.py` (about 130 sentences plus phrase patterns) covers the pages that were still English in Hindi mode: /ipd, /opd, /emergency, /ipd/board, /wardview, /beds, /alerts, /privacy, /workflow, access-denied pages, doctor tabs, lab, pharmacy and admin dashboard labels. It is loaded in `registration.py` with `setdefault`, so older translations win. React: new `src/hi_extra.js` (merged in `i18n.jsx`); the Beds page (`src/Beds.jsx`) now uses `tx()` everywhere instead of fixed Hinglish text, the notice ticker, address and email on the home page are translated.
- **Not translated on purpose:** judge-only pages (/demo, /tour), doctor and patient names, demo data, drug names, codes.
- **React rebuild:** `frontend/dist` was patched (home tiles, wording, Hindi for the new sentences). The Beds page and other `src` changes only show in the site after `cd frontend && npm ci && npm run build` (the dist in this zip is older than `src`).
- Tests: new `tests_admit_hi.py` (30). Existing suites unchanged; `tests_ward.py` has 1 failure ("visit shows care team") that was already there in v6.

# v33: doctor-led admission, ward duty, ward-wise alerts, ward view (workflow for the tech fest)
- **Patients no longer request IPD.** `/admit` now sends to the IPD info page (`/ipd`); the IPD tile, tabs, doctor-card button and React/menu links were removed or relabelled "How admission works". Admission happens only (1) when the DOCTOR presses "Admit to hospital (IPD)" on the OPD note page (ward + urgency; diagnosis, medicines, tests and allergy go to the ward), or (2) through `/emergency` (reception / nurse / doctor) when OPD is closed or the patient is serious. Reception still gives the bed after a photo-ID check.
- **Ward duty roster** (new `wardduty.py`, `/admin/ward-duty`, admin): each nurse and doctor gets ward(s) + shift. A SAMPLE roster and three sample nurses (9000000061 ICU, 9000000062 Maternity, 9000000063 Paediatric, password nurse123) are created on first start only if the roster is empty. Run `python issue_cards.py` once so the new nurses get ID cards. Enter the real roster before real use.
- **Ward-wise alerts:** an alert about an admitted patient goes to the treating doctor, the duty doctor on the care team, and the doctors and nurses on duty in THAT ward. Not acknowledged in ESCALATE_MIN minutes = escalated to every doctor and nurse. Admin sees all. A nurse with no ward set sees all alerts (fail-safe). Each alert shows "Sent to: ...". Acknowledging another ward's alert is refused (403). Applies to `/alerts`, the pop-up feed and the alert count.
- **Auto care team:** on admission (reception bed, emergency admit) the care team (duty doctor, duty nurses, shift, family attendant from the admission) is filled from the roster. Staff can still edit it at `/ward/<code>`. The patient's Visit page shows ward, bed and team.
- **Ward live view `/wardview`** (doctor, nurse, admin): one tab per ward with duty staff and every admitted patient: bed, diagnosis, treating doctor, latest vitals, open alerts, "doctor review pending", care team. Most serious first, refreshes every 60 s. Menu: My workspace > My ward.
- Emergency admit now picks the duty doctor of the chosen ward first (then the department doctor).
- `/workflow` shows the 3-part journey: OPD, doctor admits (IPD), OPD closed (emergency). Hindi added for the new pages.
- Tests: new `tests_wardduty.py` (36). Updated for the new flow: tests_ipd (16), tests_ward (39), tests_flow (70), tests_merge (58), tests_registration (123), tests_ipd_care (71). All other tests unchanged and passing.
- React `frontend/dist` was patched (labels only), not rebuilt; `src` has the same changes, so a later `npm run build` keeps them.

# v32: v31 + responsive pass (phone, tablet, laptop)
- Checked 320, 375, 768, 1024, 1440 px on every page for every role: no element goes outside the screen now.
- Flask pages: words no longer split in the middle in tables / booking steps; tables scroll sideways inside their own box; tour bar menu stays inside the screen; extra tablet and 320 px rules; hover lift off on touch screens; reduced-motion respected.
- React site: between 1024 and 1279 px the 9 menu links did not fit and pushed "Book OPD" off screen, so the menu button is used there; on phones the hero photo has a darker overlay so buttons and numbers can be read.
- CSS only. Same rules are in `frontend/src/index.css` and in the built `frontend/dist` CSS, so no rebuild is needed (a later `npm run build` keeps them).

# v31: v30 + real SMS OTP (MSG91 / Fast2SMS / Twilio) + phone-friendly layout
- NEW `sms_gateway.py` (standard library only). Set `SMS_PROVIDER` = msg91 | fast2sms | twilio and its keys (see the top of the file). When a gateway is configured `OTP_MODE` becomes `sms` by itself: the OTP goes by SMS and is never shown on screen. Without a gateway the old demo mode stays (testing only). `OTP_MODE=off` still skips OTP.
- India: OTP SMS needs a DLT-registered sender ID and template (TRAI). Do the DLT steps in the provider's dashboard first, then send ONE real test SMS with your own key (this build was tested with the HTTP call mocked, not against live gateways).
- OTP limits (sms mode): `OTP_COOLDOWN_SEC` 30, `OTP_PER_HOUR` 5 per mobile number, `OTP_PER_IP_HOUR` 30 per device address. Behind nginx/another proxy, pass the real client IP (ProxyFix) or the device limit will see only the proxy.
- If the gateway fails the patient sees a plain message, the reason goes to the server log only (never the OTP or a full number), and no OTP is left in the database. `SMS_NOTIFY=1` also sends booking / registration messages (Twilio, or Fast2SMS dlt_manual).
- Phone layout: React header has a menu button and a one-line top bar, the 3 floating buttons became one compass button, quick cards and blood strip fit 320 px; Flask pages got a phone CSS block (stacked search forms, smaller hero, safe-area for notches, 16 px inputs so iPhones do not zoom). Rebuilt `frontend/dist` (run `npm ci && npm run build` in `frontend/` after any change to `src`). Checked at 320, 375 px (no sideways scroll) and desktop.
- Tests: new `tests_sms.py` (39). tests_flow 71, tests_registration 123, tests_ward 38, tests_merge 57, tests_tour 39 all pass.

# v30: v29 + the website is open to everyone; login only when needed
- `/` and the first page are now the full website (/app/): hospital info, doctors, OPD, IPD, blood bank, map, workflow, assistant, triage, tracking all open with NO login.
- Login (name + mobile + OTP, and the password for registered accounts) is asked only for personal actions: Book OPD, IPD admission request, my visits / reports / family / history, upload of old prescriptions or records. The page the patient wanted is remembered (with the chosen doctor) and opened right after login; at the first booking the registration details + password step follows (unchanged).
- OPD hub (/opd): how OPD works, every doctor with a department filter, "Book OPD" per doctor (no IPD buttons there). IPD (/ipd) is a separate process with its own page. The landing page, header "Book OPD" button and the quick bar now open these hubs instead of a login screen; /app/book goes to /opd.
- A logged-in patient sees a welcome line on the website with My home / History / Records.
- Tests: tests_flow 71, tests_registration 123, tests_ward 38, tests_merge 57, tests_tour 39 all pass.

# v29: v28 + photo data merged into ONE system, with a workflow page and a judge tour
- BASE = v28 (start/OTP journey, home tiles, blood bank, care team, signed death certificate, Aadhaar check, Hindi). The earlier separate blood bank / IPD stay / death certificate code of v25b was DROPPED because v28 already has the same features, tested; only the signboard data was ported.
- From the hospital signboard photos (v25): `opd_roster.py` (weekday roster, rooms, paediatrics 8:30-1:30), doctors sit only on their days (booking shows other days as off), doctor cards show days and room, `hospital_map.py` Ground/First floor follow the real floor plans (second floor, ICU, wards, cardiology, labs, blood bank still marked "[to be confirmed]"). Lines tagged `# CHECK` in opd_roster.py need a look against the real boards.
- NEW `/workflow` (public): the whole journey on one page (OPD, IPD, outcome, certificate, verify), safety net, who sees what. Hindi supported (i18n_tour.py). Linked from the top menu, the home tiles, the login page and the React top bar.
- NEW `/tour` (judge tour, only when DEMO_MODE=1): "Load story" makes one admitted patient (AP-TOUR1, 3 days in the General ward); 10 steps, each button signs in as the right role and opens the right screen; steps tick themselves (care team saved, death recorded, certificate). Sample values are shown. A small "Judge tour" bar on every page shows the current role and switches role. Set DEMO_MODE=0 in production and all of this disappears.
- Tests: tests_tour.py (39 new) + tests_ward 38 + tests_registration 123 (now roster aware) + tests_flow 49 + tests_merge 57: all pass.
- Demo logins (DEMO only): patient 9000000001 / pat123, reception 9000000010 / rec123, doctor 9000000041 / doc123, lab 9000000020 / lab123, pharmacy 9000000030 / ph123, admin 9000000000 / admin123.

# v28: v27 + v26_1 merged, easier for a free government hospital, Aadhaar / Ayushman check
- MERGE: v27 already contained everything in v26_1 (no route or page was missing), so v27 is the base. First page is still /start (login / OTP sign-up); after login every service is visible.
- /home now has a big-tile grid "What do you need today?": see a doctor, EMERGENCY 112/108, admit (IPD), blood bank, find the way, my visits and slips, upload old prescription, reports, medicines in stock, lab tests, my family, verify Aadhaar/Ayushman, assistant, track a patient. The login page also shows public tiles (blood bank, map, doctors, departments, help, assistant, emergency) so nobody needs an account just to look.
- FREE-SERVICE notice: "All services at this government hospital are free. Do not pay anyone for an appointment, slip, bed or report. If anyone asks for money, tell the help desk." on the login page, home and booking page, and "All services free" in the top bar. This is the hospital's statement; set FREE_SERVICES=0 if any service is charged, or edit FREE_NOTE in ease.py.
- Easier to use: Hindi shown first to a new visitor on the login page (language switch stays); A+ bigger-text button on every page (remembered); microphone button to SPEAK the problem (booking reason box, assistant) in Hindi/English (needs Chrome + internet); bigger buttons and fields for phones; "No phone? Go to the Registration counter, staff register you free" note.
- Aadhaar / Ayushman document check (/verify patient, /admin/verify reception): Aadhaar 12 digits + Verhoeff checksum, card photo read by OCR (needs Tesseract installed) for number + name, duplicate-number flag, reception approves or rejects with a reason. Full number is never stored (last 4 digits + hash), photo is private and deleted when staff decide. Verified badge shows on the patient's home and on the doctor's page. NOT government e-KYC: it cannot confirm with UIDAI or NHA that a card is genuine or that Ayushman cover is active.
- Tests: tests_merge.py (57 new checks) + tests_flow (49) + tests_ward (38) + tests_registration (123): all pass.
- Files added: ease.py, idverify.py, idcheck.py, i18n_ease.py, templates _free/_pub/_services/verify/verify_admin. Changed: base.html, _gate.html, home.html, note.html, app.py (two import lines).

# v27: patient journey, OTP start page, SGMH colours (on top of v26)
- First page is /start: name + mobile + OTP (OTP is shown on screen in demo mode; plug an SMS gateway into registration.deliver_otp()). New patients get an account; after the first registration the account is protected: OTP + password are both needed, 5 wrong tries lock the number for 15 minutes.
- /home: "Welcome, <name>", next step, 5-step journey, doctors already consulted, recent visits (date, what was found, tests, medicines; advice appears only after the doctor approves it), own records.
- Choosing a doctor for the first time opens /register/details (full details + password, UHID issued there), then booking continues with the same doctor. /book shows earlier visits with the chosen doctor; /appt shows "What happens next".
- /history and /records (upload old prescriptions or reports: PDF/JPG/PNG up to 5 MB, checked by file signature; owner, doctors, reception, nurses and admin can open them; doctor's note page lists them).
- Patients can no longer log in with /login or the React login (staff only); /app/login redirects to /start; React pages reuse the Flask login through /api/v1/me-token.
- Colours taken from the SGMH photo: navy #0a3569, sky #309ced, grey-white, green only for "available / success".
- Tests: tests_flow.py (49), tests_ward.py (38), tests_registration.py (123). Hindi for the new pages in i18n_flow.py.

# v26: tested + Hindi + homepage blood strip (on top of v25)
- Tested end to end (tests_ward.py, 38 checks + the 123 registration checks): blood bank view/update/permissions, care team save + family view, death record (wrong password, future time, before admission, missing cause all rejected), signed certificate, public verify page, tamper detection (FAILED / not GENUINE), blocking of discharge/orders after death.
- Hindi: every new page (blood bank, care team, death form, certificate, verify, visit) is now fully Hindi when the language is Hindi (i18n_care.py; dynamic text such as bed numbers, dates and shifts handled by phrase patterns in app.py `PAT`). Names, codes, UHID and "OPD" stay as they are.
- Homepage: a live "Blood bank: which blood group is available now" strip under the quick-action bar (8 groups, Available / Low / Not available with the number of units, "may be outdated" warning after 12 h). Added in nav-extras.js + index.css, no React rebuild needed.

# v25: Blood bank stock, IPD care team, death record + digitally signed certificate, Hugging Face assistant
- Blood bank: public page /blood-bank (also in Services menu and React top bar + floating button). 8 groups: Available (10+), Low (1-9), Not available (0), with "updated at" and "may be outdated" after 12 h. Lab/admin staff update units on the same page. Demo numbers are SAMPLE until staff enter real stock.
- Care team of an admitted patient: /ward/<IPD code> (reception, nurse, doctor; link in Reception and Doctor lists): duty doctor, duty nurse, ward attendant, shift, family attendant. Family sees it on the Visit page (phone only for logged-in users).
- Death record + certificate: doctor opens "Record death" in the Doctor list (IPD rows). Enters time of death, causes, manner, registration number, and re-types the password to sign. System computes how long the patient stayed (days + hours from the admission event), copies the care team as at that moment, makes a certificate with a number and verify-QR (/death/verify/<token>), locks the record (status deceased), and queues a family notification.
- After death is recorded, new vitals, lab results, dispensing and test orders for that patient are BLOCKED and raise a critical AFTER_DEATH alert (stops billing/activity after death).
- Accident/suicide/homicide/pending = medico-legal: certificate says police intimation is required.
- Signature = HMAC-SHA256 with SECRET_KEY: proves the text is unchanged (tamper shows FAILED / TAMPERED). SET A STRONG SECRET_KEY in production, otherwise signatures can be forged.
- IMPORTANT LIMIT: this is the hospital's digitally signed death SUMMARY. It is NOT the statutory death certificate (that is issued by the Registrar of Births and Deaths on registration; the hospital doctor's Medical Certificate of Cause of Death feeds it) and the signature is not a legal DSC / Aadhaar eSign. The hospital must confirm current rules and forms before real use. Corrections after signing are not supported yet (needs an admin amendment process).
- Assistant now uses Hugging Face (set HF_TOKEN; optional HF_MODEL, default Qwen/Qwen2.5-7B-Instruct) with emergency-word bypass and offline fallback; blood-availability questions point to the Blood Bank page.
- NOTE: this zip (your v24 lineage with registration/UHID) does NOT contain the earlier Aadhaar/Ayushman document verification or the old-prescription upload from my previous v23/v24; those lived in a different copy.

# v22: patient registration + smart booking (government-hospital version)

Booking now works like a large hospital's flow (register, choose who the visit is for, doctor, time, confirmation with all patient details), but built for a PUBLIC hospital: no online payment, no packages or upselling, walk-ins are first-class, and privacy is strict.

**For patients** (`/register`, `/family`, `/book`, `/appt/<code>`, `/mine`, `/notifications`)
- Registration with mobile OTP. Gives a **UHID** (Unique Health ID). Fields: name, gender, DOB or approximate age, guardian, address (village/ward, district, PIN), category (General / BPL / Ayushman Bharat PM-JAY / other scheme), optional ABHA and PM-JAY numbers, differently-abled flag, allergies, conditions, blood group, emergency contact, language, SMS and data consent.
- **Family profiles**: one login can book for parents and children, each with own UHID, allergies and history.
- Booking steps: Patient > Department > Doctor > Date and time > Confirm. Department is suggested from symptoms AND age/sex (child under 12 > Paediatrics, pregnancy > Gynaecology). Each day shows how many slots are free; "Earliest available" button.
- **Priority queue**: senior citizen (60+), pregnant woman, differently-abled, infant go first among arrived patients (SAMPLE policy, the hospital must set the real one).
- Confirmation page with every patient detail, room and floor, "Please bring" checklist built from the patient's category, printable OPD slip, calendar file (.ics), reschedule (max 3 times), cancel, feedback after the visit.
- Duplicate guards: same patient + doctor + day is refused; a slot can never be double booked (database unique index plus a check).

**For reception** (`/reception`, `/staff/patients`, `/staff/patients/new`, `/staff/walkin/<UHID>`)
- Walk-in registration without a smartphone or booking: search by UHID / mobile / name, warn about duplicate records, register, pick doctor, token is issued at once. A walk-in record is linked automatically if the patient later registers online with the same mobile and name.
- After "Mark arrived" a **verify panel** shows name, age/sex, UHID, category, priority, allergy and the documents to check.

**Privacy (read this before real use)**
- Role-based views: reception sees identity/address/scheme; a doctor sees age, sex, allergies, conditions and ONLY for patients who have a visit with that doctor; lab and pharmacy cannot open profiles.
- Every profile view, search and slip print by staff goes into the hash-chained audit log. Search text is not logged.
- Full Aadhaar number is never stored (optional last 4 digits only). Phones are masked on screen. OTP is stored hashed. QR codes carry only the appointment code.
- Privacy notice at `/privacy` is a draft. Hospital legal team must review it (DPDP Act 2023).

**Allergy fix**: allergies now belong to the PATIENT profile. Before, a son booking for his mother would have been checked against the SON's allergies.

**SAMPLE / not real**
- SMS is simulated: messages are saved in the `notifications` table and shown at `/notifications`. Connect the hospital SMS gateway in `sms()` and `deliver_otp()` inside `registration.py`.
- `OTP_MODE=demo` (default) shows the OTP on screen. `OTP_MODE=off` skips OTP. Never use `demo` in production.
- Fees: nothing is invented. Text comes from `OPD_FEE_NOTE` (environment variable). Priority rules, document lists and the district list are samples.
- No scheduler: day-before reminders need a cron job that calls `sms()`.

**React app**: patient registration, family and booking pages are Flask pages. `frontend/public/nav-extras.js` (also copied into `dist/`) sends `/app/book` to `/book` and adds a "New patient? Register here" link on the React login page. The React source was not changed, so no rebuild is needed.

**Tests**: `python tests_registration.py` runs 120+ end-to-end checks on a throw-away database.

Upgrade: a v21 database is migrated automatically on start (new tables and columns). Old bookings keep working.

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


## Latest upgrade notes (2026-10-23)

See [`UPGRADE_NOTES_2026-10-23.md`](UPGRADE_NOTES_2026-10-23.md) for the file-level changes, ward-mapping limits, test commands and single-server build instructions. The existing Flask app still serves both the API and the built React frontend.


## Academic demo: sample bed inventory (fictional)

If you do not have authorized hospital bed counts, you may use clearly labelled fictional values for a local college presentation only.

1. Stop the running server with `Ctrl+C` in its terminal.
2. From the project root (`smart_sgmh_app`), run `python seed_demo_beds.py`.
3. In the frontend folder, run `npm run build` so the demo-only label and the Unavailable count display are included.
4. Start the app again with `python app.py`, then refresh `/app/beds`.

The seed script refuses to overwrite inventory that appears to contain non-demo values. It marks the rows as `DEMO SAMPLE DATA - NOT REAL HOSPITAL DATA`. Never use these values for actual admissions or present them as real SGMH data. To restore an untouched database, restore your backup of `smartsgmh.db`.
