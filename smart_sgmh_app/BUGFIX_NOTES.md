Smart SGMH / Arogya Path — bug-fix notes

Root cause found for the blank page:
- frontend/src/landing.jsx referenced `lang` in the Departments section but did not read it from `useT()`.
- When React rendered that section, it could throw `ReferenceError: lang is not defined`. Since the page background is navy, the browser showed only a dark background and the floating action buttons.

Fixes in this source update:
- Read `lang` from the existing language context in Landing; preserves the existing route/component structure.
- Reuse the existing large Hindi dictionary from `src/hi.js` in `src/i18n.jsx`, instead of maintaining a second dictionary with duplicate keys.
- Make language state safe if localStorage contains an unexpected value.
- Translate additional visible homepage content and footer labels through the existing `tx()` translation helper.
- No hospital booking routes, API endpoints, or database models were intentionally removed.

Important build/run steps after extracting:
1. Open PowerShell in `smart_sgmh_app\frontend`.
2. Run `npm ci`
3. Run `npm run build`
4. Return to `smart_sgmh_app` and run `python app.py`
5. Open `http://127.0.0.1:5000/app/`

Why rebuilding matters:
Flask serves the compiled frontend from `frontend/dist`. Editing source files alone does not change the page served by Flask; `npm run build` must complete successfully after these changes.

Verification limits:
- Updated JSX files passed a syntax transpilation check, and Python source files passed syntax parsing.
- A full Vite build and live browser end-to-end test could not be completed in this environment because npm dependency installation timed out and the local npm cache lacked a required package. Please run the build on the same machine where `npm ci` works, then test language switching, login, OPD booking, token and existing features.
