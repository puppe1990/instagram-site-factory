from __future__ import annotations

import json
from pathlib import Path

import pytest

from unittest.mock import patch

from pipeline.lib.instagram import (
    build_source_urls,
    extract_username,
    fetch_profile_web_api,
    normalize_profile_url,
    read_metadata,
)


class TestNormalizeProfileUrl:
    def test_adds_https_for_username_only(self):
        assert normalize_profile_url("salao_beleza") == "https://www.instagram.com/salao_beleza/"

    def test_strips_at_prefix(self):
        assert normalize_profile_url("@salao_beleza") == "https://www.instagram.com/salao_beleza/"

    def test_keeps_full_url(self):
        url = "https://www.instagram.com/salao_beleza/"
        assert normalize_profile_url(url) == url


class TestExtractUsername:
    def test_extracts_from_profile_url(self):
        assert extract_username("https://www.instagram.com/cleversonborges.adv/") == "cleversonborges.adv"

    def test_rejects_post_url(self):
        with pytest.raises(ValueError, match="perfil"):
            extract_username("https://www.instagram.com/p/abc123/")

    def test_rejects_reel_url(self):
        with pytest.raises(ValueError, match="perfil"):
            extract_username("https://www.instagram.com/reel/abc123/")


class TestBuildSourceUrls:
    def test_includes_posts_and_reels(self):
        urls = build_source_urls("salao_beleza")
        assert len(urls) == 3
        assert any("/posts/" in url for url in urls)
        assert any("/reels/" in url for url in urls)


class TestFetchProfileWebApi:
    def test_parses_user_payload(self):
        payload = {
            "data": {
                "user": {
                    "username": "cleversonborges.adv",
                    "full_name": "Cleverson Borges | Advogado",
                    "biography": "Bio real do Instagram",
                    "external_url": "https://wa.me/5532920007640",
                    "edge_followed_by": {"count": 100},
                    "edge_follow": {"count": 50},
                    "edge_owner_to_timeline_media": {"count": 10},
                    "is_business_account": True,
                    "category_name": "Lawyer",
                }
            }
        }

        class FakeResp:
            def read(self):
                return json.dumps(payload).encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch("pipeline.lib.instagram.urllib.request.urlopen", return_value=FakeResp()):
            info = fetch_profile_web_api("cleversonborges.adv")

        assert info["biography"] == "Bio real do Instagram"
        assert info["external_url"] == "https://wa.me/5532920007640"


class TestReadMetadata:
    def test_returns_empty_dict_when_missing(self, tmp_path: Path):
        assert read_metadata(tmp_path / "video.mp4") == {}

    def test_reads_valid_json(self, tmp_path: Path):
        video = tmp_path / "video.mp4"
        video.touch()
        meta = {"description": "Legenda teste", "likes": 42}
        video.with_suffix(".mp4.json").write_text(json.dumps(meta), encoding="utf-8")
        assert read_metadata(video)["likes"] == 42

    def test_returns_empty_on_invalid_json(self, tmp_path: Path):
        video = tmp_path / "video.mp4"
        video.touch()
        video.with_suffix(".mp4.json").write_text("{invalid", encoding="utf-8")
        assert read_metadata(video) == {}