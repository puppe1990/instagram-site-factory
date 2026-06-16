#!/usr/bin/env python3
"""Gera demo HTML (site + linktree + pacote publish) a partir de site_data.json."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from copy import deepcopy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_TEMPLATE_DIR = PROJECT_ROOT / "templates" / "local-demo"
LINKTREE_TEMPLATE_DIR = PROJECT_ROOT / "templates" / "linktree-demo"
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.lib.favicon import write_favicon  # noqa: E402
from pipeline.lib.link_icons import LINK_ICONS  # noqa: E402

ICONS = LINK_ICONS
OAB_RE = re.compile(r"OAB[/\s]*[A-Z]{2}\s*[\d.]+", re.IGNORECASE)
SITE_TEMPLATE_FILES = ("script.js", "styles.css", "editorial.css")


def copy_site_template_files(target_dir: Path, *, include_netlify: bool = False) -> None:
    for filename in SITE_TEMPLATE_FILES:
        shutil.copy2(SITE_TEMPLATE_DIR / filename, target_dir / filename)
    if include_netlify:
        shutil.copy2(SITE_TEMPLATE_DIR / "netlify.toml", target_dir / "netlify.toml")


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    return re.sub(r"[-\s]+", "-", value).strip("-") or "negocio"


def netlify_site_slug(username: str) -> str:
    """Slug padrão dos sites Netlify gerados a partir do @usuario."""
    cleaned = username.lower().strip().lstrip("@")
    cleaned = re.sub(r"[._]+", "-", cleaned)
    return re.sub(r"-+", "-", cleaned).strip("-") or "negocio"


def default_publish_url(site_data: dict) -> str:
    explicit = (site_data.get("publish_url") or "").strip().rstrip("/")
    if explicit:
        return explicit
    username = site_data.get("username", "")
    if username:
        return f"https://{netlify_site_slug(username)}.netlify.app"
    return ""


def absolute_asset_url(publish_base: str, relative_path: str) -> str:
    rel = relative_path.lstrip("/")
    if not publish_base:
        return rel
    return f"{publish_base.rstrip('/')}/{rel}"


def prepare_og_image(assets_dir: Path, username: str, source_avatar: Path) -> str:
    """Cria arquivo dedicado ao preview social (evita cache de avatar.jpg antigo)."""
    og_name = f"og-{netlify_site_slug(username)}.jpg"
    og_path = assets_dir / og_name
    shutil.copy2(source_avatar, og_path)
    return f"assets/{og_name}"


def render_services(services: list[dict[str, str]], profile_style: str = "professional") -> str:
    if not services:
        return """
        <article class="service-card">
          <p>Entre em contato para consultar serviços e valores atualizados.</p>
        </article>
        """
    rows = []
    for index, item in enumerate(services, start=1):
        rows.append(
            f"""
            <article class="service-card">
              <span class="service-card__index">0{index}</span>
              <h3>{html.escape(item.get("name", "Serviço"))}</h3>
              <p>{html.escape(item.get("price", "Sob consulta"))}</p>
            </article>
            """
        )
    return "\n".join(rows)


def render_trust_badges(badges: list[str]) -> str:
    if not badges:
        return ""
    return "\n".join(f'<span class="pill">{html.escape(badge)}</span>' for badge in badges)


def split_display_name(display_name: str) -> tuple[str, str]:
    parts = display_name.strip().split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return display_name.strip(), ""


def render_nav_brand(display_name: str) -> str:
    first, rest = split_display_name(display_name)
    if rest:
        return f"<strong>{html.escape(first)}</strong> {html.escape(rest)}"
    return html.escape(display_name)


def primary_cta(site_data: dict) -> tuple[str, str]:
    whatsapp_url = (site_data.get("whatsapp_url") or "").strip()
    if whatsapp_url and whatsapp_url not in {"#", "#contato"}:
        return whatsapp_url, site_data.get("cta_label", "Falar no WhatsApp")
    instagram_url = site_data.get("instagram_url", "#contato")
    return instagram_url, "Falar no Instagram"


def expand_services(services: list[dict[str, str]]) -> list[dict[str, str]]:
    expanded: list[dict[str, str]] = []
    for item in services:
        name = (item.get("name") or "Serviço").strip()
        price = item.get("price", "Sob consulta")
        if "," in name:
            for part in name.split(","):
                part = part.strip()
                if part:
                    expanded.append({"name": part, "price": price})
        else:
            expanded.append({"name": name, "price": price})
    if not expanded:
        expanded.append({"name": "Atendimento jurídico", "price": "Sob consulta"})
    return expanded[:6]


def area_description(name: str) -> str:
    name_l = name.lower()
    if "tribut" in name_l:
        return "Planejamento, contencioso e orientação estratégica com foco em segurança jurídica."
    if "integridade" in name_l or "compliance" in name_l:
        return "Programas de compliance, governança e conduta alinhados à realidade do negócio."
    if "regulat" in name_l:
        return "Navegação em normas e exigências setoriais com visão prática para decisões seguras."
    if "penal" in name_l or "criminal" in name_l:
        return "Defesa técnica, acompanhamento processual e orientação em cada etapa."
    if "trabalh" in name_l:
        return "Consultoria preventiva e contenciosa para empresas e profissionais."
    if "civil" in name_l:
        return "Soluções jurídicas com foco em prevenção de litígios e resolução de conflitos."
    if "imobili" in name_l or "itbi" in name_l:
        return "Assessoria em operações, tributos e segurança jurídica imobiliária."
    return "Atendimento personalizado com rigor técnico e linguagem acessível."


def render_hero_caption(site_data: dict) -> str:
    display_name = site_data.get("display_name") or site_data.get("business_name", "")
    category = site_data.get("category", "")
    if category:
        return f"{display_name} · {category}"
    return display_name


def render_nav_content(site_data: dict) -> str:
    if site_data.get("gallery") or site_data.get("highlights"):
        return '<a href="#conteudo">Conteúdo</a>'
    return ""


def hero_primary_cta_label(site_data: dict, default_label: str) -> str:
    whatsapp_url = (site_data.get("whatsapp_url") or "").strip()
    if whatsapp_url and whatsapp_url not in {"#", "#contato"}:
        return default_label
    return "Acompanhar no Instagram"


def render_hero_eyebrow(site_data: dict) -> str:
    bio = f"{site_data.get('bio', '')} {site_data.get('subheadline', '')}"
    oab_match = OAB_RE.search(bio)
    category = site_data.get("category") or site_data.get("category_base", "")
    if oab_match:
        return f"{oab_match.group(0)} · {category or 'Advogado'}"
    city = site_data.get("city", "")
    if city and category:
        return f"{category} · {city}"
    return category or site_data.get("category_base", "Profissional")


def render_hero_title_html(site_data: dict) -> str:
    highlights = site_data.get("highlights") or []
    if highlights:
        hook = (highlights[0].get("title") or "").strip()
        if len(hook) > 24:
            words = hook.split()
            line1: list[str] = []
            length = 0
            for word in words:
                if length + len(word) > 52 and line1:
                    break
                line1.append(word)
                length += len(word) + 1
            rest = " ".join(words[len(line1) :])
            first = " ".join(line1)
            if rest:
                return f"{html.escape(first)}\n<span>{html.escape(rest[:72])}</span>"
            return html.escape(first)

    display_name = site_data.get("display_name") or site_data.get("business_name", "")
    category = site_data.get("category", "")
    if category and category.lower() not in display_name.lower():
        return f"{html.escape(display_name)}\n<span>{html.escape(category)}</span>"
    return html.escape(display_name)


def render_hero_stats_html(services: list[dict[str, str]]) -> str:
    items = expand_services(services)[:3]
    rows = []
    for index, item in enumerate(items, start=1):
        rows.append(
            f"""
            <div class="hero-stat">
              <strong>{index:02d}</strong>
              <span>{html.escape(item.get('name', 'Serviço'))}</span>
            </div>
            """
        )
    return f'<div class="hero__stats">{"".join(rows)}</div>'


def render_secondary_cta_html(has_content: bool, instagram_url: str) -> str:
    if has_content:
        return '<a class="btn btn--ghost" href="#conteudo">Ver conteúdo em destaque</a>'
    return (
        f'<a class="btn btn--ghost" href="{html.escape(instagram_url)}" '
        f'target="_blank" rel="noopener">Instagram</a>'
    )


def render_manifesto_section(site_data: dict) -> str:
    highlights = site_data.get("highlights") or []
    quote = ""
    body = (site_data.get("subheadline") or site_data.get("bio") or "").strip()
    if highlights:
        highlight = highlights[0]
        quote = (highlight.get("title") or "").strip()
        body = (highlight.get("excerpt") or body).strip()
    if not quote:
        quote = body[:140]
        body = (site_data.get("about") or body)[len(quote) :].strip() or body
    if not quote:
        return ""

    return f"""
    <section class="manifesto" aria-labelledby="manifesto-title">
      <div class="manifesto__inner reveal">
        <p class="manifesto__label" id="manifesto-title">Posicionamento</p>
        <blockquote>{html.escape(quote)}</blockquote>
        <p>{html.escape(body[:320])}</p>
      </div>
    </section>
    """


def render_areas_section(services: list[dict[str, str]]) -> str:
    items = expand_services(services)[:3]
    rows = []
    for index, item in enumerate(items, start=1):
        rows.append(
            f"""
            <article class="area-card">
              <span class="area-card__num">{index:02d}</span>
              <h3>{html.escape(item.get('name', 'Serviço'))}</h3>
              <p>{html.escape(area_description(item.get('name', '')))}</p>
            </article>
            """
        )
    return f'<div class="areas-grid reveal">{"".join(rows)}</div>'


def render_feature_content_section(site_data: dict) -> str:
    gallery = site_data.get("gallery") or []
    highlights = site_data.get("highlights") or []
    item = gallery[0] if gallery else None
    highlight = highlights[0] if highlights else {}

    if item:
        title = (highlight.get("title") or item.get("caption") or "Conteúdo em destaque").strip()
        excerpt = (highlight.get("excerpt") or item.get("caption") or "").strip()
        url = item.get("url") or site_data.get("instagram_url", "#")
        image = item.get("src", "")
        date = highlight.get("date", "")
        meta = f"Instagram · {date}" if date else "Instagram"
    elif highlight:
        title = (highlight.get("title") or "Conteúdo em destaque").strip()
        excerpt = (highlight.get("excerpt") or "").strip()
        url = highlight.get("url") or site_data.get("instagram_url", "#")
        image = site_data.get("hero_image") or site_data.get("avatar_image") or ""
        meta = f"Instagram · {highlight.get('date', '')}".strip(" ·")
    else:
        return ""

    image_html = (
        f'<img src="{html.escape(image)}" alt="{html.escape(title[:120])}" loading="lazy" />'
        if image
        else ""
    )
    return f"""
      <section class="section section--alt" id="conteudo">
        <div class="container">
          <div class="section-head reveal">
            <p class="section-head__eyebrow">Conteúdo</p>
            <h2 class="section-head__title">Publicação em destaque</h2>
            <p class="section-head__lead">Trecho do conteúdo que resume a atuação profissional.</p>
          </div>
          <article class="feature-card reveal">
            <div class="feature-card__media">{image_html}</div>
            <div class="feature-card__body">
              <p class="feature-card__meta">{html.escape(meta)}</p>
              <h3>{html.escape(title[:120])}</h3>
              <p>{html.escape(excerpt[:280])}</p>
              <a href="{html.escape(url)}" target="_blank" rel="noopener">Ver no Instagram →</a>
            </div>
          </article>
        </div>
      </section>
    """


def render_about_panel_html(site_data: dict) -> str:
    about = (site_data.get("about") or site_data.get("bio") or "").strip()
    credentials: list[str] = []
    bio = f"{site_data.get('bio', '')} {site_data.get('subheadline', '')}"
    oab_match = OAB_RE.search(bio)
    if oab_match:
        credentials.append(oab_match.group(0))
    credentials.extend(site_data.get("topics") or [])
    for badge in site_data.get("trust_badges") or []:
        if badge not in credentials:
            credentials.append(badge)
    credentials = credentials[:6]

    chips = "".join(f"<span>{html.escape(item)}</span>" for item in credentials)
    instagram_url = site_data.get("instagram_url", "#")
    username = site_data.get("username", "")
    return f"""
      <div class="about-panel reveal">
        <p>{html.escape(about)}</p>
        <div class="about-credentials">{chips}</div>
        <a class="about-link" href="{html.escape(instagram_url)}" target="_blank" rel="noopener">
          Acompanhe @{html.escape(username)} no Instagram →
        </a>
      </div>
    """


def render_footer_extra(site_data: dict) -> str:
    bio = f"{site_data.get('bio', '')} {site_data.get('subheadline', '')}"
    oab_match = OAB_RE.search(bio)
    return f" · {html.escape(oab_match.group(0))}" if oab_match else ""


def render_wa_float_html(whatsapp_url: str) -> str:
    if not whatsapp_url or whatsapp_url in {"#", "#contato"}:
        return ""
    return f"""
    <a
      class="wa-float"
      href="{html.escape(whatsapp_url)}"
      target="_blank"
      rel="noopener"
      aria-label="WhatsApp"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.435 9.884-9.881 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"
        />
      </svg>
    </a>
    """


def hero_title(display_name: str, profile_style: str) -> str:
    name = html.escape(display_name.strip())
    if profile_style != "creator" or " " not in display_name.strip():
        return name
    first, last = display_name.strip().rsplit(" ", 1)
    return f"{html.escape(first)} <em>{html.escape(last)}</em>"


def services_labels(category: str, profile_style: str = "professional") -> tuple[str, str]:
    if profile_style == "creator":
        return "Atuação", "O que faço"
    if category.lower() in {"advocacia", "clínica"}:
        return "Áreas", "Áreas de atuação"
    return "Serviços", "O que oferecemos"


def services_intro(profile_style: str) -> str:
    if profile_style == "creator":
        return "Advocacia séria, comunicação leve — do conteúdo ao atendimento."
    return "Atendimento dedicado com clareza, estratégia e comunicação direta."


def contact_intro(profile_style: str, *, has_whatsapp: bool = True) -> str:
    if profile_style == "creator":
        if has_whatsapp:
            return "Palestras, orientação jurídica ou parcerias — chame no WhatsApp."
        return "Palestras, orientação jurídica ou parcerias — chame no Instagram."
    if has_whatsapp:
        return "Tire suas dúvidas, entenda suas opções e agende um atendimento pelo WhatsApp."
    return "Tire suas dúvidas e agende uma conversa pelo Instagram."


THEMES = {
    "creator": {
        "fonts": (
            "https://fonts.googleapis.com/css2?"
            "family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800"
            "&family=Manrope:wght@400;500;600;700;800&display=swap"
        ),
    },
    "professional": {
        "fonts": (
            "https://fonts.googleapis.com/css2?"
            "family=Instrument+Serif:ital@0;1"
            "&family=Sora:wght@400;500;600;700&display=swap"
        ),
    },
}


def favicon_colors(site_data: dict, *, variant: str) -> tuple[str | None, str | None]:
    palette = site_data.get("theme_palette") or {}
    bg = palette.get("favicon_bg") or palette.get("hero-bg")
    fg = palette.get("favicon_fg") or palette.get("accent")
    if variant == "linktree" and not palette.get("favicon_bg"):
        bg = palette.get("hero-bg") or bg
    return bg, fg


def render_theme_override(site_data: dict) -> str:
    palette = site_data.get("theme_palette")
    if not palette:
        return ""

    profile_style = html.escape(site_data.get("profile_style", "professional"))
    vars_lines = []
    for key, value in palette.items():
        if key.startswith("favicon_"):
            continue
        css_key = key.replace("_", "-")
        vars_lines.append(f"  --{css_key}: {value};")

    vars_block = "\n".join(vars_lines)
    return f"""<style>
