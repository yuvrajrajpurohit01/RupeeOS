"""
Growth Agent.
Input: customer's natural-language product request.
Output: recommended product + up to 2 add-ons + reasoning.

MVP note: uses simple keyword/price matching against data/products.json.
Swap `recommend()`'s internals for a real LLM call later — keep the return
shape identical so the orchestrator/API/frontend don't need to change.
"""
import json
import os
from typing import Optional

_PRODUCTS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "products.json")


def _load_products() -> list[dict]:
    try:
        with open(_PRODUCTS_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def recommend(query: str, budget: Optional[float] = None) -> dict:
    products = _load_products()
    query_lower = query.lower()

    def matches(p):
        if p.get("category") == "addon":
            return False
        if budget and p["price"] > budget:
            return False
        tags = [t.lower() for t in p.get("tags", [])]
        name = p.get("name", "").lower()
        product_id = p.get("product_id", "").replace("-", " ").lower()
        return name in query_lower or product_id in query_lower or any(word in query_lower for word in tags) or p["category"].lower() in query_lower

    candidates = [p for p in products if matches(p)] or [
        p for p in products if p.get("category") != "addon" and (not budget or p["price"] <= budget)
    ]
    candidates.sort(key=lambda p: p["price"])

    if not candidates:
        return {
            "intent": query,
            "recommended_products": [],
            "reasoning": "No products matched the request within budget.",
            "upsell": [],
            "estimated_cart_value": 0,
        }

    primary = candidates[0]
    compatible_ids = primary.get("compatible_addon_ids", [])
    addons = [p for p in products if p.get("product_id") in compatible_ids][:2]

    return {
        "intent": query,
        "recommended_products": [primary],
        "reasoning": f"Best match for '{query}'" + (f" within budget ₹{budget}" if budget else ""),
        "upsell": addons,
        "estimated_cart_value": primary["price"] + sum(a["price"] for a in addons),
    }
