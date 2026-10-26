"""Smoke tests for symptom-routing model. Run: python tests_ml.py"""
import ml

passed = failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print("FAIL:", name)

check("sample has multiple departments", len(ml.DATA) >= 4)
check("sample has enough examples for a preliminary smoke test", sum(map(len, ml.DATA.values())) >= 50)
check("rank returns list for non-empty symptom", isinstance(ml.rank("bukhar aur kamzori"), list))
if ml.MODEL is not None:
    check("rank returns bounded probabilities", all(0 <= x["prob"] <= 1 for x in ml.rank("bukhar aur kamzori")))
else:
    print("NOTE: scikit-learn is not installed; model test skipped and keyword fallback remains available.")
print("PASS", passed, "FAIL", failed)
