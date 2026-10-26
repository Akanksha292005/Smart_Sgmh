# Smart SGMH update notes

## Changes made
- Removed the site-wide Hindi auto-translation logic that directly edited React-managed text nodes. The safe language hook only updates the document language and title; existing React i18n labels continue to work. This prevents the known class of blank-screen/render desynchronization bugs caused by external DOM mutation.
- Updated the Flask doctor dashboard to support Today, Upcoming, Past history, Cancelled, and All bookings views, with counts. Doctor accounts are filtered to their own doctor ID; administrators retain the all-doctor view.
- Hardened the doctor lab-order route by using the existing appointment ownership check and avoiding a `None` dereference for missing/unauthorized appointment codes.

## Checks completed in this environment
- Python source compiles with `python -m compileall`.
- Built JavaScript bundle passes `node --check`.
- New doctor-dashboard SQL queries were checked against the included SQLite schema.

## Checks not completed
- Full Flask integration tests could not run here because Flask and the project's Python dependencies were not installed, and package installation was unavailable due to network restrictions.
- A fresh Vite build could not be run here because npm dependency installation timed out. The served `dist` bundle was patched for the known language-switch issue; after opening this project locally, run `npm ci` and `npm run build` in `frontend` to rebuild from source.
- Login, booking, PDF/token, maps, and other end-to-end flows still require local browser testing with demo accounts. This is a prototype and should use synthetic patient data only.
