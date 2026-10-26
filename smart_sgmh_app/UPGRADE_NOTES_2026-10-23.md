# Smart SGMH – safe upgrade notes (2026-10-23)

This update preserves the existing Flask server, SQLite database, routes, React pages, templates and assets. It does not create a second server or replace the database.

## Changes included

1. **IPD bed occupancy synchronization**
   - Admission/discharge transitions for the mapped wards update occupancy in the same SQLite transaction as the appointment status.
   - Configured mapped wards reject an admission when capacity (including unavailable beds) is full.
   - The sync uses existing `appts` records and the existing `bed_inventory` table.
   - One-to-one mappings only: `General ward` → `General Ward`, `Maternity ward` → `Maternity Ward`, and `Paediatric ward` → `Paediatric Ward`.
   - `ICU / HDU` remains unmapped because the existing admission form does not say which one of the two units is assigned. `Private room` is also unmapped because there is no corresponding inventory unit. Do not infer these mappings without hospital confirmation.
   - If no total capacity has been configured, admissions retain the prior workflow and counts remain unverified in the public page. Staff must enter a confirmed total before the public API marks counts verified.

2. **Admin bed analytics**
   - `/api/v1/admin/stats` now includes the existing inventory summary.
   - `frontend/src/admin.jsx` adds a ward occupancy panel.

3. **Bed update integrity**
   - For mapped wards, the admin update API derives occupied counts from active IPD admissions rather than trusting a manually typed occupied value.
   - For unmapped units, existing manual inventory behavior remains.

4. **ML evaluation support**
   - `evaluate_ml.py` runs a deterministic train/test evaluation and reports accuracy, macro F1, per-class precision/recall/F1, and a confusion matrix.
   - The current `ml.py` dataset is a small hand-written sample, not a 1,000+ record external dataset. The evaluation script explicitly labels results preliminary and not clinical validation.

5. **Regression tests**
   - `tests_ipd.py` includes mapped occupancy, full-capacity guard and discharge/free-capacity checks.
   - `tests_beds_api.py` covers public reads, admin authorization, invalid capacity and derived occupancy.
   - `tests_ml.py` is a model smoke test.

## Files changed / added

- Modified: `app.py`, `api.py`, `frontend/src/Beds.jsx`, `frontend/src/admin.jsx`, `tests_ipd.py`
- Added: `evaluate_ml.py`, `tests_ml.py`, `tests_beds_api.py`, `UPGRADE_NOTES_2026-10-23.md`
- All other project files are retained from the uploaded ZIP.

## Build and run

From the project root, use the same single Flask server:

```bash
python -m pip install -r requirements.txt
python -m compileall -q .
python tests_ipd.py
python tests_ward.py
python tests_beds_api.py
python tests_ml.py
python evaluate_ml.py
cd frontend
npm ci
npm run build
cd ..
python app.py
```

Open `http://127.0.0.1:5000/app/`. The React source changes must be built into `frontend/dist` before Flask can serve the updated UI. No separate Vite dev server is needed.

## Important limitations

- This remains a hospital workflow prototype. Existing project documentation says the hospital-system links and some reference data are sample/simulated.
- Only the three unambiguous ward types automatically sync. ICU/HDU and Private room need a confirmed mapping and appropriate data model first.
- Do not enter invented bed counts or present preliminary sample-based ML metrics as real hospital performance.
