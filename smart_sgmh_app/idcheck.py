"""ID document helpers: Aadhaar checksum, Ayushman number format, card-photo OCR, name match (used by journey.py).

WHAT THIS IS: a prototype *document check*, not government e-KYC. It (1) validates the number format (Aadhaar: 12 digits + Verhoeff checksum),
(2) reads the card photo with OCR and checks the typed number and the registered name appear on it, (3) flags a number already used by another account,
and (4) puts the result in a queue where reception staff compare the photo with the person and approve or reject.
It CANNOT confirm with UIDAI / NHA that a card is genuine or that Ayushman cover is active; that needs official API access (see README).

PRIVACY: the full number is never stored or logged (only last 4 digits + a salted hash for duplicate detection). The photo is re-encoded (EXIF/GPS removed),
kept in a private folder (not /static), shown only to the owner and staff, and DELETED as soon as staff approve or reject."""
import os, io, re, subprocess, tempfile, difflib
from PIL import Image, ImageOps

_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]
def verhoeff_ok(num):
    c = 0
    for i, ch in enumerate(reversed(num)): c = _D[c][_P[i % 8][int(ch)]]
    return c == 0

def check_number(kind, raw):
    """returns (clean_number or None, message). Format check only."""
    n = re.sub(r"[\s-]", "", raw or "")
    if kind == "aadhaar":
        if not re.fullmatch(r"[2-9]\d{11}", n): return None, "Aadhaar must be 12 digits and cannot start with 0 or 1."
        if not verhoeff_ok(n): return None, "This Aadhaar number fails the checksum, so one digit is wrong. Please re-check."
        return n, ""
    if kind == "ayushman":  # PM-JAY card / beneficiary ID formats vary by state, so only a loose check; 14 digits = ABHA number
        if re.fullmatch(r"\d{14}", n) or re.fullmatch(r"[A-Za-z0-9]{8,20}", n): return n.upper(), ""
        return None, "Enter the Ayushman card / ABHA number printed on the card (8 to 20 letters or digits)."
    return None, "Choose a document type."

def mask(n): return "XXXX XXXX " + n[-4:] if len(n) >= 4 else "XXXX"

def ocr_text(path):
    try:
        im = ImageOps.autocontrast(ImageOps.grayscale(Image.open(path)))
        if im.width < 1400: im = im.resize((im.width * 2, im.height * 2))
        with tempfile.NamedTemporaryFile(suffix=".png") as t:
            im.save(t.name); out = subprocess.run(["tesseract", t.name, "stdout", "-l", "eng", "--psm", "6"], capture_output=True, text=True, timeout=40)
        return out.stdout if out.returncode == 0 else None
    except Exception: return None   # tesseract missing / failed -> staff review only

def number_found(num, text):
    if text is None: return None
    digits = re.sub(r"\D", "", text) if num.isdigit() else ""
    if num.isdigit(): return num in digits
    return num in re.sub(r"[^A-Z0-9]", "", text.upper())

TITLES = {"mr", "mrs", "ms", "dr", "shri", "smt", "kumari", "km", "sri", "late"}
def name_score(name, text):
    if text is None: return None
    want = [w for w in re.findall(r"[a-z]+", name.lower()) if w not in TITLES and len(w) > 1]
    have = re.findall(r"[a-z]+", text.lower())
    if not want: return None
    hit = sum(1 for w in want if any(difflib.SequenceMatcher(None, w, h).ratio() >= 0.8 for h in have))
    return round(100 * hit / len(want))

