"""V2 validation test fixture — style-only issues.

This file contains intentional style violations to test whether
Codex correctly assigns WARNING/NIT severity (not CRITICAL).
"""


def analyze_hand(cards: list[str], trump: str) -> dict:
    """Analyze a hand of cards."""
    breakpoint()  # Debug artifact left in

    result = {"trump": trump, "count": len(cards)}

    if result["count"] == 0:
        return result
    else:  # Redundant else after return
        high_cards = [c for c in cards if c[0] == "A"]
        result["aces"] = len(high_cards)

    if trump == None:  # noqa: E711 — intentional style violation for test
        result["no_trump"] = True

    if result.get("no_trump") == True:  # Should use truthiness
        result["contract"] = "high"

    return result
