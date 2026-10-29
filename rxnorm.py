
import requests

BASE = "https://rxnav.nlm.nih.gov/REST"
REQUEST_TIMEOUT_SECONDS = 8


def normalize(name: str) -> dict:
  
    result = {"input": name, "rxcui": None, "ingredient": None, "status": "needs_confirmation"}
    try:
       
        response = requests.get(
            f"{BASE}/rxcui.json",
            params={"name": name, "search": 2},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        rxcuis = response.json().get("idGroup", {}).get("rxnormId") or []
        if not rxcuis:
            return result
        rxcui = rxcuis[0]

        
        related_response = requests.get(
            f"{BASE}/rxcui/{rxcui}/related.json",
            params={"tty": "IN"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        groups = related_response.json().get("relatedGroup", {}).get("conceptGroup") or []
        properties = [prop for group in groups for prop in group.get("conceptProperties", [])]

        result.update(
            rxcui=rxcui,
            ingredient=properties[0]["name"].lower() if properties else None,
            status="matched" if properties else "needs_confirmation",
        )
    except Exception:
        result["status"] = "lookup_failed"  
    return result