"""Reproducible, preliminary evaluation for the bundled symptom-routing sample.

IMPORTANT: this evaluates only the small hand-written examples in ml.DATA. It is
not clinical validation and must not be presented as real-world medical accuracy.
Replace/extend the sample with a properly reviewed, de-identified dataset before
making performance claims.
Run: python evaluate_ml.py
"""
import json

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import make_pipeline
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
except ImportError as exc:
    raise SystemExit("scikit-learn is required. Install requirements.txt first.") from exc

from ml import DATA

X = [text for examples in DATA.values() for text in examples]
y = [department for department, examples in DATA.items() for _ in examples]
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)
model = make_pipeline(
    TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True),
    LogisticRegression(C=20, max_iter=2000),
)
model.fit(X_train, y_train)
pred = model.predict(X_test)
labels = sorted(DATA)
report = classification_report(y_test, pred, labels=labels, output_dict=True, zero_division=0)
print("PRELIMINARY OFFLINE EVALUATION — HAND-WRITTEN SAMPLE ONLY")
print(f"Examples: {len(X)} | Train: {len(X_train)} | Test: {len(X_test)} | Seed: 42")
print(f"Accuracy: {accuracy_score(y_test, pred):.3f}")
print("Macro F1:", round(report["macro avg"]["f1-score"], 3))
print("Per-class metrics:")
for label in labels:
    m = report[label]
    print(f"  {label}: precision={m['precision']:.3f}, recall={m['recall']:.3f}, f1={m['f1-score']:.3f}, support={m['support']}")
print("Confusion matrix labels:", labels)
print(confusion_matrix(y_test, pred, labels=labels))
print("\nLIMITATION: this small sample is not an independently collected dataset or clinical validation.")
