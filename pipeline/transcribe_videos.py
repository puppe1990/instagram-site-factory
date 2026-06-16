#!/usr/bin/env python3
"""Transcreve vídeos do perfil e anexa ao context.json."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.extract_profile import load_env  # noqa: E402
from pipeline.lib.transcribe import convert_videos_to_mp3, transcribe_mp3_files  # noqa: E402

DEFAULT_ENV_FILES = [
    PROJECT_ROOT / ".env",
    Path("/Users/matheuspuppe/Desktop/estudo/my_life/.env"),
]


def load_all_env() -> None:
    for path in DEFAULT_ENV_FILES:
        load_env(path)


def attach_transcripts(output_dir: Path, transcripts: dict[str, str]) -> None:
    context_path = output_dir / "context.json"
    context = json.loads(context_path.read_text(encoding="utf-8"))

    for post in context.get("posts", []):
        if post.get("type") != "video":
            continue
        stem = Path(post["filename"]).stem
        if stem in transcripts:
            post["transcript"] = transcripts[stem]

    context["transcription"] = {
        "count": len(transcripts),
        "with_text": sum(1 for text in transcripts.values() if text.strip()),
    }

    combined_lines = []
    for post in sorted(context.get("posts", []), key=lambda item: item.get("date", ""), reverse=True):
        if post.get("type") != "video" or not post.get("transcript"):
            continue
        combined_lines.append(
            "\n".join(
                [
                    f"## {post.get('caption') or post.get('shortcode', 'Post')}",
                    f"Data: {post.get('date', '')}",
                    f"URL: {post.get('url', '')}",
                    f"Likes: {post.get('likes', 0)}",
                    post["transcript"],
                ]
            )
        )

    combined_path = output_dir / "all_transcripts.txt"
    combined_path.write_text("\n\n---\n\n".join(combined_lines).strip() + "\n", encoding="utf-8")
    context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Transcrições anexadas ao context.json ({context['transcription']['with_text']} com texto)")
    print(f"Combinado: {combined_path}")


def transcribe_profile(output_dir: Path, api_key: str, limit: int = 12) -> dict[str, str]:
    media_dir = output_dir / "media"
    audio_dir = output_dir / "audios"
    transcript_dir = output_dir / "transcricoes"

    mp3_files = convert_videos_to_mp3(media_dir, audio_dir, limit=limit)
    if not mp3_files:
        print("Nenhum vídeo para transcrever.")
        return {}

    return transcribe_mp3_files(mp3_files, transcript_dir, api_key)


def main() -> None:
    load_all_env()

    parser = argparse.ArgumentParser(description="Transcrever vídeos e atualizar context.json")
    parser.add_argument("output_dir", help="Pasta do perfil (ex: output/cleversonborges.adv)")
    parser.add_argument("--limit", type=int, default=12, help="Máximo de vídeos recentes")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    api_key = os.environ.get("AAI_API_KEY")
    if not api_key:
        print("AAI_API_KEY não configurada.", file=sys.stderr)
        sys.exit(1)

    transcripts = transcribe_profile(output_dir, api_key, limit=args.limit)
    if transcripts:
        attach_transcripts(output_dir, transcripts)


if __name__ == "__main__":
    main()