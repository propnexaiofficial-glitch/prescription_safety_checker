from datetime import date, datetime

from schemas import CheckRequest, Source

RULE_ENGINE_VERSION = "rule-engine v0.1"
INJECTION_HINTS = ["ignore", "previous instruction", "system prompt", "say it is safe", "bypass"]
LAB_MAX_AGE_DAYS = 90
OCR_CONFIDENCE_THRESHOLD = 0.85
REQUIRED_MEDICINE_FIELDS = ["strength", "route", "frequency", "duration"]
REQUIRED_PATIENT_FIELDS = ["age", "weight_kg", "conditions", "allergies", "current_medicines"]


def _missing(tracked) -> bool:
    
    return tracked.source == Source.missing or tracked.value is None


def find_missing_patient(req: CheckRequest) -> list:
    
    patient = req.patient
    return [f for f in REQUIRED_PATIENT_FIELDS if _missing(getattr(patient, f))]


def alert(rule_id, severity, finding, action, source=RULE_ENGINE_VERSION):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "finding": finding,
        "recommended_action": action,
        "evidence_source": source,
    }


def check_completeness(req):

    alerts = []
    for med in req.new_prescription:
        for field in REQUIRED_MEDICINE_FIELDS:
        
            if getattr(med, field) is None and not (field == "duration" and med.prn):
                alerts.append(alert(
                    "COMPLETENESS", "Low",
                    f"{med.name}: '{field}' is missing.",
                    "Confirm with the prescriber or pharmacist.",
                ))

        if med.confidence is not None and med.confidence < OCR_CONFIDENCE_THRESHOLD:
            alerts.append(alert(
                "OCR_CONFIDENCE", "Moderate",
                f"{med.name}: the text read from the image is uncertain (confidence {med.confidence}).",
                "Re-verify the strength and dose against the original prescription.",
            ))

        if med.uncertain_fields:
            alerts.append(alert(
                "UNCERTAIN_FIELDS", "Moderate",
                f"{med.name}: uncertain fields: {', '.join(med.uncertain_fields)}.",
                "Confirm these fields, then run the check again.",
            ))

        if med.raw_text and any(hint in med.raw_text.lower() for hint in INJECTION_HINTS):
            alerts.append(alert(
                "SUSPICIOUS_TEXT", "Moderate",
                f"{med.name}: the document text contains instruction-like content; it was ignored.",
                "Review the document manually.",
            ))
    return alerts


def check_duplicates(req, norm):

    seen, alerts = {}, []
    for med in req.new_prescription:
        ingredient = norm[med.name].get("ingredient")
        if not ingredient:
            continue
        if ingredient in seen:
            alerts.append(alert(
                "DUPLICATE_INGREDIENT", "Moderate",
                f"Both {seen[ingredient]} and {med.name} contain '{ingredient}'.",
                "Ask a pharmacist to check the total daily exposure.",
            ))
        seen[ingredient] = med.name
    return alerts


def check_allergy(req, norm):

    allergies = req.patient.allergies
    if _missing(allergies):
        return [], ["allergy"]

    alerts = []
    for med in req.new_prescription:
        ingredient = (norm[med.name].get("ingredient") or "").lower()
        for allergy in allergies.value:
            substance = allergy.substance.lower()
            if substance and (
                substance in med.name.lower()
                or (ingredient and (substance in ingredient or ingredient in substance))
            ):
                alerts.append(alert(
                    "ALLERGY_MATCH", "High",
                    f"{med.name} ({ingredient or 'ingredient unknown'}) matches the patient's "
                    f"allergy '{allergy.substance}' (certainty: {allergy.certainty or 'unknown'}).",
                    "Inform the doctor or pharmacist before taking this medicine.",
                ))
    return alerts, []


def check_lab_recency(req):
    
    labs = req.patient.labs
    if _missing(labs):
        return []

    alerts = []
    for lab in labs.value:
        try:
            age_days = (date.today() - datetime.strptime(lab.date, "%Y-%m-%d").date()).days
        except Exception:
            alerts.append(alert(
                "LAB_DATE", "Low",
                f"{lab.name}: the date is missing or invalid, so rules cannot be applied reliably.",
                "Confirm the lab date.",
            ))
            continue

        if age_days > LAB_MAX_AGE_DAYS:
            alerts.append(alert(
                "STALE_LAB", "Low",
                f"{lab.name} is {age_days} days old.",
                "Run the check again with a recent lab value.",
            ))
    return alerts


def run_all(req, norm):
    
    alerts, not_checked = [], []

    alerts += check_completeness(req)
    alerts += check_duplicates(req, norm)

    allergy_alerts, skipped = check_allergy(req, norm)
    alerts += allergy_alerts
    not_checked += [{"check": c, "reason": "allergy details were not provided"} for c in skipped]

    alerts += check_lab_recency(req)

    for med in req.new_prescription:
        if norm[med.name]["status"] != "matched":
            alerts.append(alert(
                "UNKNOWN_MEDICINE", "Moderate",
                f"'{med.name}' could not be confirmed in RxNorm ({norm[med.name]['status']}).",
                "Confirm the name and spelling; checks for this medicine are treated as unsupported.",
            ))

    # These checks stay "not checked" until a licensed drug database is connected.
    for check in ["drug-drug interaction", "dose/frequency limit", "contraindication (condition conflict)"]:
        not_checked.append({
            "check": check,
            "reason": "the drug knowledge database is not connected yet (prototype)",
        })

    patient = req.patient
    if _missing(patient.current_medicines):
        not_checked.append({"check": "interaction with current medicines",
                            "reason": "current medicines were not provided"})
    if _missing(patient.conditions):
        not_checked.append({"check": "condition conflict",
                            "reason": "medical history was not provided"})
    if _missing(patient.age) or _missing(patient.weight_kg):
        not_checked.append({"check": "age/weight-based dose",
                            "reason": "age or weight is missing"})

    return alerts, not_checked