#!/usr/bin/env python3
"""Converte context.json em site_data.json para o template HTML."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


PHONE_RE = re.compile(r"(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\s?)?\d{4}[-\s]?\d{4}")
EMOJI_RE = re.compile(
    "[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e0-\U0001f1ff]+",
    flags=re.UNICODE,
)
MEME_CAPTION_RE = re.compile(
    r"\b(risada|kkk|kkkk|meme|humor|viral|engraçad)\b",
    re.IGNORECASE,
)
CREATOR_BIO_SIGNALS = ("sorrir", "palestr", "humor", "meme", "creator", "influencer", "reels")
TRADITIONAL_BIO_SIGNALS = (
    "criminalista",
    "trabalhista",
    "escritório",
    "escritorio",
    "oab",
    "atuação",
    "atuacao",
)
PRICE_LINE_RE = re.compile(
    r"^[\-\*•]?\s*(.+?)\s*(?:[-–:|]\s*)?(R\$\s?\d+(?:[.,]\d{2})?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
PRICE_INLINE_RE = re.compile(r"(R\$\s?\d+(?:[.,]\d{2})?)", re.IGNORECASE)
CITY_RE = re.compile(
    r"\b(?:em|de|para|atendemos?|salvador|são paulo|rio de janeiro|belo horizonte|recife|fortaleza|curitiba|brasília|porto alegre|manaus|belém|goiânia|florianópolis|londrina)\b",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.IGNORECASE)
WEBSITE_RE = re.compile(
    r"(?:https?://|www\.)[\w.-]+\.[a-z]{2,}(?:/[\w./%-]*)?",
    re.IGNORECASE,
)
INSTAGRAM_CATEGORY_MAP = {
    "lawyer": "Advocacia",
    "law firm": "Advocacia",
    "legal service": "Advocacia",
    "legal services": "Advocacia",
    "attorney": "Advocacia",
    "estate planning lawyer": "Advocacia",
    "notary public": "Advocacia",
    "beauty salon": "Salão de Beleza",
    "hair salon": "Salão de Beleza",
    "restaurant": "Restaurante",
    "medical & health": "Clínica",
    "dentist": "Clínica",
    "personal trainer": "Personal Trainer",
    "pet service": "Pet Shop",
}
CITY_FROM_HASHTAG = {
    "londrina": "Londrina, PR",
    "londrinaeregiao": "Londrina e região",
    "saopaulo": "São Paulo, SP",
    "sãopaulo": "São Paulo, SP",
    "riodejaneiro": "Rio de Janeiro, RJ",
    "curitiba": "Curitiba, PR",
    "salvador": "Salvador, BA",
    "recife": "Recife, PE",
    "fortaleza": "Fortaleza, CE",
    "belohorizonte": "Belo Horizonte, MG",
    "portoalegre": "Porto Alegre, RS",
    "brasilia": "Brasília, DF",
}
ADVOCACIA_KEYWORDS = (
    "advogad",
    "advocacia",
    "jurídic",
    "juridic",
    "direito",
    "oab",
    "imobiliar",
    "consultoria jurídica",
)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def digits_only(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("55"):
        return digits
    if len(digits) in (10, 11):
        return f"55{digits}"
    return digits


def extract_phone(text: str) -> str | None:
    match = PHONE_RE.search(text)
    if not match:
        return None
    return digits_only(match.group(0))


def extract_services(captions: list[str]) -> list[dict[str, str]]:
    services: list[dict[str, str]] = []
    seen: set[str] = set()

    for caption in captions:
        for name, price in PRICE_LINE_RE.findall(caption):
            key = f"{name.strip().lower()}|{price.lower()}"
            if key in seen:
                continue
            seen.add(key)
            services.append({"name": name.strip().title(), "price": price.strip()})

        if not PRICE_LINE_RE.search(caption):
            prices = PRICE_INLINE_RE.findall(caption)
            if prices and len(caption) < 120:
                label = re.sub(r"R\$\s?\d+(?:[.,]\d{2})?", "", caption, flags=re.IGNORECASE)
                label = re.sub(r"[^\w\s\-]", " ", label).strip()
                if label:
                    key = f"{label.lower()}|{prices[0].lower()}"
                    if key not in seen:
                        seen.add(key)
                        services.append({"name": label.title()[:60], "price": prices[0]})

    return services[:12]


def normalize_instagram_category(raw: str) -> str | None:
    if not raw:
        return None
    key = raw.strip().lower()
    if key in INSTAGRAM_CATEGORY_MAP:
        return INSTAGRAM_CATEGORY_MAP[key]
    for mapped, label in INSTAGRAM_CATEGORY_MAP.items():
        if mapped in key or key in mapped:
            return label
    return None


def is_advocacia_profile(profile: dict[str, Any], captions: list[str]) -> bool:
    raw_category = profile.get("category") or ""
    if normalize_instagram_category(raw_category) == "Advocacia":
        return True
    text = " ".join(
        [
            profile.get("full_name", ""),
            profile.get("biography", ""),
            raw_category,
            *captions,
        ]
    ).lower()
    return any(keyword in text for keyword in ADVOCACIA_KEYWORDS)


def guess_category(profile: dict[str, Any], captions: list[str]) -> str:
    mapped = normalize_instagram_category(profile.get("category") or "")
    if mapped:
        return mapped
    if is_advocacia_profile(profile, captions):
        return "Advocacia"
    text = " ".join([profile.get("biography", ""), *captions]).lower()
    rules = [
        (
            "Advocacia",
            ["advogad", "advocacia", "jurídic", "direito", "oab", "processo", "tribunal"],
        ),
        (
            "Salão de Beleza",
            ["manicure", "cabelo", "unha", "salão", "estética", "lash", "sobrancelha"],
        ),
        ("Clínica", ["clínica", "consultório", "médic", "odont", "fisioterap", "psicolog"]),
        ("Restaurante", ["restaurante", "delivery", "cardápio", "pizza", "burger", "comida"]),
        ("Personal Trainer", ["personal", "treino", "academia", "fitness", "musculação"]),
        ("Pet Shop", ["pet", "veterin", "banho e tosa", "cachorro", "gato"]),
    ]
    for label, keywords in rules:
        if any(word in text for word in keywords):
            return label
    return "Negócio Local"


def resolve_category_label(profile: dict[str, Any], captions: list[str], category_base: str) -> str:
    if category_base != "Advocacia":
        mapped = normalize_instagram_category(profile.get("category") or "")
        if mapped:
            return category_base
        return profile.get("category") or category_base

    text = " ".join(
        [
            profile.get("full_name", ""),
            profile.get("biography", ""),
            *captions,
        ]
    ).lower()
    specialty_rules = [
        (
            "Direito Imobiliário",
            ["imobiliar", "usucapi", "itbi", "matrícula", "matricula", "regulariz"],
        ),
        ("Direito Tributário", ["tribut", "crédito tribut", "credito tribut"]),
        ("Direito Criminal", ["criminal", "audiência", "audiencia", "delegacia"]),
        ("Direito Trabalhista", ["trabalh", "clt", "empreg"]),
        ("Direito de Família", ["família", "familia", "divórc", "divorc", "pensão", "pensao"]),
        ("Direito do Consumidor", ["consumidor", "procon"]),
    ]
    for label, keywords in specialty_rules:
        if any(keyword in text for keyword in keywords):
            return label
    return "Advocacia"


def extract_email(text: str) -> str:
    match = EMAIL_RE.search(text)
    return match.group(0).lower() if match else ""


def extract_website(text: str, external_url: str = "") -> str:
    skip_hosts = ("instagram.com", "wa.me", "whatsapp.com", "facebook.com")
    for candidate in [external_url, *WEBSITE_RE.findall(text)]:
        url = candidate.strip()
        if not url:
            continue
        if not url.startswith("http"):
            url = f"https://{url.lstrip('/')}"
        host = url.lower()
        if any(host_part in host for host_part in skip_hosts):
            continue
        return url
    return ""


def collect_post_tags(posts: list[dict[str, Any]]) -> list[str]:
    tags: list[str] = []
    for post in posts:
        for tag in post.get("tags") or []:
            tags.append(tag.lstrip("#").lower())
    return tags


def extract_city(profile: dict[str, Any], posts: list[dict[str, Any]]) -> str:
    bio = profile.get("biography") or ""
    for line in bio.splitlines():
        cleaned = strip_emojis(line).strip()
        if not cleaned:
            continue
        if "📍" in line or CITY_RE.search(cleaned):
            city_line = cleaned.lstrip("📍").strip(" -–|")
            if city_line and len(city_line) <= 80:
                if city_line.lower() not in {
                    "atendimento presencial e online.",
                    "atendimento presencial e online",
                }:
                    return city_line

    for tag in collect_post_tags(posts):
        if tag in CITY_FROM_HASHTAG:
            return CITY_FROM_HASHTAG[tag]

    bio_match = CITY_RE.search(bio)
    if bio_match:
        token = bio_match.group(0)
        if token.lower() not in {"em", "de", "para", "atendemos", "atendemo"}:
            return token.title() if token.islower() else token
    return ""


LEGAL_GALLERY_KEYWORDS = (
    "direito",
    "imóvel",
    "imovel",
    "itbi",
    "tribut",
    "contrato",
    "cartório",
    "cartorio",
    "registro",
    "mcmv",
    "financiamento",
    "casa própria",
    "casa propria",
    "juríd",
    "jurid",
    "advogad",
    "lei ",
)
PERSONAL_GALLERY_KEYWORDS = (
    "te amo",
    "casamento",
    "casados",
    "aniversário",
    "aniversario",
    "família",
    "familia",
    "churrasco",
    "arraial",
    "vidona",
)


def gallery_relevance_score(post: dict[str, Any], *, category: str = "") -> tuple[int, int, str]:
    text = collect_post_text(post).lower()
    score = 0
    if category == "Advocacia":
        score += sum(3 for keyword in LEGAL_GALLERY_KEYWORDS if keyword in text)
        score -= sum(4 for keyword in PERSONAL_GALLERY_KEYWORDS if keyword in text)
        if len(text) >= 80:
            score += 2
    return (score, post.get("likes", 0), str(post.get("date", "")))


def pick_gallery(
    posts: list[dict[str, Any]], limit: int = 12, *, category: str = ""
) -> list[dict[str, str]]:
    images = [
        post for post in posts if post.get("type") == "image" and not post.get("source_video")
    ]
    images.sort(
        key=lambda post: gallery_relevance_score(post, category=category),
        reverse=True,
    )
    gallery = []
    for post in images[:limit]:
        caption = clean_caption(post.get("caption", "")) or "Conteúdo do Instagram"
        gallery.append(
            {
                "src": f"assets/{post['filename']}",
                "alt": caption[:120],
                "caption": caption[:160],
                "url": post.get("url", ""),
                "likes": str(post.get("likes", 0)),
            }
        )
    return gallery


def clean_caption(caption: str) -> str:
    lines = []
    for line in caption.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return " ".join(lines).strip()


def excerpt(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rsplit(" ", 1)[0] + "..."


def collect_post_text(post: dict[str, Any]) -> str:
    parts = [post.get("caption", ""), post.get("transcript", "")]
    return " ".join(part.strip() for part in parts if part).strip()


def strip_emojis(text: str) -> str:
    cleaned = EMOJI_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def is_meme_caption(caption: str) -> bool:
    return bool(MEME_CAPTION_RE.search(caption))


def detect_profile_style(profile: dict[str, Any], posts: list[dict[str, Any]]) -> str:
    bio = (profile.get("biography") or "").lower()
    if any(signal in bio for signal in CREATOR_BIO_SIGNALS):
        return "creator"
    if any(signal in bio for signal in TRADITIONAL_BIO_SIGNALS):
        return "professional"

    humor_posts = 0
    for post in posts:
        text = (post.get("caption") or "").lower()
        tags = " ".join(tag.lower() for tag in post.get("tags", []))
        combined = f"{text} {tags}"
        if any(keyword in combined for keyword in ("humor", "meme", "viral", "risada", "kkk")):
            humor_posts += 1

    total_posts = len(posts) or 1
    if humor_posts / total_posts >= 0.55:
        return "creator"
    return "professional"


def build_creator_topics() -> list[str]:
    return [
        "Defesa de Direitos",
        "Palestras",
        "Consultoria Jurídica",
        "Conteúdo Educativo",
    ]


def build_creator_services(bio: str) -> list[dict[str, str]]:
    lower = bio.lower()
    services: list[dict[str, str]] = []
    if "palestr" in lower:
        services.append({"name": "Palestras", "price": "Sob consulta"})
    if any(word in lower for word in ("defendo", "direito", "advog")):
        services.append({"name": "Defesa de Direitos", "price": "Sob consulta"})
    services.append({"name": "Consultoria Jurídica", "price": "Sob consulta"})
    services.append({"name": "Conteúdo Educativo", "price": "Acompanhe no Instagram"})
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for service in services:
        key = service["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(service)
    return unique[:5]


def build_creator_subheadline(name: str, bio: str) -> str:
    lower = bio.lower()
    if "defendo" in lower and "palestr" in lower:
        return (
            "Advogado que defende direitos, ministra palestras e leva "
            "informação jurídica com leveza."
        )
    cleaned = strip_emojis(bio).replace("\n", " ").strip()
    if cleaned:
        return cleaned
    return f"{name} une advocacia e comunicação para aproximar o direito de todo mundo."


def build_creator_about(name: str, topics: list[str]) -> str:
    areas = ", ".join(topics[:4]) if topics else "advocacia e comunicação"
    return (
        f"{name} combina atuação jurídica com presença digital de alto engajamento. "
        "Pelos reels e posts, traduz temas complexos em linguagem acessível — "
        "com o mesmo compromisso na defesa de quem precisa de orientação legal. "
        f"Atuação em {areas}."
    )


def build_creator_trust_badges() -> list[str]:
    return [
        "Conteúdo que viraliza",
        "Palestras",
        "Defesa de direitos",
        "Resposta rápida",
    ]


def category_label(category: str, profile_style: str) -> str:
    if profile_style == "creator" and category == "Advocacia":
        return "Advogado & Creator"
    return category


def extract_topics(
    posts: list[dict[str, Any]],
    category: str,
    *,
    profile_style: str = "professional",
) -> list[str]:
    if profile_style == "creator" and category == "Advocacia":
        return build_creator_topics()

    topic_rules = {
        "Advocacia": [
            ("Regularização de Imóveis", ["regulariz", "matrícula", "matricula", "averba"]),
            ("Usucapião", ["usucapi"]),
            (
                "Contratos Imobiliários",
                ["locador", "locatário", "locatario", "inquilinato", "aluguel", "contrato"],
            ),
            ("ITBI e Tributos", ["itbi", "tribut", "crédito tribut", "credito tribut"]),
            ("Inventário e Sucessões", ["inventário", "inventario", "herança", "heranca"]),
            (
                "Direito Criminal",
                [
                    "criminal",
                    "réu",
                    "reu",
                    "audiência",
                    "audiencia",
                    "prisão",
                    "prisao",
                    "delegacia",
                ],
            ),
            ("Direito Trabalhista", ["trabalh", "clt", "demiss", "empreg"]),
            (
                "Direito de Família",
                ["família", "familia", "divórc", "divorc", "pensão", "pensao", "guarda"],
            ),
            ("Direito do Consumidor", ["consumidor", "reclama", "procon"]),
            ("Consultoria Jurídica", ["consulta", "orienta", "dúvida", "duvida", "assessor"]),
            ("Atendimento Online", ["online", "videochamada", "remoto"]),
        ],
        "Salão de Beleza": [
            ("Cabelo", ["cabelo", "corte", "color", "mechas", "escova"]),
            ("Unhas", ["unha", "manicure", "pedicure", "nail"]),
            ("Estética", ["estética", "pele", "limpeza", "design"]),
        ],
    }

    combined = " ".join(collect_post_text(post) for post in posts).lower()
    found: list[str] = []
    for label, keywords in topic_rules.get(category, []):
        if any(keyword in combined for keyword in keywords):
            found.append(label)

    if not found and category == "Advocacia":
        found = ["Consultoria Jurídica", "Atendimento Personalizado", "Orientação Legal"]
    return found[:6]


def build_highlights(
    posts: list[dict[str, Any]], limit: int = 6, *, category: str = ""
) -> list[dict[str, str]]:
    videos = [post for post in posts if post.get("type") == "video"]
    with_transcript = [post for post in videos if (post.get("transcript") or "").strip()]
    without_transcript = [post for post in videos if post not in with_transcript]

    with_transcript.sort(
        key=lambda post: gallery_relevance_score(post, category=category),
        reverse=True,
    )
    without_transcript.sort(
        key=lambda post: gallery_relevance_score(post, category=category),
        reverse=True,
    )
    ordered = with_transcript + without_transcript
    if category == "Advocacia":
        image_posts = [
            post
            for post in posts
            if post.get("type") == "image" and len(clean_caption(post.get("caption", ""))) >= 80
        ]
        image_posts.sort(
            key=lambda post: gallery_relevance_score(post, category=category),
            reverse=True,
        )
        ordered = image_posts + ordered

    highlights: list[dict[str, str]] = []
    for post in ordered:
        transcript = (post.get("transcript") or "").strip()
        caption = clean_caption(post.get("caption", ""))
        if not transcript and not caption:
            continue
        if category == "Advocacia" and gallery_relevance_score(post, category=category)[0] < 1:
            continue

        title = caption or excerpt(transcript, 80) or "Conteúdo em destaque"
        body = transcript or caption
        highlights.append(
            {
                "title": title[:100],
                "excerpt": excerpt(body, 260),
                "url": post.get("url", ""),
                "date": str(post.get("date", ""))[:10],
                "likes": str(post.get("likes", 0)),
            }
        )
        if len(highlights) >= limit:
            break
    return highlights


def display_name(full_name: str) -> str:
    for separator in ("|", " I ", " — ", " - "):
        if separator in full_name:
            return full_name.split(separator, 1)[0].strip()
    return full_name.strip()


def build_about_from_content(
    profile: dict[str, Any],
    category: str,
    topics: list[str],
) -> str:
    bio = strip_emojis((profile.get("biography") or "").strip())
    name = display_name(profile.get("full_name") or profile.get("username") or "nosso negócio")

    if bio and topics:
        areas = ", ".join(topics[:5])
        return f"{bio}\n\nAtuação em {areas}."
    if bio:
        return bio
    if topics:
        areas = ", ".join(topics[:5])
        return f"{name} atua em {category.lower()} com foco em {areas}."
    return (
        f"{name} é referência em {category.lower()} e oferece atendimento dedicado. "
        "Entre em contato para saber mais."
    )


def build_trust_badges(
    category: str,
    *,
    has_whatsapp: bool,
    profile_style: str = "professional",
) -> list[str]:
    if profile_style == "creator":
        badges = build_creator_trust_badges()
        if has_whatsapp and "Resposta rápida" not in badges:
            badges.append("Resposta rápida")
        return badges[:4]

    badges_by_category = {
        "Advocacia": ["Atendimento personalizado", "Consultas online", "Sigilo profissional"],
        "Salão de Beleza": [
            "Profissionais qualificados",
            "Agendamento fácil",
            "Ambiente acolhedor",
        ],
        "Clínica": ["Equipe especializada", "Atendimento humanizado", "Horários flexíveis"],
    }
    badges = list(badges_by_category.get(category, ["Atendimento de qualidade", "Foco no cliente"]))
    if has_whatsapp and "Resposta rápida" not in badges:
        badges.append("Resposta rápida")
    return badges[:4]


def extract_services_from_bio(bio: str, category: str) -> list[dict[str, str]]:
    if category != "Advocacia" or not bio or "|" not in bio:
        return []

    skip_terms = ("whatsapp", "contato", "entre em", "agende", "link na bio")
    services: list[dict[str, str]] = []
    seen: set[str] = set()

    for raw_part in re.split(r"[|\n]+", bio):
        part = strip_emojis(raw_part).strip(" -•")
        if not part or len(part) < 4:
            continue
        low = part.lower()
        if any(term in low for term in skip_terms):
            continue
        if low in {"advogado", "advogada"}:
            continue

        if low.startswith("especialista em "):
            name = part
        elif low.startswith("direito "):
            name = part
        elif any(
            token in low
            for token in ("bancár", "bancar", "imobiliár", "tributár", "criminal", "trabalh")
        ):
            name = part if part.lower().startswith("direito ") else f"Direito {part}"
        elif "mcmv" in low or "financiamento" in low:
            name = part if "financiamento" in low else "Financiamento MCMV"
        else:
            continue

        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        services.append({"name": name, "price": "Sob consulta"})

    return services[:8]


def resolve_whatsapp_url(phone: str, external_url: str, message: str) -> str:
    if phone:
        return f"https://wa.me/{phone}?text={quote(message)}"
    if external_url and ("wa.me" in external_url or "whatsapp" in external_url.lower()):
        return external_url
    return ""


def build_services_from_content(
    services: list[dict[str, str]],
    topics: list[str],
    category: str,
    *,
    profile_style: str = "professional",
    bio: str = "",
) -> list[dict[str, str]]:
    if profile_style == "creator" and category == "Advocacia":
        return build_creator_services(bio)
    bio_services = extract_services_from_bio(bio, category)
    if bio_services:
        return bio_services
    if services:
        return services
    if topics:
        return [{"name": topic, "price": "Sob consulta"} for topic in topics]
    if category == "Advocacia":
        return [
            {"name": "Consultoria Jurídica", "price": "Sob consulta"},
            {"name": "Atendimento Personalizado", "price": "Sob consulta"},
        ]
    return services


def maybe_enrich_with_llm(site_data: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return site_data

    try:
        import urllib.request

        prompt = (
            "Você é copywriter para negócios locais. Melhore headline, subheadline e about "
            "mantendo fatos. Responda só JSON com keys: headline, subheadline, about, cta_label.\n\n"
            f"Dados: {json.dumps(site_data, ensure_ascii=False)}"
        )
        payload = {
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
        }
        req = urllib.request.Request(
            f"{os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return site_data
        enriched = json.loads(match.group(0))
        for key in ("headline", "subheadline", "about", "cta_label"):
            if enriched.get(key):
                site_data[key] = enriched[key]
    except Exception as exc:
        print(f"Aviso: LLM indisponível, usando heurísticas ({exc})")
    return site_data


def build_links(
    *,
    whatsapp_url: str,
    cta_label: str,
    instagram_url: str,
    phone: str,
    external_url: str,
    website_url: str = "",
    email: str = "",
    services: list[dict[str, str]],
    site_demo_path: str = "../demo/index.html",
) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []

    if whatsapp_url:
        links.append(
            {
                "label": cta_label,
                "subtitle": "Resposta rápida pelo WhatsApp",
                "url": whatsapp_url,
                "icon": "whatsapp",
                "style": "primary",
            }
        )

    links.append(
        {
            "label": "Ver site completo",
            "subtitle": "Página profissional com serviços e galeria",
            "url": site_demo_path,
            "icon": "site",
            "style": "default",
        }
    )

    if instagram_url:
        links.append(
            {
                "label": "Instagram",
                "subtitle": "Acompanhe novidades e trabalhos",
                "url": instagram_url,
                "icon": "instagram",
                "style": "default",
            }
        )

    if website_url:
        links.append(
            {
                "label": "Site oficial",
                "subtitle": "Visite nossa página na web",
                "url": website_url,
                "icon": "site",
                "style": "default",
            }
        )

    if email:
        links.append(
            {
                "label": "E-mail",
                "subtitle": "Envie sua mensagem",
                "url": f"mailto:{email}",
                "icon": "mail",
                "style": "default",
            }
        )

    if external_url and external_url not in {instagram_url, whatsapp_url, website_url}:
        is_wa = "wa.me" in external_url or "whatsapp" in external_url.lower()
        links.append(
            {
                "label": "WhatsApp" if is_wa else "Link da bio",
                "subtitle": "Acesso direto ao link atual do perfil",
                "url": external_url,
                "icon": "whatsapp" if is_wa else "link",
                "style": "default",
            }
        )

    for service in services[:3]:
        label = service.get("name", "Serviço")
        price = service.get("price", "")
        links.append(
            {
                "label": label,
                "subtitle": price or "Saiba mais",
                "url": whatsapp_url or site_demo_path,
                "icon": "star",
                "style": "default",
            }
        )

    if phone:
        links.append(
            {
                "label": "Ligar agora",
                "subtitle": "Fale direto com o atendimento",
                "url": f"tel:+{phone}",
                "icon": "phone",
                "style": "default",
            }
        )

    return links


def refine_site_copy(
    profile: dict[str, Any],
    *,
    category: str,
    profile_style: str,
    topics: list[str],
    short_name: str,
) -> dict[str, str]:
    bio_raw = (profile.get("biography") or "").strip()
    bio_clean = strip_emojis(bio_raw)

    if profile_style == "creator":
        subheadline = build_creator_subheadline(short_name, bio_raw)
        about = build_creator_about(short_name, topics)
        cta_label = "Chamar no WhatsApp"
        seo_description = (
            f"{short_name} — advocacia com conteúdo que conecta. "
            "Palestras, defesa de direitos e atendimento pelo WhatsApp."
        )[:155]
        site_bio = subheadline
    else:
        subheadline = bio_clean if bio_clean else f"{short_name} — {category}"
        about = build_about_from_content(profile, category, topics)
        cta_label = "Agendar consulta" if category == "Advocacia" else "Agendar pelo WhatsApp"
        seo_description = (bio_clean or about)[:155]
        site_bio = bio_clean or subheadline

    return {
        "subheadline": subheadline,
        "about": about,
        "cta_label": cta_label,
        "seo_description": seo_description,
        "bio": site_bio,
    }


def parse_context(context: dict[str, Any]) -> dict[str, Any]:
    profile = context.get("profile", {})
    posts = context.get("posts", [])
    video_posts = [post for post in posts if post.get("type") == "video"]
    captions = [post.get("caption", "") for post in posts if post.get("caption")]
    transcripts = [post.get("transcript", "") for post in video_posts if post.get("transcript")]

    bio = profile.get("biography", "")
    external_url = (profile.get("external_url") or "").strip()
    all_text = "\n".join([bio, external_url, *captions, *transcripts])
    phone = extract_phone(all_text) or ""
    category = guess_category(profile, captions + transcripts)
    profile_style = detect_profile_style(profile, posts)
    business_name = profile.get("full_name") or profile.get("username") or "Negócio Local"
    username = profile.get("username", "")
    topics = extract_topics(video_posts or posts, category, profile_style=profile_style)
    services = build_services_from_content(
        extract_services(captions),
        topics,
        category,
        profile_style=profile_style,
        bio=bio,
    )
    trust_badges = build_trust_badges(
        category,
        has_whatsapp=bool(phone or (external_url and "wa.me" in external_url)),
        profile_style=profile_style,
    )
    city = extract_city(profile, posts)
    email = extract_email(all_text)
    website_url = extract_website(all_text, external_url)

    short_name = display_name(business_name)
    headline = short_name
    copy = refine_site_copy(
        profile,
        category=category,
        profile_style=profile_style,
        topics=topics,
        short_name=short_name,
    )
    whatsapp_message = (
        "Olá! Vi seu site e gostaria de conversar."
        if profile_style == "creator"
        else "Olá! Vi o site de vocês e gostaria de agendar."
    )
    whatsapp_url = resolve_whatsapp_url(phone, external_url, whatsapp_message)
    instagram_url = context.get("profile_url", f"https://www.instagram.com/{username}/")
    gallery = pick_gallery(posts, category=category)
    highlights = build_highlights(posts, category=category)

    label = resolve_category_label(profile, captions + transcripts, category)
    display_category = category_label(label, profile_style)
    seo_title = f"{short_name} | {display_category}"
    if city and city not in seo_title:
        seo_title = f"{short_name} | {display_category} em {city.split(',')[0]}"

    site_data = {
        "username": username,
        "business_name": business_name,
        "category": display_category,
        "category_base": category,
        "profile_style": profile_style,
        "city": city,
        "phone": phone,
        "email": email,
        "website_url": website_url,
        "whatsapp_url": whatsapp_url,
        "instagram_url": instagram_url,
        "external_url": external_url,
        "display_name": short_name,
        "headline": headline,
        "subheadline": copy["subheadline"],
        "bio": copy["bio"],
        "about": copy["about"],
        "cta_label": copy["cta_label"],
        "services": services,
        "topics": topics,
        "trust_badges": trust_badges,
        "highlights": highlights,
        "transcripts_count": len(transcripts),
        "gallery": gallery,
        "hero_image": gallery[0]["src"] if gallery else "",
        "avatar_image": (
            profile.get("profile_pic", "").replace("media/", "assets/")
            if profile.get("profile_pic")
            else ""
        ),
        "seo_title": seo_title,
        "seo_description": copy["seo_description"],
        "site_demo_path": "../demo/index.html",
        "site_demo_path_publish": "site/index.html",
        "readiness": context.get("readiness", {}),
        "is_demo": True,
    }

    site_data["links"] = build_links(
        whatsapp_url=whatsapp_url,
        cta_label=copy["cta_label"],
        instagram_url=instagram_url,
        phone=phone,
        external_url=external_url,
        website_url=website_url,
        email=email,
        services=services,
        site_demo_path=site_data["site_demo_path"],
    )

    return maybe_enrich_with_llm(site_data)


def main() -> None:
    load_env(PROJECT_ROOT / ".env")

    parser = argparse.ArgumentParser(description="Gerar site_data.json a partir de context.json")
    parser.add_argument("output_dir", help="Pasta com context.json (ex: output/salao_exemplo)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    context_path = output_dir / "context.json"
    if not context_path.exists():
        print(f"Arquivo não encontrado: {context_path}", file=sys.stderr)
        sys.exit(1)

    context = json.loads(context_path.read_text(encoding="utf-8"))
    site_data = parse_context(context)

    site_data_path = output_dir / "site_data.json"
    site_data_path.write_text(
        json.dumps(site_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"site_data salvo: {site_data_path}")
    print(
        f"Serviços: {len(site_data['services'])} | Galeria: {len(site_data['gallery'])} "
        f"| Destaques: {len(site_data['highlights'])} | Transcrições: {site_data['transcripts_count']}"
    )


if __name__ == "__main__":
    main()
