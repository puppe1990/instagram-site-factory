from __future__ import annotations

from pipeline.parse_context import (
    build_highlights,
    build_links,
    clean_caption,
    detect_profile_style,
    display_name,
    extract_city,
    extract_email,
    extract_phone,
    extract_services,
    extract_topics,
    extract_website,
    guess_category,
    parse_context,
    strip_emojis,
)


class TestExtractPhone:
    def test_extracts_brazilian_mobile(self):
        assert extract_phone("WhatsApp (71) 99999-8888") == "5571999998888"

    def test_returns_none_when_missing(self):
        assert extract_phone("Sem contato aqui") is None


class TestExtractServices:
    def test_parses_price_lines_from_captions(self):
        captions = ["Balayage premium - R$280", "Manicure - R$35"]
        services = extract_services(captions)
        assert len(services) == 2
        assert services[0]["price"] == "R$280"


class TestGuessCategory:
    def test_detects_advocacia(self):
        assert guess_category({}, ["#advogado #humor"]) == "Advocacia"

    def test_maps_instagram_english_lawyer_category(self):
        profile = {"category": "Estate Planning Lawyer", "biography": "Advogada imobiliarista"}
        assert guess_category(profile, []) == "Advocacia"

    def test_detects_salao(self):
        assert guess_category({}, ["Manicure e cabelo"]) == "Salão de Beleza"


class TestExtractCityAndContact:
    def test_extracts_city_from_hashtag(self):
        posts = [{"tags": ["#londrina", "#advogada"]}]
        assert extract_city({}, posts) == "Londrina, PR"

    def test_extracts_email_and_website(self):
        text = "Contato: juridico.tahismunhoz@gmail.com www.tahismunhozadvocacia.com.br"
        assert extract_email(text) == "juridico.tahismunhoz@gmail.com"
        assert "tahismunhozadvocacia.com.br" in extract_website(text)


class TestDisplayName:
    def test_splits_on_pipe_separator(self):
        assert display_name("Tahís Munhoz | Advogada") == "Tahís Munhoz"

    def test_splits_on_i_separator(self):
        assert display_name("Tahís Munhoz Advogada I Imobiliarista") == "Tahís Munhoz Advogada"


class TestParseContextImobiliarista:
    def test_builds_services_for_estate_lawyer_profile(self):
        context = {
            "profile_url": "https://www.instagram.com/advocaciatahismunhoz/",
            "profile": {
                "username": "advocaciatahismunhoz",
                "full_name": "Tahís Munhoz Advogada I Imobiliarista",
                "biography": "Descomplicando regularizações imobiliárias e tributárias.\n📍Atendimento presencial e online.",
                "category": "Estate Planning Lawyer",
                "external_url": "https://wa.me/message/AFDINQT4HZB2H1",
            },
            "posts": [
                {
                    "type": "video",
                    "caption": "Usucapião exige análise técnica. (43) 98454-4623 juridico.tahismunhoz@gmail.com www.tahismunhozadvocacia.com.br #londrina #direitoimobiliario",
                    "likes": 37,
                    "tags": ["#londrina", "#direitoimobiliario"],
                },
                {
                    "type": "video",
                    "caption": "ITBI pago a mais pode ser recuperado.",
                    "likes": 29,
                    "tags": [],
                },
            ],
        }
        site = parse_context(context)
        assert site["category_base"] == "Advocacia"
        assert site["category"] == "Direito Imobiliário"
        assert site["city"] == "Londrina, PR"
        assert site["email"] == "juridico.tahismunhoz@gmail.com"
        assert "tahismunhozadvocacia.com.br" in site["website_url"]
        assert len(site["services"]) >= 2
        assert site["cta_label"] == "Agendar consulta"
        service_names = [item["name"] for item in site["services"]]
        assert any("Usucapião" in name or "Regularização" in name for name in service_names)


