
import requests

URL = "https://api.fda.gov/drug/label.json"
SOURCE_NAME = "US FDA drug label (openFDA)"
REQUEST_TIMEOUT_SECONDS = 8
FIELDS = [
    "indications_and_usage",
    "warnings",
    "contraindications",
    "drug_interactions",
    "adverse_reactions",
]
MAX_CHARS = 600  


def get_label(ingredient):
    if not ingredient:
        return None

    name = str(ingredient).replace('"', "").strip()
    if not name:
        return None

    try:
        response = requests.get(
            URL,
            params={"search": f'openfda.generic_name:"{name}"', "limit": 1},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            return None

        results = response.json().get("results") or []
        if not results:
            return None

        doc = results[0]
        excerpts = {}
        for field in FIELDS:
            value = doc.get(field)
            if value:
                text = " ".join(value) if isinstance(value, list) else str(value)
               
                excerpts[field] = " ".join(text.split())[:MAX_CHARS]

        if not excerpts:
            return None

        return {"source": SOURCE_NAME, "ingredient": name, "excerpts": excerpts}
    except Exception:
        return None