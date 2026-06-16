from __future__ import annotations

import json
from pathlib import Path

from pipeline.lib.transcribe import _video_sort_key, format_transcript
from pipeline.transcribe_videos import attach_transcripts


class TestFormatTranscript:
    def test_joins_utterances_without_speaker_prefix(self):
        result = format_transcript(
            {
                "utterances": [
                    {"speaker": "A", "text": "Olá"},
                    {"speaker": "B", "text": "mundo"},
                ]
            }
        )
        assert result == "Olá mundo"

    def test_falls_back_to_plain_text(self):
        assert format_transcript({"text": "Texto direto"}) == "Texto direto"


class TestVideoSortKey:
    def test_sorts_by_likes_from_metadata(self, tmp_path: Path):
        low = tmp_path / "low.mp4"
        high = tmp_path / "high.mp4"
        low.touch()
        high.touch()
        low.with_suffix(".mp4.json").write_text(json.dumps({"likes": 10}), encoding="utf-8")
        high.with_suffix(".mp4.json").write_text(json.dumps({"likes": 999}), encoding="utf-8")
        assert _video_sort_key(high) > _video_sort_key(low)


class TestAttachTranscripts:
    def test_writes_transcript_to_matching_video_post(self, tmp_output_dir: Path):
        media = tmp_output_dir / "media"
        media.mkdir()
        context = {
            "profile": {"username": "test"},
            "posts": [
                {
                    "filename": "2026-06-01_ABC [1].mp4",
                    "type": "video",
                    "caption": "Legenda",
                    "date": "2026-06-01",
                    "url": "https://instagram.com/p/abc",
                    "likes": 5,
                }
            ],
        }
        (tmp_output_dir / "context.json").write_text(json.dumps(context), encoding="utf-8")

        stem = "2026-06-01_ABC [1]"
        attach_transcripts(tmp_output_dir, {stem: "Texto transcrito do vídeo."})

        updated = json.loads((tmp_output_dir / "context.json").read_text(encoding="utf-8"))
        assert updated["posts"][0]["transcript"] == "Texto transcrito do vídeo."
        assert updated["transcription"]["with_text"] == 1
        assert (tmp_output_dir / "all_transcripts.txt").exists()