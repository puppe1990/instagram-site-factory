from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_SCRIPTS_VENV = Path("/Users/matheuspuppe/Desktop/estudo/code_scripts/.venv-instagram/bin/gallery-dl")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4"}


def normalize_profile_url(value: str) -> str:
    value = value.strip()
    if value.startswith("@"):
        value = value[1:]
    if "instagram.com" not in value:
        value = f"https://www.instagram.com/{value}/"
    return value


def extract_username(profile_url: str) -> str:
    match = re.search(r"instagram\.com/([^/?#]+)", profile_url)
    if not match:
        raise ValueError(f"URL inválida do Instagram: {profile_url}")
    username = match.group(1).strip("/")
    blocked = {"p", "reel", "reels", "stories", "explore", "accounts", "tv"}
    if username in blocked:
        raise ValueError(f"Informe a URL do perfil, não de um post: {profile_url}")
    return username


def find_gallery_dl() -> str:
    candidates = [
        PROJECT_ROOT / ".venv" / "bin" / "gallery-dl",
        CODE_SCRIPTS_VENV,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    found = shutil.which("gallery-dl")
    if found:
        return found
    raise RuntimeError(
        "gallery-dl não encontrado. Rode: pip install -r requirements.txt"
    )


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode not in (0, 4):
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Comando falhou: {' '.join(cmd)}\n{stderr}")
    return result


def build_source_urls(username: str) -> list[str]:
    return [
        f"https://www.instagram.com/{username}/",
        f"https://www.instagram.com/{username}/posts/",
        f"https://www.instagram.com/{username}/reels/",
    ]


def download_media(
    profile_url: str,
    output_dir: Path,
    cookies_file: str | None = None,
    limit: int | None = 40,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    username = extract_username(profile_url)
    gallery_dl = find_gallery_dl()

    extensions = ", ".join(repr(ext.lstrip(".")) for ext in sorted(IMAGE_EXTENSIONS | VIDEO_EXTENSIONS))
    media_filter = f"extension in ({extensions})"

    cmd = [
        gallery_dl,
        "-D",
        str(output_dir),
        "-f",
        "{date:%Y-%m-%d}_{post_shortcode} [{post_id}].{extension}",
        "--write-metadata",
        "--filter",
        media_filter,
    ]
    if limit:
        cmd.extend(["--range", f"1-{limit}"])
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])

    cmd.extend(build_source_urls(username))

    print(f"Baixando mídia de @{username} → {output_dir}")
    run_cmd(cmd, check=True)

    files = sorted(
        path
        for path in output_dir.iterdir()
        if path.suffix.lower() in (IMAGE_EXTENSIONS | VIDEO_EXTENSIONS)
    )
    print(f"Mídia baixada: {len(files)} arquivo(s)")
    return files


def read_metadata(media_path: Path) -> dict:
    metadata_path = media_path.with_suffix(media_path.suffix + ".json")
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def fetch_profile_web_api(username: str) -> dict:
    """Busca bio e metadados via API pública do Instagram (fallback sem login)."""
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "X-IG-App-ID": "936619743392459",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    user = payload.get("data", {}).get("user", {})
    return {
        "username": user.get("username") or username,
        "full_name": user.get("full_name") or "",
        "biography": user.get("biography") or "",
        "external_url": user.get("external_url") or "",
        "followers": user.get("edge_followed_by", {}).get("count"),
        "following": user.get("edge_follow", {}).get("count"),
        "posts_count": user.get("edge_owner_to_timeline_media", {}).get("count"),
        "is_business": user.get("is_business_account"),
        "category": user.get("category_name") or user.get("business_category_name") or "",
        "profile_pic_url_hd": user.get("profile_pic_url_hd") or "",
        "profile_pic_url": user.get("profile_pic_url") or "",
    }


def meta_owner_username(meta: dict) -> str:
    owner = meta.get("owner") or {}
    return (meta.get("username") or owner.get("username") or "").lower()


def metadata_matches_profile(meta: dict, profile_username: str) -> bool:
    owner = meta_owner_username(meta)
    if not owner:
        return True
    if not profile_username:
        return True
    return owner == profile_username.lower()


def download_profile_picture(username: str, dest: Path) -> bool:
    """Baixa a foto de perfil via API pública (fonte confiável do dono do perfil)."""
    try:
        info = fetch_profile_web_api(username)
    except Exception as exc:
        print(f"Aviso: não foi possível buscar foto de perfil de @{username}: {exc}")
        return False

    pic_url = info.get("profile_pic_url_hd") or info.get("profile_pic_url")
    if not pic_url:
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(pic_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
        return dest.stat().st_size > 0
    except Exception as exc:
        print(f"Aviso: falha ao baixar foto de perfil: {exc}")
        return False


def fetch_profile_info(username: str, cookies_file: str | None = None) -> dict:
    try:
        import instaloader
    except ImportError as exc:
        raise RuntimeError("instaloader não instalado. Rode: pip install instaloader") from exc

    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )
    if cookies_file:
        loader.load_session_from_file(username, cookies_file)

    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        return {
            "username": profile.username,
            "full_name": profile.full_name or "",
            "biography": profile.biography or "",
            "external_url": profile.external_url or "",
            "followers": profile.followers,
            "following": profile.followees,
            "posts_count": profile.mediacount,
            "is_business": profile.is_business_account,
            "category": profile.business_category_name or "",
        }
    except Exception:
        return fetch_profile_web_api(username)