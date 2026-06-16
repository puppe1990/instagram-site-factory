from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from pipeline.lib.instagram import (
    download_profile_picture,
    fetch_profile_web_api,
    metadata_matches_profile,
)
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


def _merge_profile_field(profile: dict[str, Any], field: str, value: Any) -> None:
    if value:
        profile[field] = value


def _sync_profile_from_web_api(profile: dict[str, Any]) -> None:
    username = profile.get("username", "")
    if not username:
        return

    try:
        web_info = fetch_profile_web_api(username)
    except Exception as exc:
        print(f"Aviso: não foi possível buscar bio via API: {exc}")
        return

    _merge_profile_field(profile, "biography", web_info.get("biography"))
    _merge_profile_field(profile, "full_name", web_info.get("full_name"))
    _merge_profile_field(profile, "external_url", web_info.get("external_url"))


def _ensure_profile_picture(profile: dict[str, Any], media_dir: Path) -> None:
    username = profile.get("username", "")
    if not username:
        return

    avatar_path = media_dir / "profile_pic.jpg"
    if download_profile_picture(username, avatar_path):
        profile["profile_pic"] = "media/profile_pic.jpg"


def enrich_context(output_dir: Path) -> dict[str, Any]:
    context_path = output_dir / "context.json"
    if not context_path.exists():
        raise FileNotFoundError(f"context.json não encontrado em {output_dir}")

    context = json.loads(context_path.read_text(encoding="utf-8"))
    media_dir = output_dir / "media"
    profile = context.setdefault("profile", {})
    profile_username = (profile.get("username") or "").lower()

    meta_files = sorted(media_dir.glob("*.json")) if media_dir.exists() else []
    matched_meta: dict[str, Any] | None = None

    for meta_path in meta_files:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if profile_username and metadata_matches_profile(meta, profile_username):
            matched_meta = meta
            break

    if matched_meta:
        owner = matched_meta.get("owner") or {}
        full_name = (
            matched_meta.get("fullname")
            or owner.get("full_name")
            or profile.get("full_name")
            or profile.get("username", "")
        )
        profile["full_name"] = full_name

        pic_url = (owner.get("hd_profile_pic_url_info") or {}).get("url") or owner.get("profile_pic_url")
        if pic_url:
            avatar_path = media_dir / "profile_pic.jpg"
            if download_url(pic_url, avatar_path):
                profile["profile_pic"] = "media/profile_pic.jpg"
    elif profile_username:
        print(f"Aviso: nenhum metadata de @{profile_username} — usando API pública para foto de perfil.")

    _sync_profile_from_web_api(profile)
    _ensure_profile_picture(profile, media_dir)

    captions = [post.get("caption", "") for post in context.get("posts", []) if post.get("caption")]
    if not profile.get("biography"):
        profile["biography"] = infer_bio(profile.get("full_name", ""), captions)

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
        if profile_username and not metadata_matches_profile(meta, profile_username):
            owner = meta.get("owner", {}).get("username") or meta.get("username") or "?"
            print(f"Ignorando reel de @{owner}: {meta_path.name}")
            continue

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
