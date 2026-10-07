import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Literal

import pandas as pd
from pydantic import BaseModel, Field


POLICY_DOCS = [
    {"id": "POL-CAT-01", "text": "Eligible: economy airfare, lodging, meals subject to per-diem, ground transport, conference/registration fees for documented business purposes."},
    {"id": "POL-CAT-02", "text": "Ineligible: alcohol, minibar, spa, gym, personal entertainment, in-room movies, personal shopping, gifts, traffic fines, penalties, late fees and personal expenses."},
    {"id": "POL-PD-01", "text": "Meals maximum 75 USD per day; excess is deducted."},
    {"id": "POL-PD-02", "text": "Lodging maximum 200 USD per night; excess is deducted."},
    {"id": "POL-PD-03", "text": "Ground transport maximum 50 USD per day; excess is deducted."},
    {"id": "POL-AIR-01", "text": "Only economy airfare is reimbursable. Business/first class is an exception and must go to Manual Review."},
    {"id": "POL-RCT-01", "text": "Any single item above 25 USD requires an attached itemized receipt. Airfare and lodging always require a receipt."},
    {"id": "POL-RCT-02", "text": "Missing required receipt routes the claim to Manual Review."},
    {"id": "POL-APR-01", "text": "Total reimbursable amount <= 500 USD may be auto-approved when fully compliant."},
    {"id": "POL-APR-02", "text": "Total reimbursable amount > 500 and <= 2000 USD is approvable when fully compliant."},
    {"id": "POL-APR-03", "text": "Total reimbursable amount > 2000 USD must go to Manual Review."},
    {"id": "POL-TIME-01", "text": "Claims must be submitted within 30 days of the expense date; late claims go to Manual Review."},
]

CLAIMS = [
    {"claim_id": "CLM-001", "employee": "A. Rivera", "trip_end": "2026-06-12", "submitted": "2026-06-20", "items": [
        {"category": "airfare", "description": "Round-trip economy airfare", "amount": 420, "receipt_attached": True},
        {"category": "lodging", "description": "Hotel, 2 nights @ $180", "amount": 360, "receipt_attached": True, "nights": 2},
        {"category": "meals", "description": "Meals, 3 days @ ~$60/day", "amount": 180, "receipt_attached": True, "days": 3},
        {"category": "conference_fees", "description": "Conference registration", "amount": 150, "receipt_attached": True},
    ]},
    {"claim_id": "CLM-002", "employee": "B. Osei", "trip_end": "2026-06-15", "submitted": "2026-06-25", "items": [
        {"category": "spa", "description": "Hotel spa package", "amount": 300, "receipt_attached": True},
        {"category": "minibar", "description": "In-room minibar", "amount": 80, "receipt_attached": True},
    ]},
    {"claim_id": "CLM-003", "employee": "C. Nakamura", "trip_end": "2026-06-10", "submitted": "2026-06-22", "items": [
        {"category": "airfare", "description": "Round-trip economy airfare", "amount": 300, "receipt_attached": True},
        {"category": "lodging", "description": "Hotel, 2 nights @ $250", "amount": 500, "receipt_attached": True, "nights": 2},
        {"category": "meals", "description": "Meals, 2 days @ $70/day", "amount": 140, "receipt_attached": True, "days": 2},
    ]},
    {"claim_id": "CLM-004", "employee": "D. Fischer", "trip_end": "2026-06-18", "submitted": "2026-06-28", "items": [
        {"category": "airfare", "description": "Business-class international airfare", "amount": 2400, "receipt_attached": True, "class": "business"},
        {"category": "lodging", "description": "Hotel, 3 nights", "amount": 600, "receipt_attached": False, "nights": 3},
    ]},
    {"claim_id": "CLM-005", "employee": "E. Haddad", "trip_end": "2026-06-11", "submitted": "2026-06-24", "items": [
        {"category": "meals", "description": "Client dinner for 4 (business development)", "amount": 220, "receipt_attached": False, "days": 1},
    ]},
]


def retrieve_policy(query: str, top_k: int = 4):
    q = set(re.findall(r"[a-z0-9]+", query.lower()))
    scored = []
    for d in POLICY_DOCS:
        t = set(re.findall(r"[a-z0-9]+", d["text"].lower()))
        score = len(q & t)
        if score:
            scored.append((score, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:top_k]]


def policy_lookup(item):
    return {"tool": "policy_lookup", "policies": [d for d in retrieve_policy(item["category"] + " " + item["description"])]}


def receipt_checker(item):
    required = item["category"] in {"airfare", "lodging"} or float(item["amount"]) > 25
    missing = required and not item.get("receipt_attached", False)
    return {
        "tool": "receipt_checker",
        "required": required,
        "attached": item.get("receipt_attached", False),
        "missing": missing,
        "policy_ref": "POL-RCT-02" if missing else ("POL-RCT-01" if required else None),
    }


def limit_checker(item):
    c = item["category"]
    amount = float(item["amount"])
    if c == "meals":
        limit = 75 * int(item.get("days", 1))
        ref = "POL-PD-01"
    elif c == "lodging":
        limit = 200 * int(item.get("nights", 1))
        ref = "POL-PD-02"
    elif c == "ground_transport":
        limit = 50 * int(item.get("days", 1))
        ref = "POL-PD-03"
    else:
        return {"tool": "limit_checker", "approved": amount, "deducted": 0, "policy_ref": None}
    return {"tool": "limit_checker", "approved": min(amount, limit), "deducted": max(0, amount - limit), "limit": limit, "policy_ref": ref}


