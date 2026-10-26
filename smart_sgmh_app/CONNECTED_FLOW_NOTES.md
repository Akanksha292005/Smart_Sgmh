# Connected flow: Patient <-> Doctor <-> Pharmacy <-> Lab

1. Patient books (OTP login) -> Doctor logs in (/login) -> /doctor shows Today / Upcoming / Past appointments.
2. Doctor note form now has a real **Follow-up date** and **Tests advised** (checkboxes). On save the doctor gets a
   warning if a medicine clashes with the patient's allergy or condition (sample rules in safety.py RISK_RULES).
3. On **Approve**: the patient account gets one message (follow-up date, tests, pharmacy reminder), advised tests appear
   in the Lab queue as "Ordered", and the prescription appears in the Pharmacy queue.
4. Pharmacy enters the batch of each medicine given (/pharmacy/verify). Checks: on prescription, expiry, allergy,
   patient condition, duplicate, stock. Success -> patient sees "Medicine given". Failure -> red ALERT on the patient account.
   "Mark all dispensed" is blocked until at least one verified medicine is recorded.
5. Lab releases a report with patient code + sample barcode. Wrong patient -> report blocked, alert to the patient
   (without naming the other patient) and to doctor/nurse (/alerts). Correct -> "Lab report ready" + visible in /reports.

Patient sees everything in: /notifications (alerts in red), /rx/<code>, /reports, /patient/<code>.
Rules table (RISK_RULES) is SAMPLE only: a hospital pharmacist/doctor must approve the real list.
Tests: python tests_connected.py

## Staff login with SGMH ID card (new)
- Staff (doctor, reception, lab, pharmacy, nurse, admin) sign in at /login with **phone + password + ID card code** (type it or scan the card QR).
- The card belongs to ONE person (SGMH-DR-0006-XXXXXXXXXX). Wrong card, someone else's card, password only, or card only: login fails.
- Patients cannot use staff login (OTP on /start only). 5 wrong tries lock that phone for 15 minutes. Every failure is in the audit log.
- Admin: /admin/cards -> Issue / Replace / Revoke. Replacing or revoking a card signs that person out on their next click (web and API).
- First set-up: `python issue_cards.py` (cards for all staff without one -> staff_id_cards.html, then DELETE that file). Lost admin card: `python issue_cards.py --reissue <admin phone>`.
- Demo role switcher (/tour/as/..) and /demo/start cannot create staff sessions while the card check is on.
- Session key: no longer the public default; SECRET_KEY env, or a random key saved in secret_key.txt on first start (keep it private).
- Demo cards for the sample accounts: DEMO_CARD_CODES.txt. Tests: python tests_staffauth.py
- STAFF_ID_CARD_REQUIRED=0 turns the check off (only for old automated tests; prints a warning).
- React page /app/staff-access still has no card field: staff must use /login.

## Recall, Flag and lab PDF (new)
- **Doctor Recall** (note page, after Approve): reason is required. The prescription goes back to "not approved", the pharmacy can no longer dispense it, the patient gets a red ALERT, doctor/nurse get an alert (critical if some medicine was already handed over), and it is saved in the audit log (RX_RECALLED). Edit + Approve again to issue a corrected one.
- **Pharmacist Flag** (/pharmacy, "Something looks wrong?"): choose a reason (need to confirm / looks wrong / doctor says he did not write this / other). Dispensing and "Mark all dispensed" are paused, doctor + nurse see a CRITICAL alert (auto-escalates if nobody answers), the patient gets a calm message. The prescribing doctor either **"Yes, I wrote this: confirm"** (clears flag) or **Recall**. Audit: RX_FLAGGED, RX_CONFIRMED.
- **Lab PDF**: /lab "Verified report entry" accepts an optional PDF (max 5 MB) with or without result text. Same patient/sample match check runs first; a wrong-patient report is blocked and no file is stored. Only real PDFs are accepted (extension + %PDF header; PDFs with scripts/attachments are rejected). Stored outside the web root, opened at /report-file/<id> only by that patient, their tracked code, or staff; served with nosniff + sandbox headers.
- Tests: python tests_rx_controls.py (43 checks).
- Also fixed: React home "Doctors on app" showed "-" while loading (now "90+"); garbled emoji in the critical-alert popup.

