"""Run once on your own PC (needs internet): python download_photos.py
Downloads each doctor's official photo from ssmcrewa.ac.in into frontend/public/doctors/<slug>.jpg, so the app works offline."""
import os, re, urllib.request, urllib.parse
from doctors_data import DOCTORS

BASE = os.path.dirname(os.path.abspath(__file__))
OUTS = [os.path.join(BASE, "frontend", "public", "doctors"), os.path.join(BASE, "frontend", "dist", "doctors")]  # public/ for rebuilds, dist/ so it works right now
for o in OUTS: os.makedirs(o, exist_ok=True)
slug = lambda n: re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")
ok = 0
for _, name, dept, _, _, url in DOCTORS:
    u = urllib.parse.quote(url, safe=":/")  # photo paths contain spaces
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://ssmcrewa.ac.in/"})
    try:
        data = urllib.request.urlopen(req, timeout=20).read()
        [open(os.path.join(o, slug(name) + ".jpg"), "wb").write(data) for o in OUTS]; ok += 1
        print("OK  ", name, f"({len(data)//1024} KB)")
    except Exception as e:
        print("FAIL", name, "->", e, "\n     Save the photo manually as", slug(name) + ".jpg", "in", OUTS[0])
print(f"\n{ok}/{len(DOCTORS)} photos saved.")
