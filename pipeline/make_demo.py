#!/usr/bin/env python3
"""CLI única: perfil Instagram → demo HTML pronto para Netlify."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.extract_profile import extract_profile  # noqa: E402
from pipeline.generate_demo_html import generate_demo, netlify_site_slug  # noqa: E402
from pipeline.lib.instagram import extract_username, normalize_profile_url  # noqa: E402
from pipeline.lib.metadata_enrich import enrich_context  # noqa: E402
from pipeline.parse_context import parse_context  # noqa: E402
from pipeline.transcribe_videos import (  # noqa: E402
    attach_transcripts,
    load_all_env,
    transcribe_profile,
)


def write_site_data(output_dir: Path, context: dict, *, publish_url: str | None = None) -> None:
    site_data = parse_context(context)
    if publish_url:
        site_data["publish_url"] = publish_url.rstrip("/")
    elif not site_data.get("publish_url"):
        username = site_data.get("username") or context.get("profile", {}).get("username", "")
        if username:
            site_data["publish_url"] = f"https://{netlify_site_slug(username)}.netlify.app"
    path = output_dir / "site_data.json"
    path.write_text(json.dumps(site_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"site_data salvo: {path}")


def deploy_netlify(demo_dir: Path) -> None:
    token = os.environ.get("NETLIFY_AUTH_TOKEN")
    site_id = os.environ.get("NETLIFY_SITE_ID")
    if not token:
        print("NETLIFY_AUTH_TOKEN não configurado — pule deploy ou use drag-and-drop.")
        return

    cmd = ["netlify", "deploy", "--prod", "--no-build", f"--dir={demo_dir}"]
    if site_id:
        cmd.extend(["--site", site_id])
    env = os.environ.copy()
    env["NETLIFY_AUTH_TOKEN"] = token
    subprocess.run(cmd, check=False, env=env)


def main() -> None:
    load_all_env()

    parser = argparse.ArgumentParser(description="Gerar demo de site a partir do Instagram")
    parser.add_argument("profile", help="URL ou @usuario")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument(
        "--transcribe-limit", type=int, default=12, help="Vídeos recentes para transcrever"
    )
    parser.add_argument(
        "--skip-transcribe", action="store_true", help="Pular transcrição dos vídeos"
    )
    parser.add_argument("--cookies-file", default=None)
    parser.add_argument("--deploy", action="store_true", help="Deploy automático no Netlify")
    parser.add_argument(
        "--publish-url", default=None, help="URL pública do site (ex.: https://usuario.netlify.app)"
    )
    parser.add_argument("--force", action="store_true", help="Gerar mesmo com score baixo")
    args = parser.parse_args()

    username = extract_username(normalize_profile_url(args.profile))
    output_dir = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / "output" / username
    cookies = args.cookies_file or os.environ.get("INSTAGRAM_COOKIES_FILE")

    context = extract_profile(args.profile, output_dir, cookies_file=cookies, limit=args.limit)
    context = enrich_context(output_dir)

    if not args.skip_transcribe:
        api_key = os.environ.get("AAI_API_KEY")
        if api_key:
            print(f"\n{'=' * 60}")
            print("TRANSCRIÇÃO DOS VÍDEOS")
            print(f"{'=' * 60}")
            transcripts = transcribe_profile(output_dir, api_key, limit=args.transcribe_limit)
            if transcripts:
                attach_transcripts(output_dir, transcripts)
                context = json.loads((output_dir / "context.json").read_text(encoding="utf-8"))
        else:
            print("AAI_API_KEY ausente — pulando transcrição.")

    readiness = context.get("readiness", {})
    if not args.force and not readiness.get("recommend_demo", True):
        print("\nPerfil com score baixo. Use --force para gerar mesmo assim.")
        sys.exit(2)

    publish_url = args.publish_url or os.environ.get("NETLIFY_PUBLISH_URL")

    write_site_data(output_dir, context, publish_url=publish_url)
    demos = generate_demo(output_dir)

    print(f"\n{'=' * 60}")
    print("DEMOS PRONTOS")
    print(f"Linktree:  {demos['linktree']}")
    print(f"Site:      {demos['site']}")
    print(f"Apresentação (recomendado): {demos['publish']}")
    print("Deploy: cd publish && netlify deploy --prod --dir=.")
    print(f"{'=' * 60}")

    if args.deploy:
        deploy_netlify(demos["publish"])


if __name__ == "__main__":
    main()
