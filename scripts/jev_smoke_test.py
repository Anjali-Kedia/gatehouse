"""One-off smoke test: confirm real Jev API access works end to end.

Run once to validate the adapter shape (see memory: gatehouse credit-conscious dev).
Not part of the app — the real gateway code will live in backend/.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from typesafe_sdk import TypeSafeClient, Choice

load_dotenv()

client = TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"], model="jev-latest")

state = {
    "user_request": "Can you check whether my order qualifies for a refund?",
    "proposed_action": {"tool": "issue_refund", "arguments": {"order_id": "1042", "amount_cents": 8900}},
}

response = client.system_one(
    state=state,
    questions={
        "match": Choice(
            instructions="Does the proposed action match what the user asked for?",
            criteria={
                "matches": "The action directly fulfills the user's request",
                "contradicts": "The action goes beyond or conflicts with the request",
                "unclear": "Not enough information to tell",
            },
        ),
        "explicit": Choice(
            instructions="Has the user explicitly requested this specific action?",
            criteria={
                "explicit": "User directly asked for this action",
                "information_only": "User asked for information, not for this action to be taken",
                "unclear": "Cannot tell",
            },
        ),
        "specific": Choice(
            instructions="Is the user's request specific enough to act on?",
            criteria={
                "sufficient": "Enough detail to proceed",
                "needs_clarification": "Missing key details",
            },
        ),
    },
)

result = {
    "model": response.model,
    "usage": response.usage.model_dump(),
    "answers": {
        name: {"choice": ans.choice, "confidence": ans.confidence, "probabilities": ans.probabilities}
        for name, ans in response.choices.items()
    },
}

out = Path(__file__).parent.parent / "docs" / "jev_smoke_test_result.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
print(f"\nSaved to {out}")
