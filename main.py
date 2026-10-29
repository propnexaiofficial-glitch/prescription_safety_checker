from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from checks import find_missing_patient, run_all
from label import get_label
from llm_explain import disclaimer_for, explain_with_meta
from rxnorm import normalize
from schemas import CheckRequest, Source

app = FastAPI(title="Prescription Safety Checker (prototype)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_methods=["*"],
    allow_headers=["*"],
)

RULES_VERSION = "rules-0.2"
FORM_PAGE = Path(__file__).parent / "static" / "index.html"
MAX_QUESTION_CHARS = 300


RED_FLAGS = [
    # English
    "chest pain", "breath", "faint", "bleeding", "rash", "swelling",
    "overdose", "double dose", "pregnan", "breastfeed", "suicid",
    # Hindi / Hinglish
    "seene me dard", "seene mein dard", "saans", "behosh", "khoon",
    "sujan", "zyada", "garbh", "doodh pila", "khud ko",
]


@app.get("/", include_in_schema=False)
def test_form():
    
    return FileResponse(FORM_PAGE)


@app.get("/health")
def health():
    return {"status": "ok"}


def _provided(tracked) -> bool:

    return tracked.source != Source.missing and tracked.value is not None


def triage(age, alerts, question):

    reasons = []

    if any(a["severity"] == "High" for a in alerts):
        reasons.append("a high-severity alert was found (for example, an allergy match)")
    if any(a["rule_id"] == "UNKNOWN_MEDICINE" for a in alerts):
        reasons.append("the medicine name could not be verified with confidence")
    if any(a["rule_id"] in ("OCR_CONFIDENCE", "UNCERTAIN_FIELDS", "SUSPICIOUS_TEXT") for a in alerts):
        reasons.append("some details of the prescription are uncertain")
    if age is not None and (age < 12 or age >= 65):
        reasons.append(
            "a doctor should check the dose at this age, and this tool does not check doses yet"
        )

    question_lower = (question or "").lower()
    if any(word in question_lower for word in RED_FLAGS):
        reasons.append("your question mentions something that should be seen by a doctor")

    return ("see_doctor" if reasons else "routine"), reasons


def _prescription_summary(req: CheckRequest, norm: dict) -> list:

    summary = []
    for med in req.new_prescription:
        info = norm[med.name]
        fields = {
            "name": med.name,
            "strength": med.strength,
            "route": med.route,
            "frequency": med.frequency,
            "duration": med.duration,
            "ingredient": info.get("ingredient"),
            "lookup_status": info["status"],
        }
        summary.append({k: v for k, v in fields.items() if v})
    return summary


def _patient_context(patient) -> dict:

    context = {}
    if _provided(patient.age):
        context["age"] = patient.age.value
    if _provided(patient.weight_kg):
        context["weight_kg"] = patient.weight_kg.value
    if _provided(patient.pregnancy_status):
        context["pregnancy_status"] = patient.pregnancy_status.value
    if _provided(patient.conditions):
        context["conditions"] = [c.name for c in patient.conditions.value]
    if _provided(patient.allergies):
        context["allergies"] = [a.substance for a in patient.allergies.value]
    if _provided(patient.current_medicines):
        context["current_medicines"] = [m.name for m in patient.current_medicines.value]
    return context


def _checks_run(patient) -> list:
    checks = [
        "prescription completeness and reading certainty",
        "medicine name verification (RxNorm)",
        "duplicate ingredients within this prescription",
    ]
    if _provided(patient.allergies):
        checks.append("allergy match")
    if _provided(patient.labs):
        checks.append("lab result dates")
    return checks


@app.post("/check-prescription")
def check_prescription(req: CheckRequest):
    norm = {med.name: normalize(med.name) for med in req.new_prescription}
    alerts, not_checked = run_all(req, norm)

    patient = req.patient
    patient_context = _patient_context(patient)
    prescription = _prescription_summary(req, norm)
    question = (req.user_question or "").strip()[:MAX_QUESTION_CHARS]  # Truncate long text.

    advice_level, triage_reasons = triage(patient_context.get("age"), alerts, question)

   
    first_name = req.new_prescription[0].name
    label_info = (
        get_label(norm[first_name].get("ingredient")) if advice_level == "routine" else None
    )

    result = {
        "status": "Needs professional review",  # Never "safe".
        "advice_level": advice_level,
        "triage_reasons": triage_reasons,
        "alerts": alerts,
        "not_checked": not_checked,
        "checks_run": _checks_run(patient),
        "missing_data": find_missing_patient(req),
        "normalized_medicines": norm,
        "prescription": prescription,
        "patient_context": patient_context,
        "label_info": label_info,
        "user_question": question,
        "language": req.context.language or "hi",
        "metadata": {
            "rules_version": RULES_VERSION,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    
    result["explanation"], result["explanation_source"] = explain_with_meta(result)
    result["disclaimer"] = disclaimer_for(result["language"])
    return result