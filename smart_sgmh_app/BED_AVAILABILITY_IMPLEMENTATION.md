# Bed Availability / ICU / Paediatrics module

## Added in this build
- React page: `frontend/src/Beds.jsx`, reachable at `/beds`.
- Navigation links from desktop/mobile navigation, footer and landing service cards.
- SQLite table `bed_inventory` initialized by `app.py` with ward/unit names but **without invented bed counts**.
- Public read API: `GET /api/v1/beds`.
- Admin-only update API: `POST /api/v1/beds/update` with bearer-token authorization, validation and audit event.
- UI shows counts only after an authorized staff member records them; unverified counts stay blank.

## Safety and data integrity notes
- The unit names are starting labels and must be confirmed against the hospital's actual structure. Remove or rename NICU/PICU/HDU entries if not confirmed by authorized hospital staff.
- Do not enter fictional counts and present them as real. For a judging demo, explicitly say this is sample/demo inventory.
- Available = total - occupied - unavailable. API validates non-negative integers and prevents occupied + unavailable from exceeding total.
- The current upgrade automatically reconciles occupancy on IPD admission/discharge for unambiguous mappings only: `General ward` → `General Ward`, `Maternity ward` → `Maternity Ward`, and `Paediatric ward` → `Paediatric Ward`. The appointment status and occupancy reconciliation use a SQLite transaction.
- `ICU / HDU` remains unmapped because the existing admission form does not distinguish ICU from HDU. `Private room` is also unmapped because no matching inventory unit exists. Confirm the actual hospital structure before extending the mapping.
- If capacity is configured for a mapped ward, a new admission is blocked when active admissions plus unavailable beds would fill the capacity. If capacity is not configured, the existing admission workflow remains available, but public counts remain unverified.
- Regression checks were added to `tests_ipd.py` and `tests_beds_api.py`. Run them in an environment with `requirements.txt` installed.
- The page's 30-second refresh is not a guarantee of real-time hospital-system integration. Users should confirm bed availability with the admission desk. Emergency care must not be delayed while checking this page.

## Verify locally
1. Install backend dependencies in a virtual environment: `python -m pip install -r requirements.txt`.
2. Run `python -m compileall -q .`.
3. Start backend with `python app.py`.
4. Install frontend dependencies: `cd frontend && npm ci`.
5. Build frontend: `npm run build`.
6. Login to React as an admin using the configured demo account only in a local demo environment, open `/beds`, and save a test count for a unit.
7. Verify public counts update and invalid counts are rejected; verify a non-admin token receives 403 from `POST /api/v1/beds/update`.
8. Reset any test counts before presenting; do not use real patient-identifiable data in the demo.
