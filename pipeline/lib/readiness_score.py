from __future__ import annotations

import re
from typing import Any


PHONE_RE = re.compile(r"(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}[-\s]?\d{4}")
PRICE_RE = re.compile(r"R\$\s?\d+(?:[.,]\d{2})?", re.IGNORECASE)
WHATSAPP_RE = re.compile(r"whatsapp|wa\.me|agende|agenda|marque|marcação", re.IGNORECASE)


def score_profile(context: dict[str, Any]) -> dict[str, Any]:
    profile = context.get("profile", {})
    posts = context.get("posts", [])
    images = [post for post in posts if post.get("type") == "image"]

    bio = profile.get("biography", "")
    captions = [post.get("caption", "") for post in posts if post.get("caption")]
    all_text = "\n".join([bio, *captions])

    checks = {
        "has_bio": bool(bio.strip()),
        "has_contact_hint": bool(PHONE_RE.search(all_text) or WHATSAPP_RE.search(all_text)),
        "has_images": len(images) >= 5,
        "has_recent_posts": len(posts) >= 8,
        "has_prices_or_services": bool(PRICE_RE.search(all_text) or len(captions) >= 3),
        "has_business_name": bool(profile.get("full_name") or profile.get("username")),
    }

    weights = {
        "has_bio": 15,
        "has_contact_hint": 20,
        "has_images": 25,
        "has_recent_posts": 15,
        "has_prices_or_services": 15,
        "has_business_name": 10,
    }

    score = sum(weights[key] for key, ok in checks.items() if ok)
    grade = "alta" if score >= 70 else "media" if score >= 50 else "baixa"
    recommend = score >= 60

    return {
        "score": score,
        "grade": grade,
        "recommend_demo": recommend,
        "checks": checks,
        "summary": _build_summary(checks, score),
    }


def _build_summary(checks: dict[str, bool], score: int) -> str:
    missing = [name for name, ok in checks.items() if not ok]
    if score >= 70:
        return "Perfil pronto para demo — bom volume de conteúdo e sinais de contato."
    if score >= 50:
        return f"Perfil aceitável para demo, mas faltam: {', '.join(missing)}."
    return f"Perfil fraco para demo automático. Faltam: {', '.join(missing)}."