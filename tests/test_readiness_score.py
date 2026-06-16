from __future__ import annotations

from pipeline.lib.readiness_score import score_profile


def _make_context(**overrides) -> dict:
    base = {
        "profile": {
            "username": "negocio",
            "full_name": "Negócio Local",
            "biography": "WhatsApp (71) 99999-8888",
        },
        "posts": [
            {"type": "image", "caption": "Serviço A - R$50"},
            {"type": "image", "caption": "Serviço B - R$80"},
            {"type": "image", "caption": "Serviço C"},
            {"type": "image", "caption": "Serviço D"},
            {"type": "image", "caption": "Serviço E"},
            {"type": "video", "caption": "Vídeo 1"},
            {"type": "video", "caption": "Vídeo 2"},
            {"type": "video", "caption": "Vídeo 3"},
        ],
    }
    base.update(overrides)
    return base


class TestScoreProfile:
    def test_high_score_recommends_demo(self):
        result = score_profile(_make_context())
        assert result["score"] >= 70
        assert result["grade"] == "alta"
        assert result["recommend_demo"] is True

    def test_low_score_does_not_recommend_demo(self):
        result = score_profile({"profile": {}, "posts": []})
        assert result["score"] < 60
        assert result["recommend_demo"] is False
        assert result["grade"] == "baixa"

    def test_detects_contact_hint_from_whatsapp_word(self):
        context = _make_context(
            profile={"username": "x", "full_name": "X", "biography": "Agende pelo WhatsApp"},
            posts=[{"type": "image", "caption": "foto"} for _ in range(8)],
        )
        assert context["profile"]["biography"]
        result = score_profile(context)
        assert result["checks"]["has_contact_hint"] is True