class TestCleanCaption:
    def test_removes_hashtag_lines(self):
        caption = "Título do post\n\n#advogado #humor"
        assert clean_caption(caption) == "Título do post"


class TestExtractTopics:
    def test_finds_law_topics_from_transcripts(self, sample_lawyer_context):
        posts = sample_lawyer_context["posts"]
        topics = extract_topics(posts, "Advocacia")
        assert "Direito Criminal" in topics
        assert "Direito Trabalhista" in topics


class TestDetectProfileStyle:
    def test_detects_creator_from_bio(self, sample_lawyer_context):
        context = dict(sample_lawyer_context)
        context["profile"] = dict(context["profile"])
        context["profile"]["biography"] = (
            "Defendo direitos e ministro palestras para te fazer sorrir"
        )
        assert detect_profile_style(context["profile"], context["posts"]) == "creator"

    def test_detects_professional_from_practice_bio(self, sample_lawyer_context):
        assert (
            detect_profile_style(sample_lawyer_context["profile"], sample_lawyer_context["posts"])
            == "professional"
        )


class TestStripEmojis:
    def test_removes_emojis(self):
        assert "Defendo" in strip_emojis("⚖️ Defendo DIREITOS ⬇️")


class TestBuildHighlights:
    def test_prefers_transcript_over_caption_for_excerpt(self):
        posts = [
            {
                "type": "video",
                "caption": "Título curto",
                "transcript": "Texto longo da fala do vídeo sobre direito criminal e audiência.",
                "likes": 100,
                "date": "2026-06-01",
                "url": "https://example.com",
            }
        ]
        highlights = build_highlights(posts)
        assert "fala do vídeo" in highlights[0]["excerpt"]

    def test_sorts_transcript_posts_before_caption_only(self):
        posts = [
            {
                "type": "video",
                "caption": "Só legenda",
                "likes": 9999,
                "date": "2026-06-01",
                "url": "",
            },
            {
                "type": "video",
                "caption": "Com transcrição",
                "transcript": "Conteúdo transcrito aqui.",
                "likes": 10,
                "date": "2026-06-02",
                "url": "",
            },
        ]
        highlights = build_highlights(posts, limit=1)
        assert "transcrito" in highlights[0]["excerpt"]


class TestBuildLinks:
    def test_includes_whatsapp_and_site(self):
        links = build_links(
            whatsapp_url="https://wa.me/5511999999999",
            cta_label="Agendar",
            instagram_url="https://instagram.com/x",
            phone="5511999999999",
            external_url="",
            services=[],
        )
        labels = [link["label"] for link in links]
        assert "Agendar" in labels
        assert "Ver site completo" in labels
        assert links[0]["style"] == "primary"


class TestParseContext:
    def test_builds_site_data_for_salon(self, sample_salon_context):
        site = parse_context(sample_salon_context)
        assert site["business_name"] == "Studio Bella Hair"
        assert site["phone"] == "5571999998888"
        assert len(site["services"]) >= 2
        assert site["whatsapp_url"].startswith("https://wa.me/")

    def test_builds_site_data_for_lawyer_with_transcripts(self, sample_lawyer_context):
        site = parse_context(sample_lawyer_context)
        assert site["category_base"] == "Advocacia"
        assert site["profile_style"] == "professional"
        assert site["transcripts_count"] == 2
        assert len(site["gallery"]) == 1
        assert len(site["highlights"]) >= 1
        assert site["display_name"] == "Cleverson Borges"
        assert "criminalista" in site["bio"]
        assert "Senhor Vitor" not in site["about"]
        assert "RISADA" not in site["subheadline"]
        assert site["cta_label"] == "Agendar consulta"
        assert "Direito Criminal" in [s["name"] for s in site["services"]]
        assert len(site["trust_badges"]) >= 2

    def test_does_not_use_meme_caption_as_city(self, sample_lawyer_context):
        site = parse_context(sample_lawyer_context)
        assert "RISADA" not in site.get("city", "")
