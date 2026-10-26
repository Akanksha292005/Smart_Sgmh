"""Seed clearly labelled demo bed counts for a local academic presentation.

This script never overwrites an existing verified inventory. Values are fictional
and must not be used for real admission or clinical decisions.
"""
import os
import sqlite3
from datetime import datetime

DB = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "smartsgmh.db"))
DEMO_ACTOR = "DEMO SAMPLE DATA - NOT REAL HOSPITAL DATA"
SAMPLE = [
    ("General Ward", 100, 65, 5),
    ("ICU", 20, 12, 2),
    ("HDU", 15, 8, 1),
    ("Paediatric Ward", 30, 18, 2),
    ("NICU", 12, 7, 1),
    ("PICU", 10, 5, 1),
    ("Maternity Ward", 25, 14, 2),
]

def main():
    if not os.path.exists(DB):
        raise SystemExit(f"Database not found: {DB}. Check that you are running the script from the correct project folder.")
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    con = sqlite3.connect(DB)
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("""CREATE TABLE IF NOT EXISTS bed_inventory(
            id INTEGER PRIMARY KEY, unit_name TEXT UNIQUE NOT NULL,
            total_beds INTEGER, occupied_beds INTEGER NOT NULL DEFAULT 0,
            unavailable_beds INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT, updated_by TEXT,
            CHECK(total_beds IS NULL OR total_beds >= 0),
            CHECK(occupied_beds >= 0), CHECK(unavailable_beds >= 0),
            CHECK(total_beds IS NULL OR occupied_beds + unavailable_beds <= total_beds)
        )""")
        for unit, _total, _occupied, _unavailable in SAMPLE:
            con.execute(
                "INSERT OR IGNORE INTO bed_inventory(unit_name,total_beds,occupied_beds,unavailable_beds,updated_at,updated_by) VALUES(?,NULL,0,0,NULL,NULL)",
                (unit,),
            )
        rows = con.execute(
            "SELECT unit_name,total_beds,updated_by FROM bed_inventory"
        ).fetchall()
        existing_real = [r[0] for r in rows if r[1] is not None and not str(r[2] or "").startswith("DEMO SAMPLE DATA")]
        if existing_real:
            raise SystemExit(
                "Stopped to protect existing inventory: some bed counts already exist. "
                "No changes were made. Back up the DB and review it manually before reseeding."
            )
        for unit, total, occupied, unavailable in SAMPLE:
            con.execute(
                """INSERT OR IGNORE INTO bed_inventory(unit_name,total_beds,occupied_beds,unavailable_beds,updated_at,updated_by)
                   VALUES(?,NULL,0,0,NULL,NULL)""", (unit,)
            )
            con.execute(
                """UPDATE bed_inventory SET total_beds=?,occupied_beds=?,unavailable_beds=?,updated_at=?,updated_by=?
                   WHERE unit_name=?""",
                (total, occupied, unavailable, stamp, DEMO_ACTOR, unit),
            )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    print("Demo bed data saved successfully.")
    print("IMPORTANT: These are fictional academic demo values, not hospital data.")
    for unit, total, occupied, unavailable in SAMPLE:
        print(f"{unit}: total={total}, occupied={occupied}, unavailable={unavailable}, available={total-occupied-unavailable}")

if __name__ == "__main__":
    main()