## IPD: refer, emergency admit, chart, discharge summary (new, ipd_care.py)
- **Doctor refers to admission**: OPD note page -> "Admit to hospital (IPD)" (ward, planned/urgent, reason). Creates an IPD request linked to the OPD visit; diagnosis, OPD medicines, tests and allergy are copied into the first chart entry; the patient gets a message with the code. Reception sees a "Doctor referral" badge and only has to give a bed (photo ID + bed as before).
- **Emergency admit** (/emergency; reception, nurse, doctor, admin): no booking, no doctor needed first. Triage (Red/Orange/Yellow), main problem, bed, optional first aid given, optional UHID. Unknown patients get a temporary UHID ("Unknown male (~40 yrs)"). Never blocked by a full ward. Duty doctor gets a CRITICAL (Red/Orange) or WARNING alert; the patient shows "Doctor review pending" (board, doctor page banner, chart) and **cannot be discharged until a doctor files the first assessment**. Later: /ipd/<code>/identify fills in the real details, or links the treatment to the patient's real UHID (temporary record is closed, all notes stay).
- **IPD chart** (/ipd/<code>/chart; doctor, nurse, admin): casualty entry, admission note, daily rounds, procedure notes, nursing notes. Medicine orders go to the same pharmacy queue as OPD (same allergy/risk checks, same flag/recall), tests go to the lab, vitals use the existing nurse form. "Time of event" lets staff record treatment given earlier; both times are shown. A doctor can tick "taking over as treating doctor".
- **Discharge summary** (/ipd/<code>/summary/edit -> /summary): prefilled from the chart, doctor edits and approves, then patient/family see it on the Visit page and can print/save as PDF. `IPD_SUMMARY_REQUIRED=1` makes an approved summary mandatory before reception can discharge (default: only a reminder).
- **IPD board** (/ipd/board): everyone admitted, who waits for a doctor (red after EMERG_WAIT_WARN_MIN, default 15), latest vitals level, open alerts, summary status. Reception sees the board without clinical columns.
- Triage list, wait threshold and wards are SAMPLE values; the hospital must confirm them. Not yet done: Hindi wording for the new pages, React /app screens. Tests: python tests_ipd_care.py (71 checks).

## Medicine record (MAR), shift-aware duty, patient/family A-to-Z view (ipd_mar.py, wardduty.py)
- **Patient / family view**: no separate family login. The Visit page of the patient's own account (or Track with code + last 4 digits of the phone) shows the whole stay: patient + health notes + allergy, admission (type, ward, bed, OPD origin link), journey stages, who is on duty NOW, diagnosis, every medicine with each dose (time, nurse, given / held / refused / delayed), tests and reports, vitals in words with who checked, all doctor and nurse notes with names and times (plus the doctor's "Message for family in simple words"), safety alerts and who acknowledged them, emergency waiting time and who examined the patient, discharge summary. Refreshes every 20 s (/ipd/<code>/family).
- **MAR**: each medicine line a doctor writes on the IPD chart becomes an order. The nurse records each dose (given / held / refused, with reason). Frequency is read from the text (OD, BD, TDS, QID, "twice daily", "every 6 hours", q4h, SOS). A scheduled dose not recorded within MAR_GRACE_MIN (30; first dose MAR_FIRST_GRACE_MIN 60) raises ONE alert naming the duty nurse, closes when the dose is given, and escalates to every doctor and nurse like other critical alerts. Giving a dose before half the interval has passed needs "give anyway". Held / refused doses alert the doctor. The doctor can stop a medicine.
- **Shift-aware duty**: Morning 8-14, Evening 14-20, Night 20-8, All day. "On duty now" (care-team card, alerts "Sent to", family view, chart) lists only staff whose shift is running. The sample nurses/roster are created only when DEMO_MODE=1 (default); set DEMO_MODE=0 in production and enter the real roster at /admin/ward-duty.
- Escalation now covers EMERGENCY_ADMIT, MED_DOSE_OVERDUE and MED_NOT_GIVEN as well as DETERIORATION.
- Rolling schedule: next dose = last recorded dose + interval (not fixed clock times). Pharmacists/doctors must confirm the rules before real use. Tests: tests_ipd_mar.py (70 checks).
