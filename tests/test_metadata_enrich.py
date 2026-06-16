from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from pipeline.lib.metadata_enrich import enrich_context, infer_bio


class TestInferBio:
    def test_advogado_template(self):
        bio = infer_bio("Cleverson Borges | Advogado", ["#advogado #humor"])
        assert "Advogado" in bio
        assert "consulta" in bio.lower()


class TestEnrichContext:
    def test_adds_thumbnails_from_video_metadata(self, tmp_path: Path):
        output = tmp_path / "user"
        media = output / "media"
        media.mkdir(parents=True)

        video_name = "2026-06-01_TEST [1].mp4"
        (media / video_name).touch()
        meta = {
            "description": "Legenda do reel",
            "likes": 100,
            "date": "2026-06-01",
            "post_url": "https://instagram.com/p/test",
            "post_shortcode": "TEST",
            "display_url": "https://example.com/thumb.jpg",
            "owner": {"full_name": "Cleverson Borges", "profile_pic_url": "https://example.com/pic.jpg"},
            "username": "cleversonborges.adv",
            "fullname": "Cleverson Borges | Advogado",
        }
        (media / f"{video_name}.json").write_text(json.dumps(meta), encoding="utf-8")

        context = {
            "profile": {"username": "cleversonborges.adv"},
            "posts": [
                {
                    "filename": video_name,
                    "type": "video",
                    "caption": "",
                    "date": "",
                    "url": "",
                    "shortcode": "TEST",
                }
            ],
        }
        (output / "context.json").write_text(json.dumps(context), encoding="utf-8")

        with (
            patch("pipeline.lib.metadata_enrich.download_url", return_value=True),
            patch(
                "pipeline.lib.metadata_enrich.fetch_profile_web_api",
                return_value={
                    "biography": "⚖️ Defendo DIREITOS\n☎️ Contato abaixo",
                    "full_name": "Cleverson Borges | Advogado",
                    "external_url": "https://wa.me/5532920007640",
                },
            ),
        ):
            (media / f"2026-06-01_TEST [1]_thumb.jpg").write_bytes(b"img")
            (media / "profile_pic.jpg").write_bytes(b"pic")
            result = enrich_context(output)

        assert result["profile"]["full_name"] == "Cleverson Borges | Advogado"
        assert "Defendo DIREITOS" in result["profile"]["biography"]
        assert result["profile"]["external_url"] == "https://wa.me/5532920007640"
        image_posts = [p for p in result["posts"] if p["type"] == "image"]
        assert any("_thumb.jpg" in p["filename"] for p in image_posts)
        assert result["posts"][0]["likes"] == 100