def approval_checker(amount):
    if amount <= 500:
        return {"tool": "approval_threshold_checker", "tier": "AUTO_APPROVE", "manual": False, "policy_ref": "POL-APR-01"}
    if amount <= 2000:
        return {"tool": "approval_threshold_checker", "tier": "MANAGER_APPROVAL", "manual": False, "policy_ref": "POL-APR-02"}
    return {"tool": "approval_threshold_checker", "tier": "MANUAL_REVIEW", "manual": True, "policy_ref": "POL-APR-03"}


LLM_ENABLED = bool(os.getenv("OPENAI_API_KEY"))


def agent_plan(claim):
    tools = ["policy_lookup", "receipt_checker", "limit_checker", "approval_threshold_checker"]
    if not LLM_ENABLED:
        return {"mode": "deterministic_fallback", "tools": tools}
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        prompt = (
            "You are an agent planner for a travel reimbursement system. "
            "Return JSON only with a tools list chosen from policy_lookup, receipt_checker, "
            "limit_checker, approval_threshold_checker. Claim=" + json.dumps(claim)
        )
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            messages=[
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
        )
        return {"mode": "llm", "tools": json.loads(response.choices[0].message.content)["tools"]}
    except Exception as exc:  # pragma: no cover - network path only
        return {"mode": "fallback_after_llm_error", "tools": tools, "error": str(exc)}


Decision = Literal["APPROVE", "PARTIAL_APPROVE", "REJECT", "MANUAL_REVIEW"]


class ClaimDecision(BaseModel):
    claim_id: str
    decision: Decision
    approved_amount: float
    deducted_amount: float
    missing_docs: List[str]
    policy_refs: List[str]
    confidence: float = Field(ge=0, le=1)
    explanation: str
    tools_used: List[str]


INELIGIBLE = {"spa", "minibar", "alcohol", "gym", "personal_entertainment", "personal_shopping", "gifts", "traffic_fine", "penalty", "late_fee"}


def evaluate_claim(claim):
    plan = agent_plan(claim)
    tools = list(dict.fromkeys(plan["tools"]))
    approved = 0.0
    deducted = 0.0
    missing = []
    refs = set()
    reasons = []
    manual = False
    ineligible = False
    reimbursable = False
    partial = False

    late = (datetime.fromisoformat(claim["submitted"]) - datetime.fromisoformat(claim["trip_end"])).days > 30
    if late:
        manual = True
        refs.add("POL-TIME-01")
        reasons.append("Claim is outside the 30-day submission window.")

    for item in claim["items"]:
        p = policy_lookup(item)
        refs.update(x["id"] for x in p["policies"])
        c = item["category"]
        amt = float(item["amount"])

        if c in INELIGIBLE:
            ineligible = True
            refs.add("POL-CAT-02")
            deducted += amt
            reasons.append(f"{c} is ineligible under POL-CAT-02.")
            continue

        reimbursable = True
        rc = receipt_checker(item)
        if rc["policy_ref"]:
            refs.add(rc["policy_ref"])
        if rc["missing"]:
            manual = True
            missing.append(f"{c}: required receipt")
            reasons.append(f"Required receipt is missing for {c}.")
        if c == "airfare" and item.get("class", "economy").lower() in {"business", "first"}:
            manual = True
            refs.add("POL-AIR-01")
            reasons.append("Business/first-class airfare is a policy exception.")

        lim = limit_checker(item)
        approved += lim["approved"]
        deducted += lim["deducted"]
        if lim["deducted"] > 0:
            partial = True
            refs.add(lim["policy_ref"])
            reasons.append(f"{c} exceeds its policy cap by ${lim['deducted']:.2f}.")

    if ineligible and not reimbursable:
        decision = "REJECT"
        conf = 0.99
        explanation = "All claimed items are ineligible. " + " ".join(reasons)
    else:
        ap = approval_checker(approved)
        refs.add(ap["policy_ref"])
        manual = manual or ap["manual"]
        if ap["manual"]:
            reasons.append(f"Reimbursable amount ${approved:.2f} exceeds agent approval authority.")
        if manual:
            decision = "MANUAL_REVIEW"
            conf = 0.98
            explanation = "Manual Review required. " + " ".join(reasons)
        elif partial:
            decision = "PARTIAL_APPROVE"
            conf = 0.99
            explanation = f"Partially approve ${approved:.2f}; deduct ${deducted:.2f}. " + " ".join(reasons)
        else:
            decision = "APPROVE"
            conf = 0.99
            explanation = f"Claim is compliant and approvable for ${approved:.2f}."

    final_approved = 0.0 if decision == "MANUAL_REVIEW" else round(approved, 2)
    final_deducted = 0.0 if decision == "MANUAL_REVIEW" else round(deducted, 2)

    return ClaimDecision(
        claim_id=claim["claim_id"],
        decision=decision,
        approved_amount=final_approved,
        deducted_amount=final_deducted,
        missing_docs=missing,
        policy_refs=sorted(refs),
        confidence=conf,
        explanation=explanation,
        tools_used=tools,
    )


def validate_all_claims(results):
    expected = {"CLM-001": "APPROVE", "CLM-002": "REJECT", "CLM-003": "PARTIAL_APPROVE", "CLM-004": "MANUAL_REVIEW", "CLM-005": "MANUAL_REVIEW"}
    df = pd.DataFrame([
        {"claim_id": r.claim_id, "actual": r.decision, "expected": expected[r.claim_id], "pass": r.decision == expected[r.claim_id]}
        for r in results
    ])
    return df


def run_demo():
    results = [evaluate_claim(claim) for claim in CLAIMS]
    df = validate_all_claims(results)
    if not df["pass"].all():
        raise ValueError(f"Policy validation failed: {df.to_dict(orient='records')}")
    return [r.model_dump() for r in results]


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
