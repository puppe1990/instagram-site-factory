#!/usr/bin/env python3
"""Extrai mídia, bio e legendas de um perfil Instagram → context.json."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.lib.instagram import (  # noqa: E402
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    download_media,
    extract_username,
    fetch_profile_info,
    normalize_profile_url,
    read_metadata,
)
from pipeline.lib.readiness_score import score_profile  # noqa: E402


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_posts(media_dir: Path) -> list[dict]:
    posts: list[dict] = []
    for media_path in sorted(media_dir.iterdir()):
        suffix = media_path.suffix.lower()
        if suffix not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
            continue

        metadata = read_metadata(media_path)
        caption = metadata.get("description") or metadata.get("caption") or ""
        post_date = metadata.get("date") or metadata.get("post_date") or ""
        if isinstance(post_date, str) and post_date:
            pass
        elif post_date:
            post_date = str(post_date)

        posts.append(
            {
                "filename": media_path.name,
                "path": str(media_path.relative_to(media_dir.parent)),
                "type": "video" if suffix in VIDEO_EXTENSIONS else "image",
                "caption": caption.strip(),
                "date": post_date,
                "url": metadata.get("post_url") or metadata.get("url") or "",
                "shortcode": metadata.get("post_shortcode") or metadata.get("shortcode") or "",
                "likes": metadata.get("likes") or 0,
                "tags": metadata.get("tags") or [],
                "post_type": metadata.get("type") or metadata.get("subcategory") or "",
                "comments": metadata.get("comment_count") or metadata.get("comments") or 0,
            }
        )
    return posts


def extract_profile(
    profile_input: str,
    output_dir: Path,
    cookies_file: str | None = None,
    limit: int | None = 40,
) -> dict:
    profile_url = normalize_profile_url(profile_input)
    username = extract_username(profile_url)

    output_dir.mkdir(parents=True, exist_ok=True)
    media_dir = output_dir / "media"
    media_dir.mkdir(exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"Extraindo @{username}")
    print(f"{'=' * 60}")

    download_media(profile_url, media_dir, cookies_file=cookies_file, limit=limit)

    print("\nBuscando bio e metadados do perfil...")
    try:
        profile_info = fetch_profile_info(username, cookies_file=cookies_file)
    except Exception as exc:
        print(f"Aviso: não foi possível buscar bio via instaloader: {exc}")
        try:
            from pipeline.lib.instagram import fetch_profile_web_api

            profile_info = fetch_profile_web_api(username)
            print(f"Bio obtida via API pública: {len(profile_info.get('biography', ''))} caracteres")
        except Exception as api_exc:
            print(f"Aviso: API pública também falhou: {api_exc}")
            profile_info = {"username": username, "full_name": username, "biography": ""}

    posts = build_posts(media_dir)
    context = {
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "profile_url": profile_url,
        "profile": profile_info,
        "posts": posts,
        "stats": {
            "images": sum(1 for post in posts if post["type"] == "image"),
            "videos": sum(1 for post in posts if post["type"] == "video"),
            "with_caption": sum(1 for post in posts if post["caption"]),
        },
    }
    context["readiness"] = score_profile(context)

    context_path = output_dir / "context.json"
    context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\nContexto salvo: {context_path}")
    print(f"Score de prontidão: {context['readiness']['score']}/100 ({context['readiness']['grade']})")
    print(context["readiness"]["summary"])
    return context


def main() -> None:
    load_env(PROJECT_ROOT / ".env")

    parser = argparse.ArgumentParser(description="Extrair contexto de perfil Instagram")
    parser.add_argument("profile", help="URL ou @usuario")
    parser.add_argument("--output-dir", default=None, help="Diretório de saída (default: output/<user>)")
    parser.add_argument("--limit", type=int, default=40, help="Máximo de posts para baixar")
    parser.add_argument("--cookies-file", default=None, help="Cookies Netscape para perfis privados")
    args = parser.parse_args()

    username = extract_username(normalize_profile_url(args.profile))
    output_dir = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / "output" / username
    cookies = args.cookies_file or os.environ.get("INSTAGRAM_COOKIES_FILE")

    extract_profile(args.profile, output_dir, cookies_file=cookies, limit=args.limit)


if __name__ == "__main__":
    main()