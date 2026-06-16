from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any

from pipeline.lib.instagram import fetch_profile_web_api
from pipeline.lib.readiness_score import score_profile


def download_url(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
        return dest.stat().st_size > 0
    except Exception as exc:
        print(f"Aviso: falha ao baixar {dest.name}: {exc}")
        return False


def infer_bio(full_name: str, captions: list[str]) -> str:
    text = " ".join(captions).lower()
    if "advogad" in text or ".adv" in full_name.lower():
        return (
            "Advogado com atendimento jurídico dedicado. "
            "Tire suas dúvidas e agende uma consulta pelo WhatsApp."
        )
    if full_name:
        return f"{full_name}. Acompanhe nossos conteúdos e entre em contato."
    return "Entre em contato para saber mais sobre nossos serviços."


def enrich_context(output_dir: Path) -> dict[str, Any]:
    context_path = output_dir / "context.json"
    if not context_path.exists():
        raise FileNotFoundError(f"context.json não encontrado em {output_dir}")

    context = json.loads(context_path.read_text(encoding="utf-8"))
    media_dir = output_dir / "media"
    profile = context.setdefault("profile", {})

    meta_files = sorted(media_dir.glob("*.json"))
    if not meta_files:
        return context

    profile_username = (profile.get("username") or "").lower()
    owner: dict[str, Any] = {}
    full_name = profile.get("full_name", "")
    matched_meta: dict[str, Any] | None = None

    for meta_path in meta_files:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta_owner = meta.get("owner") or {}
        meta_username = (meta.get("username") or meta_owner.get("username") or "").lower()
        if profile_username and meta_username == profile_username:
            matched_meta = meta
            owner = meta_owner
            break

    if matched_meta is None:
        matched_meta = json.loads(meta_files[0].read_text(encoding="utf-8"))
        owner = matched_meta.get("owner", {})

    full_name = (
        matched_meta.get("fullname")
        or owner.get("full_name")
        or full_name
        or profile.get("username", "")
    )
    profile["full_name"] = full_name
    profile["username"] = matched_meta.get("username") or profile.get("username", "")

    pic_url = (owner.get("hd_profile_pic_url_info") or {}).get("url") or owner.get("profile_pic_url")
    if pic_url:
        avatar_path = media_dir / "profile_pic.jpg"
        if download_url(pic_url, avatar_path):
            profile["profile_pic"] = "media/profile_pic.jpg"

    username = profile.get("username", "")
    if username:
        try:
            web_info = fetch_profile_web_api(username)
            if web_info.get("biography"):
                profile["biography"] = web_info["biography"]
            if web_info.get("full_name"):
                profile["full_name"] = web_info["full_name"]
            if web_info.get("external_url"):
                profile["external_url"] = web_info["external_url"]
        except Exception as exc:
            print(f"Aviso: não foi possível buscar bio via API: {exc}")

    captions = [post.get("caption", "") for post in context.get("posts", []) if post.get("caption")]
    if not profile.get("biography"):
        profile["biography"] = infer_bio(full_name, captions)

    existing_images = {
        post.get("filename")
        for post in context.get("posts", [])
        if post.get("type") == "image"
    }

    posts_by_filename = {post.get("filename"): post for post in context.get("posts", [])}

    for meta_path in meta_files:
        if not meta_path.name.endswith(".mp4.json"):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        video_name = meta_path.name.replace(".json", "")
        video_post = posts_by_filename.get(video_name)
        if video_post:
            video_post.update(
                {
                    "likes": meta.get("likes") or video_post.get("likes", 0),
                    "tags": meta.get("tags") or video_post.get("tags", []),
                    "post_type": meta.get("type") or meta.get("subcategory") or "",
                    "caption": (meta.get("description") or meta.get("caption") or video_post.get("caption", "")).strip(),
                    "url": meta.get("post_url") or video_post.get("url", ""),
                    "shortcode": meta.get("post_shortcode") or video_post.get("shortcode", ""),
                    "date": str(meta.get("date") or meta.get("post_date") or video_post.get("date", "")),
                }
            )

        display_url = meta.get("display_url")
        if not display_url:
            continue

        video_stem = meta_path.name.replace(".mp4.json", "")
        thumb_name = f"{video_stem}_thumb.jpg"
        if thumb_name in existing_images:
            continue

        thumb_path = media_dir / thumb_name
        if not thumb_path.exists():
            download_url(display_url, thumb_path)

        if thumb_path.exists():
            caption = meta.get("description") or meta.get("caption") or ""
            post_date = meta.get("date") or meta.get("post_date") or ""
            context.setdefault("posts", []).append(
                {
                    "filename": thumb_name,
                    "path": f"media/{thumb_name}",
                    "type": "image",
                    "caption": caption.strip(),
                    "date": str(post_date),
                    "url": meta.get("post_url") or "",
                    "shortcode": meta.get("post_shortcode") or "",
                    "likes": meta.get("likes") or 0,
                    "tags": meta.get("tags") or [],
                    "source_video": video_name,
                }
            )
            existing_images.add(thumb_name)

    posts = context.get("posts", [])
    context["stats"] = {
        "images": sum(1 for post in posts if post.get("type") == "image"),
        "videos": sum(1 for post in posts if post.get("type") == "video"),
        "with_caption": sum(1 for post in posts if post.get("caption")),
    }
    context["readiness"] = score_profile(context)

    context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Contexto enriquecido: {context_path}")
    print(f"Imagens disponíveis: {context['stats']['images']}")
    print(f"Score: {context['readiness']['score']}/100")
    return context