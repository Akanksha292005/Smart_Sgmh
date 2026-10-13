"""Symptom -> department triage. TF-IDF (character n-grams, so Hindi/Hinglish spelling variants still match) + Logistic Regression.
Trained at start-up on a small hand-written sample, so it is a routing aid for the booking form, NOT a diagnosis tool."""
DATA = {
 "Medicine": ["bukhar aur kamzori", "fever with body pain and weakness", "sugar badh gaya pyas zyada lagti hai", "diabetes check up high sugar", "pet dard ulti dast", "loose motion vomiting stomach pain",
   "blood pressure high chakkar aate hain", "jaundice peeliya aankhen peeli", "thyroid problem weight gain", "typhoid malaria dengue symptoms", "bhookh nahi lagti gas acidity", "skin rash itching allergy"],
 "Orthopaedics": ["ghutne me dard", "knee pain while walking", "kamar dard back pain", "haath ya pair me fracture haddi toot gayi", "shoulder pain cannot lift arm", "gardan me dard neck pain",
   "joint pain arthritis jodon me dard", "sprain ankle swelling", "peeth me dard slip disc", "hip pain difficulty in walking", "accident ke baad pair me sujan", "heel pain foot pain"],
 "Paediatrics": ["bache ko bukhar", "my child has cold and cough", "baby not drinking milk", "bachche ko dast aur ulti", "newborn jaundice", "child vaccination teeka", "baccha raat bhar rota hai",
   "infant fever rash", "bache ki khansi", "toddler not eating weight loss", "child stomach ache", "bachche ko saans lene me dikkat khansi"],
 "Gynaecology": ["pregnancy check up", "garbhavastha jaanch", "periods late ho gaye", "irregular periods pain in lower abdomen", "delivery ke liye admit", "mahavari me bahut dard",
   "white discharge safed pani", "pregnant lady vomiting weakness", "family planning contraception", "breast lump pain women", "infertility baby not conceiving", "menopause hot flashes"],
 "Cardiology": ["seene me dard", "chest pain and sweating", "dil ki dhadkan tez palpitations", "saans phoolna chalne par", "heart blockage angiography", "left arm pain with chest heaviness",
   "high bp and heart problem", "ECG echo check up", "chest tightness while climbing stairs", "dil me ghabrahat", "swelling in feet breathlessness heart failure", "dil ka daura heart attack"],
 "ENT": ["kaan me dard", "ear pain and discharge", "gale me kharash sore throat", "naak band cold sinus", "nose bleeding naak se khoon", "sunai kam deta hai hearing loss", "tonsils swelling throat pain",
   "awaaz baith gayi voice hoarse", "kaan me bajna ringing in ear", "chakkar aur kaan band", "nasal allergy sneezing", "nigalne me dikkat swallowing pain"],
}
INFO = "TF-IDF char n-grams + Logistic Regression, trained on a small sample"
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    X = [s for v in DATA.values() for s in v]; y = [d for d, v in DATA.items() for _ in v]
    MODEL = make_pipeline(TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True), LogisticRegression(C=20, max_iter=2000)).fit(X, y)
except Exception:  # scikit-learn missing: the app falls back to its keyword matcher
    MODEL = None

def rank(text, k=3):
    """Top-k departments with probabilities, or [] if there is no model / no text."""
    if not MODEL or len((text or "").strip()) < 3: return []
    p = MODEL.predict_proba([text.lower()])[0]
    return [dict(dept=str(c), prob=round(float(v), 3)) for c, v in sorted(zip(MODEL.classes_, p), key=lambda t: -t[1])[:k]]
