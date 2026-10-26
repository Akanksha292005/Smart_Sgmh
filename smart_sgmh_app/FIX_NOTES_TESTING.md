# Testing + fixes (2026-10-25)
Tested: ~319 Flask pages x 7 roles x en/hi crawl, all tests_*.py, browser (Chromium) booking flow, fuzzed booking/API inputs: no 500 errors.
Fixed:
- Staff (doctor/reception) logged in and clicking Book OPD got a bare "Access denied": now says which account is logged in + Log out button.
- 400 (expired session/form) and 500 now show a clear error page (no raw server error).
- /app/beds, /app/staff-access and unknown /app/... URLs were BLANK (built dist is older than src): nav-extras.js now sends them to /beds, /login, /app/. New Flask page /beds (uses /api/v1/beds). "Beds & ICU" added to the top bar.
- Missing static/img/sgmh-logo.png (404 on every page) added.
- src/App.jsx: catch-all route added. Run `npm ci && npm run build` in frontend/ on your PC to rebuild dist from src.
Known: only the 11 demo doctors (9000000041..) have known passwords; other doctors need accounts from the hospital/admin.

## Round 3
Added doctor Recall, pharmacist Flag, lab PDF upload (see CONNECTED_FLOW_NOTES.md). Doctors tile fallback "90+", alert-popup emoji fix. 12 test files pass.
