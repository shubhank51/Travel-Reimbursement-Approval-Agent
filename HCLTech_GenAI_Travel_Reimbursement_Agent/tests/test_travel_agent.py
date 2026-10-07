import pytest

from travel_reimbursement_agent import evaluate_claim


CLAIMS = [
    {
        "claim_id": "CLM-001",
        "employee": "A. Rivera",
        "trip_end": "2026-06-12",
        "submitted": "2026-06-20",
        "items": [
            {"category": "airfare", "description": "Round-trip economy airfare", "amount": 420, "receipt_attached": True},
            {"category": "lodging", "description": "Hotel, 2 nights @ $180", "amount": 360, "receipt_attached": True, "nights": 2},
            {"category": "meals", "description": "Meals, 3 days @ ~$60/day", "amount": 180, "receipt_attached": True, "days": 3},
            {"category": "conference_fees", "description": "Conference registration", "amount": 150, "receipt_attached": True},
        ],
    },
    {
        "claim_id": "CLM-002",
        "employee": "B. Osei",
        "trip_end": "2026-06-15",
        "submitted": "2026-06-25",
        "items": [
            {"category": "spa", "description": "Hotel spa package", "amount": 300, "receipt_attached": True},
            {"category": "minibar", "description": "In-room minibar", "amount": 80, "receipt_attached": True},
        ],
    },
]


def test_claim_decisions_match_policy_expectations():
    decisions = {claim["claim_id"]: evaluate_claim(claim).decision for claim in CLAIMS}

    assert decisions["CLM-001"] == "APPROVE"
    assert decisions["CLM-002"] == "REJECT"
