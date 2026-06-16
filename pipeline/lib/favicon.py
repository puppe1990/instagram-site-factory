"""Gera favicon.svg com ícones Lucide por categoria."""

from __future__ import annotations

from pathlib import Path

# Paths extraídos do Lucide (ISC) — https://lucide.dev
LUCIDE_ICONS: dict[str, list[str]] = {
    "scale": [
        "M12 3v18",
        "M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2",
        "m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z",
        "m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z",
        "M7 21h10",
    ],
    "scissors": [
        "M5.42 9.71a4 4 0 1 0 0 5.58",
        "M5.42 9.71 15.6 3.6a1 1 0 0 1 1.4.2l2.8 3.5a1 1 0 0 1-.2 1.4L9.42 14.3",
        "M5.42 14.29 15.6 20.4a1 1 0 0 0 1.4-.2l2.8-3.5a1 1 0 0 0-.2-1.4L9.42 9.7",
        "M9 6h.01",
        "M9 18h.01",
    ],
    "stethoscope": [
        "M11 2v2",
        "M5 2v2",
        "M5 3H4a2 2 0 0 0-2 2v4a6 6 0 0 0 6 6 6 6 0 0 0 6-6V5a2 2 0 0 0-2-2h-1",
        "M8 15a6 6 0 0 0 12 0v-3",
        "M11 9h2",
    ],
    "utensils": [
        "M3 2v7c0 1.1.9 2 2 2h0a2 2 0 0 0 2-2V2",
        "M7 2v20",
        "M21 15V2a5 5 0 0 0-5 5v8",
        "M21 15v7",
    ],
    "dumbbell": [
        "M17.596 12.408 19 11",
        "M6.404 12.408 5 11",
        "M12 7v10",
        "M7.5 9.5 5 12",
        "M16.5 9.5 19 12",
        "M5 11v2",
        "M19 11v2",
        "M7.5 14.5 5 17",
        "M16.5 14.5 19 17",
    ],
    "paw-print": [
        "M11 11v-1a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v1",
        "M16 8V7a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v1",
        "M5 8V7a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v1",
        "M8 11v-1a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v1",
        "M7.5 15.5c.83.83 2.17 1.5 4.5 1.5s3.67-.67 4.5-1.5",
    ],
    "store": [
        "M2 7h20",
        "M4 7v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7",
        "M12 7V5a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2",
    ],
}

CATEGORY_ICON: dict[str, str] = {
    "Advocacia": "scale",
    "Salão de Beleza": "scissors",
    "Clínica": "stethoscope",
    "Restaurante": "utensils",
    "Personal Trainer": "dumbbell",
    "Pet Shop": "paw-print",
}

THEMES = {
    "site": {"bg": "#0f172a", "fg": "#c9a227"},
    "linktree": {"bg": "#15110f", "fg": "#e07a5f"},
}


def icon_name_for_category(category: str) -> str:
    return CATEGORY_ICON.get(category, "store")


def build_favicon_svg(
    category: str,
    *,
    variant: str = "site",
    bg: str | None = None,
    fg: str | None = None,
) -> str:
    icon_key = icon_name_for_category(category)
    paths = LUCIDE_ICONS[icon_key]
    theme = THEMES.get(variant, THEMES["site"])
    if bg:
        theme = {**theme, "bg": bg}
    if fg:
        theme = {**theme, "fg": fg}

    paths_markup = "\n      ".join(f'<path d="{path}"/>' for path in paths)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="Ícone">
  <rect width="32" height="32" rx="8" fill="{theme['bg']}"/>
  <g
    transform="translate(4 4)"
    fill="none"
    stroke="{theme['fg']}"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
      {paths_markup}
  </g>
</svg>
"""


def write_favicon(
    dest_dir: Path,
    category: str,
    *,
    variant: str = "site",
    bg: str | None = None,
    fg: str | None = None,
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    favicon_path = dest_dir / "favicon.svg"
    favicon_path.write_text(
        build_favicon_svg(category, variant=variant, bg=bg, fg=fg),
        encoding="utf-8",
    )
    return favicon_path