html[data-style="{profile_style}"],
[data-style="{profile_style}"] {{
{vars_block}
}}
[data-style="{profile_style}"] .demo-ribbon {{
  background: linear-gradient(90deg, var(--ink) 0%, var(--hero-bg) 100%);
  color: var(--hero-text);
}}
[data-style="{profile_style}"] .btn--primary {{
  background: var(--btn-bg, var(--hero-bg));
  color: var(--btn-text, var(--hero-text));
}}
[data-style="{profile_style}"] .btn--primary:hover {{
  background: var(--ink);
}}
[data-style="{profile_style}"] .hero__title em {{
  color: var(--accent);
  font-style: normal;
}}
[data-style="{profile_style}"] .hero__eyebrow,
[data-style="{profile_style}"] .section-head__eyebrow {{
  color: var(--accent);
  letter-spacing: 0.16em;
}}
[data-style="{profile_style}"] .link-card--primary {{
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--accent) 24%, var(--bg-elevated, var(--bg-soft))),
    var(--bg-elevated, var(--bg-soft))
  );
  border-color: color-mix(in srgb, var(--accent) 50%, var(--line));
  box-shadow: 0 14px 36px var(--accent-glow);
}}
[data-style="{profile_style}"] .profile__category {{
  color: var(--accent);
}}
</style>"""


def render_highlights(highlights: list[dict[str, str]]) -> str:
    if not highlights:
        return ""

    rows = []
    for item in highlights[:6]:
        link = item.get("url", "")
        link_html = (
            f'<a href="{html.escape(link)}" target="_blank" rel="noopener">Ver no Instagram →</a>'
            if link
            else ""
        )
        rows.append(
            f"""
            <article class="highlight-card">
              <h3>{html.escape(item.get("title", "Destaque"))}</h3>
              <p>{html.escape(item.get("excerpt", ""))}</p>
              <div class="highlight-card__meta">
                <span>{html.escape(item.get("date", ""))}</span>
                <span>{html.escape(item.get("likes", "0"))} curtidas</span>
                {link_html}
              </div>
            </article>
            """
        )
    return "\n".join(rows)


def _render_reel_card(item: dict[str, str]) -> str:
    caption = html.escape(item.get("caption", "")[:72])
    image_html = f'<img src="{html.escape(item["src"])}" alt="{html.escape(item.get("alt", ""))}" loading="lazy" />'
    play = (
        '<span class="reel-card__play" aria-hidden="true">'
        '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></span>'
    )
    body = (
        f'{image_html}{play}<div class="reel-card__shade"></div>'
        f'<p class="reel-card__meta">{caption}</p>'
    )
    if item.get("url"):
        return (
            f'<a class="reel-card" href="{html.escape(item["url"])}" '
            f'target="_blank" rel="noopener">{body}</a>'
        )
    return f'<article class="reel-card">{body}</article>'


def render_gallery(gallery: list[dict[str, str]]) -> tuple[str, str]:
    if not gallery:
        return "", ""

    strip_items = [_render_reel_card(item) for item in gallery[:10]]
    grid_items = [_render_reel_card(item) for item in gallery[:12]]
    return "\n".join(strip_items), "\n".join(grid_items)


def render_gallery_section(gallery: list[dict[str, str]], profile_style: str) -> str:
    strip, grid = render_gallery(gallery)
    if not strip:
        return ""

    eyebrow = "Reels" if profile_style == "creator" else "Galeria"
    title = "Conteúdos em destaque" if profile_style == "creator" else "Trabalhos recentes"
    intro = (
        "Os posts que mais engajam — direto do Instagram."
        if profile_style == "creator"
        else "Uma seleção dos conteúdos publicados no perfil."
    )
    return f"""
      <section class="section section--alt" id="reels">
        <div class="container">
          <div class="section-head reveal">
            <p class="section-head__eyebrow">{eyebrow}</p>
            <h2 class="section-head__title">{title}</h2>
            <p class="section-head__lead">{intro}</p>
          </div>
          <div class="reel-strip reveal">{strip}</div>
          <div class="reel-grid reveal">{grid}</div>
        </div>
      </section>
    """


def render_highlights_section(highlights: list[dict[str, str]], profile_style: str) -> str:
    cards = render_highlights(highlights)
    if not cards:
        return ""

    if profile_style != "creator":
        return ""

    return f"""
      <section class="section" id="destaques">
        <div class="container">
          <div class="section-head reveal">
            <p class="section-head__eyebrow">Destaques</p>
            <h2 class="section-head__title">No ar recentemente</h2>
            <p class="section-head__lead">Trechos e legendas dos conteúdos com mais repercussão.</p>
          </div>
          <div class="highlight-grid reveal">{cards}</div>
        </div>
      </section>
    """


def render_links(links: list[dict[str, str]]) -> str:
    if not links:
        return '<p class="links-empty">Links em atualização.</p>'

    rows = []
    for item in links:
        style = item.get("style", "default")
        icon = ICONS.get(item.get("icon", "link"), ICONS["link"])
        subtitle = item.get("subtitle", "")
        subtitle_html = (
            f'<span class="link-card__sub">{html.escape(subtitle)}</span>' if subtitle else ""
        )
        opens_new_tab = item["url"].startswith("http") or item.get("label") == "Ver site completo"
        target = ' target="_blank" rel="noopener"' if opens_new_tab else ""
        primary_class = " link-card--primary" if style == "primary" else ""
        rows.append(
            f"""
            <a class="link-card{primary_class}" href="{html.escape(item["url"])}"{target}>
              <span class="link-card__icon">{icon}</span>
              <span>
                <span class="link-card__label">{html.escape(item.get("label", "Link"))}</span>
                {subtitle_html}
              </span>
            </a>
            """
        )
    return "\n".join(rows)


def render_schema(site_data: dict) -> str:
    image = (
        site_data.get("og_image") or site_data.get("avatar_image") or site_data.get("hero_image")
    )
    payload = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": site_data.get("business_name"),
        "description": site_data.get("seo_description"),
        "url": site_data.get("publish_url") or site_data.get("instagram_url"),
        "image": image,
        "telephone": f"+{site_data['phone']}" if site_data.get("phone") else None,
    }
    payload = {key: value for key, value in payload.items() if value}
    return json.dumps(payload, ensure_ascii=False)


def apply_site_template(template: str, site_data: dict) -> str:
    profile_style = site_data.get("profile_style", "professional")
    category_base = site_data.get("category_base", site_data.get("category", ""))
    theme = THEMES.get(profile_style, THEMES["professional"])
    services_eyebrow, services_title = services_labels(category_base, profile_style)
    display_name = site_data.get("display_name") or site_data.get(
        "headline", site_data.get("business_name", "")
    )
    avatar = site_data.get("avatar_image") or "assets/profile_pic.jpg"
    og_image = site_data.get("og_image") or avatar
    og_url = site_data.get("og_url") or site_data.get("publish_url") or ""
    services = site_data.get("services", [])
    gallery = site_data.get("gallery", [])
    highlights = site_data.get("highlights", [])
    whatsapp_url = (site_data.get("whatsapp_url") or "").strip()
    has_whatsapp = bool(whatsapp_url and whatsapp_url not in {"#", "#contato"})
    primary_url, primary_label = primary_cta(site_data)
    has_content = bool(gallery or highlights)
    feature_section = render_feature_content_section(site_data)

    replacements = {
        "{{PROFILE_STYLE}}": html.escape(profile_style),
        "{{BUSINESS_NAME}}": html.escape(site_data.get("business_name", "")),
        "{{DISPLAY_NAME}}": html.escape(display_name),
        "{{HERO_TITLE}}": hero_title(display_name, profile_style),
        "{{HERO_TITLE_HTML}}": render_hero_title_html(site_data),
        "{{HERO_EYEBROW}}": html.escape(render_hero_eyebrow(site_data)),
        "{{HERO_CAPTION}}": html.escape(render_hero_caption(site_data)),
        "{{HERO_STATS_HTML}}": render_hero_stats_html(services),
        "{{NAV_BRAND}}": render_nav_brand(display_name),
        "{{NAV_CONTENT}}": render_nav_content(site_data),
        "{{PRIMARY_CTA_URL}}": html.escape(primary_url),
        "{{PRIMARY_CTA_LABEL}}": html.escape(primary_label),
        "{{HERO_PRIMARY_CTA_LABEL}}": html.escape(
            hero_primary_cta_label(site_data, primary_label)
        ),
        "{{SECONDARY_CTA_HTML}}": render_secondary_cta_html(
            has_content, site_data.get("instagram_url", "#")
        ),
        "{{CONTACT_CTA_URL}}": html.escape(primary_url),
        "{{CONTACT_CTA_LABEL}}": html.escape(primary_label),
        "{{MANIFESTO_SECTION}}": render_manifesto_section(site_data),
        "{{AREAS_SECTION}}": render_areas_section(services),
        "{{FEATURE_CONTENT_SECTION}}": feature_section,
        "{{ABOUT_PANEL_HTML}}": render_about_panel_html(site_data),
        "{{FOOTER_EXTRA}}": render_footer_extra(site_data),
        "{{WA_FLOAT_HTML}}": render_wa_float_html(whatsapp_url),
        "{{CATEGORY}}": html.escape(site_data.get("category", "")),
        "{{HEADLINE}}": html.escape(site_data.get("headline", "")),
        "{{SUBHEADLINE}}": html.escape(site_data.get("subheadline", "")),
        "{{BIO}}": html.escape(site_data.get("bio", site_data.get("subheadline", ""))),
        "{{ABOUT}}": html.escape(site_data.get("about", "")),
        "{{CTA_LABEL}}": html.escape(site_data.get("cta_label", "Fale conosco")),
        "{{WHATSAPP_URL}}": html.escape(site_data.get("whatsapp_url", "#contato")),
        "{{AVATAR_IMAGE}}": html.escape(avatar),
        "{{OG_IMAGE}}": html.escape(og_image),
        "{{OG_URL}}": html.escape(og_url),
        "{{SEO_TITLE}}": html.escape(
            site_data.get("seo_title", site_data.get("business_name", "Site"))
        ),
        "{{SEO_DESCRIPTION}}": html.escape(site_data.get("seo_description", "")),
        "{{SERVICES_EYEBROW}}": html.escape(services_eyebrow),
        "{{SERVICES_TITLE}}": html.escape(services_title),
        "{{SERVICES_INTRO}}": html.escape(services_intro(profile_style)),
        "{{CONTACT_INTRO}}": html.escape(
            contact_intro(profile_style, has_whatsapp=has_whatsapp)
        ),
        "{{SERVICES_HTML}}": render_services(services, profile_style),
        "{{TRUST_HTML}}": render_trust_badges(site_data.get("trust_badges", [])),
        "{{GALLERY_SECTION}}": render_gallery_section(gallery, profile_style),
        "{{HIGHLIGHTS_SECTION}}": render_highlights_section(highlights, profile_style),
        "{{NAV_REELS}}": '<a href="#reels">Reels</a>' if gallery else "",
        "{{FONT_LINK}}": theme["fonts"],
        "{{THEME_OVERRIDE}}": render_theme_override(site_data),
        "{{SCHEMA_JSON}}": render_schema(site_data),
        "{{INSTAGRAM_URL}}": html.escape(site_data.get("instagram_url", "#")),
        "{{CITY}}": html.escape(site_data.get("city", "")),
        "{{USERNAME}}": html.escape(site_data.get("username", "")),
    }
    result = template
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result


def apply_linktree_template(template: str, site_data: dict, *, site_demo_path: str) -> str:
    links = []
    for item in site_data.get("links", []):
        link = dict(item)
        if link.get("label") == "Ver site completo":
            link["url"] = site_demo_path
        links.append(link)

    profile_style = site_data.get("profile_style", "professional")
    theme = THEMES.get(profile_style, THEMES["professional"])
    display_name = site_data.get("display_name") or site_data.get(
        "headline", site_data.get("business_name", "")
    )
    avatar = site_data.get("avatar_image") or site_data.get("hero_image") or "assets/avatar.jpg"
    og_image = site_data.get("og_image") or avatar
    og_url = site_data.get("og_url") or site_data.get("publish_url") or ""
    replacements = {
        "{{PROFILE_STYLE}}": html.escape(profile_style),
        "{{BUSINESS_NAME}}": html.escape(site_data.get("business_name", "")),
        "{{DISPLAY_NAME}}": html.escape(display_name),
        "{{HERO_TITLE}}": hero_title(display_name, profile_style),
        "{{BIO}}": html.escape(site_data.get("bio", site_data.get("subheadline", ""))),
        "{{CATEGORY}}": html.escape(site_data.get("category", "")),
        "{{AVATAR_IMAGE}}": html.escape(avatar),
        "{{OG_IMAGE}}": html.escape(og_image),
        "{{OG_URL}}": html.escape(og_url),
        "{{SEO_DESCRIPTION}}": html.escape(site_data.get("seo_description", "")),
        "{{LINKS_HTML}}": render_links(links),
        "{{FONT_LINK}}": theme["fonts"],
        "{{THEME_OVERRIDE}}": render_theme_override(site_data),
        "{{INSTAGRAM_URL}}": html.escape(site_data.get("instagram_url", "#")),
        "{{USERNAME}}": html.escape(site_data.get("username", "")),
    }
    result = template
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result


def copy_gallery_assets(media_dir: Path, assets_dir: Path, gallery: list[dict[str, str]]) -> int:
    copied = 0
    if not media_dir.exists():
        return copied
    for gallery_item in gallery:
        filename = Path(gallery_item["src"]).name
        source = media_dir / filename
        if source.exists():
            shutil.copy2(source, assets_dir / filename)
            copied += 1
    return copied


def copy_profile_avatar(media_dir: Path, assets_dir: Path) -> bool:
    """Copia media/profile_pic.jpg para assets/avatar.jpg (foto de perfil no linktree)."""
    profile_pic = media_dir / "profile_pic.jpg"
    if not profile_pic.exists():
        return False
    shutil.copy2(profile_pic, assets_dir / "avatar.jpg")
    if not (assets_dir / "profile_pic.jpg").exists():
        shutil.copy2(profile_pic, assets_dir / "profile_pic.jpg")
    return True


def generate_site_demo(output_dir: Path, site_data: dict) -> Path:
    demo_dir = output_dir / "demo"
    assets_dir = demo_dir / "assets"

    if demo_dir.exists():
        shutil.rmtree(demo_dir)
    demo_dir.mkdir(parents=True)
    assets_dir.mkdir(parents=True)

    media_dir = output_dir / "media"
    copied = 1 if copy_profile_avatar(media_dir, assets_dir) else 0
    copied += copy_gallery_assets(media_dir, assets_dir, site_data.get("gallery", []))

    copy_site_template_files(demo_dir, include_netlify=True)
    favicon_bg, favicon_fg = favicon_colors(site_data, variant="site")
    write_favicon(
        demo_dir,
        site_data.get("category_base", site_data.get("category", "")),
        variant="site",
        bg=favicon_bg,
        fg=favicon_fg,
    )

    template = (SITE_TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    rendered = apply_site_template(template, site_data)
    (demo_dir / "index.html").write_text(rendered, encoding="utf-8")

    print(f"Site demo: {demo_dir} ({copied} imagens)")
    return demo_dir


def generate_linktree_demo(output_dir: Path, site_data: dict) -> Path:
    linktree_dir = output_dir / "linktree"
    assets_dir = linktree_dir / "assets"

    if linktree_dir.exists():
        shutil.rmtree(linktree_dir)
    linktree_dir.mkdir(parents=True)
    assets_dir.mkdir(parents=True)

    media_dir = output_dir / "media"
    copied = 1 if copy_profile_avatar(media_dir, assets_dir) else 0
    if copied:
        site_data = deepcopy(site_data)
        site_data["avatar_image"] = "assets/avatar.jpg"

    shutil.copy2(LINKTREE_TEMPLATE_DIR / "script.js", linktree_dir / "script.js")
    shutil.copy2(LINKTREE_TEMPLATE_DIR / "styles.css", linktree_dir / "styles.css")
    favicon_bg, favicon_fg = favicon_colors(site_data, variant="linktree")
    write_favicon(
        linktree_dir,
        site_data.get("category_base", site_data.get("category", "")),
        variant="linktree",
        bg=favicon_bg,
        fg=favicon_fg,
    )

    template = (LINKTREE_TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    rendered = apply_linktree_template(
        template,
        site_data,
        site_demo_path=site_data.get("site_demo_path", "../demo/index.html"),
    )
    (linktree_dir / "index.html").write_text(rendered, encoding="utf-8")

    print(f"Linktree demo: {linktree_dir} ({copied} imagens)")
    return linktree_dir


def generate_publish_bundle(output_dir: Path, site_data: dict) -> Path:
    publish_dir = output_dir / "publish"
    site_dir = publish_dir / "site"
    assets_dir = site_dir / "assets"
    linktree_assets = publish_dir / "assets"

    if publish_dir.exists():
        shutil.rmtree(publish_dir)
    site_dir.mkdir(parents=True)
    assets_dir.mkdir(parents=True)
    linktree_assets.mkdir(parents=True)

    media_dir = output_dir / "media"
    copied = 1 if copy_profile_avatar(media_dir, assets_dir) else 0
    copied += copy_gallery_assets(media_dir, assets_dir, site_data.get("gallery", []))
    for asset in assets_dir.iterdir():
        shutil.copy2(asset, linktree_assets / asset.name)
    copy_profile_avatar(media_dir, linktree_assets)

    publish_base = default_publish_url(site_data)
    username = site_data.get("username", "negocio")
    avatar_source = linktree_assets / "avatar.jpg"
    if avatar_source.exists():
        og_relative = prepare_og_image(linktree_assets, username, avatar_source)
        prepare_og_image(assets_dir, username, avatar_source)
        og_image = absolute_asset_url(publish_base, og_relative)
    else:
        og_image = ""

    publish_site_data = deepcopy(site_data)
    publish_site_data["avatar_image"] = "assets/profile_pic.jpg"
    publish_site_data["hero_image"] = ""
    publish_site_data["publish_url"] = publish_base
    publish_site_data["og_url"] = f"{publish_base}/site/" if publish_base else ""
    publish_site_data["og_image"] = (
        absolute_asset_url(publish_base, f"site/assets/og-{netlify_site_slug(username)}.jpg")
        if publish_base and og_image
        else og_image
    )

    copy_site_template_files(site_dir)
    favicon_bg, favicon_fg = favicon_colors(site_data, variant="site")
    write_favicon(
        site_dir,
        site_data.get("category_base", site_data.get("category", "")),
        variant="site",
        bg=favicon_bg,
        fg=favicon_fg,
    )
    write_favicon(
        publish_dir,
        site_data.get("category_base", site_data.get("category", "")),
        variant="linktree",
        bg=favicon_bg,
        fg=favicon_fg,
    )

    site_template = (SITE_TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    (site_dir / "index.html").write_text(
        apply_site_template(site_template, publish_site_data),
        encoding="utf-8",
    )

    publish_linktree_data = deepcopy(site_data)
    publish_linktree_data["avatar_image"] = "assets/avatar.jpg"
    publish_linktree_data["publish_url"] = publish_base
    publish_linktree_data["og_url"] = publish_base
    publish_linktree_data["og_image"] = (
        absolute_asset_url(publish_base, f"assets/og-{netlify_site_slug(username)}.jpg")
        if publish_base and og_image
        else og_image
    )

    shutil.copy2(LINKTREE_TEMPLATE_DIR / "script.js", publish_dir / "script.js")
    shutil.copy2(LINKTREE_TEMPLATE_DIR / "styles.css", publish_dir / "styles.css")

    linktree_template = (LINKTREE_TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    (publish_dir / "index.html").write_text(
        apply_linktree_template(
            linktree_template,
            publish_linktree_data,
            site_demo_path=site_data.get("site_demo_path_publish", "site/index.html"),
        ),
        encoding="utf-8",
    )

    shutil.copy2(SITE_TEMPLATE_DIR / "netlify.toml", publish_dir / "netlify.toml")
    print(f"Pacote publish: {publish_dir} ({copied} imagens)")
    return publish_dir


def generate_demo(output_dir: Path) -> dict[str, Path]:
    site_data_path = output_dir / "site_data.json"
    if not site_data_path.exists():
        raise FileNotFoundError(f"site_data.json não encontrado em {output_dir}")

    site_data = json.loads(site_data_path.read_text(encoding="utf-8"))

    return {
        "site": generate_site_demo(output_dir, site_data),
        "linktree": generate_linktree_demo(output_dir, site_data),
        "publish": generate_publish_bundle(output_dir, site_data),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gerar HTML demo (site + linktree + publish)")
    parser.add_argument("output_dir", help="Pasta com site_data.json")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    try:
        generate_demo(output_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
