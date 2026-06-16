from __future__ import annotations

import json
from pathlib import Path

from pipeline.generate_demo_html import (
    apply_linktree_template,
    apply_site_template,
    copy_profile_avatar,
    generate_demo,
    netlify_site_slug,
    render_highlights,
    render_links,
    render_services,
    services_labels,
)


class TestRenderServices:
    def test_renders_placeholder_when_empty(self):
        html_out = render_services([])
        assert "service-card" in html_out
        assert "Entre em contato" in html_out

    def test_escapes_html_in_service_name(self):
        html_out = render_services([{"name": "<script>", "price": "R$10"}])
        assert "<script>" not in html_out
        assert "&lt;script&gt;" in html_out


class TestRenderHighlights:
    def test_renders_instagram_link(self):
        html_out = render_highlights(
            [
                {
                    "title": "Post",
                    "excerpt": "Texto",
                    "url": "https://instagram.com/p/x",
                    "date": "2026-06-01",
                    "likes": "10",
                }
            ]
        )
        assert "Ver no Instagram" in html_out


class TestRenderLinks:
    def test_marks_primary_whatsapp_link(self):
        html_out = render_links(
            [
                {
                    "label": "WhatsApp",
                    "url": "https://wa.me/55",
                    "icon": "whatsapp",
                    "style": "primary",
                }
            ]
        )
        assert "link-card" in html_out
        assert "link-card--primary" in html_out


class TestServicesLabels:
    def test_advocacia_uses_areas_label(self):
        eyebrow, title = services_labels("Advocacia")
        assert eyebrow == "Áreas"
        assert "atuação" in title

    def test_creator_uses_o_que_faco(self):
        eyebrow, title = services_labels("Advocacia", "creator")
        assert eyebrow == "Atuação"
        assert title == "O que faço"


class TestNetlifySlug:
    def test_converts_dots_and_underscores(self):
        assert netlify_site_slug("adv.rafaelgarcianunes") == "adv-rafaelgarcianunes"
        assert netlify_site_slug("alanbmarques_advogado") == "alanbmarques-advogado"


class TestApplyTemplates:
    def test_site_template_replaces_editorial_placeholders(self):
        site_data = {
            "business_name": "Teste",
            "display_name": "Maria Silva",
            "category": "Advocacia",
            "category_base": "Advocacia",
            "profile_style": "professional",
            "headline": "Teste",
            "subheadline": "Sub",
            "about": "Sobre",
            "cta_label": "Fale",
            "whatsapp_url": "https://wa.me/55",
            "hero_image": "assets/x.jpg",
            "seo_title": "SEO",
            "seo_description": "Desc",
            "instagram_url": "https://instagram.com/x",
            "username": "x",
            "services": [{"name": "Direito Civil", "price": "Sob consulta"}],
            "highlights": [],
            "gallery": [],
        }
        template = (
            "{{NAV_BRAND}} | {{HERO_EYEBROW}} | {{AREAS_SECTION}} | "
            "{{MANIFESTO_SECTION}} | {{WA_FLOAT_HTML}}"
        )
        rendered = apply_site_template(template, site_data)
        assert "<strong>Maria</strong> Silva" in rendered
        assert "area-card" in rendered
        assert "wa-float" in rendered

    def test_linktree_renders_multiline_bio(self):
        site_data = {
            "business_name": "Teste",
            "bio": "Linha 1\nLinha 2",
            "category": "Advocacia",
            "avatar_image": "assets/a.jpg",
            "seo_description": "Desc",
            "instagram_url": "https://instagram.com/x",
            "username": "x",
            "links": [],
        }
        template = "{{BIO}}"
        rendered = apply_linktree_template(template, site_data, site_demo_path="site/index.html")
        assert "Linha 1\nLinha 2" in rendered

    def test_linktree_includes_theme_toggle(self):
        site_data = {
            "business_name": "Teste",
            "bio": "Bio",
            "category": "Advocacia",
            "profile_style": "professional",
            "avatar_image": "assets/a.jpg",
            "seo_description": "Desc",
            "instagram_url": "https://instagram.com/x",
            "username": "x",
            "links": [],
        }
        template_path = Path(__file__).resolve().parents[1] / "templates" / "linktree-demo" / "index.html"
        rendered = apply_linktree_template(
            template_path.read_text(encoding="utf-8"),
            site_data,
            site_demo_path="site/index.html",
        )
        assert 'class="theme-toggle"' in rendered
        assert 'localStorage.getItem("linktree-theme")' in rendered

    def test_ver_site_completo_opens_new_tab(self):
        html_out = render_links(
            [
                {
                    "label": "Ver site completo",
                    "url": "site/index.html",
                    "icon": "globe",
                    "subtitle": "Página profissional",
                }
            ]
        )
        assert 'href="site/index.html"' in html_out
        assert 'target="_blank"' in html_out
        assert 'rel="noopener"' in html_out

    def test_linktree_rewrites_site_path(self):
        site_data = {
            "business_name": "Teste",
            "bio": "Bio",
            "category": "Advocacia",
            "avatar_image": "assets/a.jpg",
            "seo_description": "Desc",
            "instagram_url": "https://instagram.com/x",
            "username": "x",
            "links": [{"label": "Ver site completo", "url": "../demo/index.html", "icon": "globe"}],
        }
        template = "{{LINKS_HTML}}"
        rendered = apply_linktree_template(template, site_data, site_demo_path="site/index.html")
        assert "site/index.html" in rendered


class TestGenerateDemo:
    def test_generates_publish_bundle(self, tmp_path: Path, sample_lawyer_context):
        output = tmp_path / "lawyer"
        output.mkdir()
        media = output / "media"
        media.mkdir()

        (media / "profile_pic.jpg").write_bytes(b"fake")
        (media / "thumb.jpg").write_bytes(b"fake")

        site_data = __import__("pipeline.parse_context", fromlist=["parse_context"]).parse_context(
            sample_lawyer_context
        )
        (output / "site_data.json").write_text(json.dumps(site_data), encoding="utf-8")

        result = generate_demo(output)
        assert (result["publish"] / "index.html").exists()
        assert (result["publish"] / "site" / "index.html").exists()
        assert (result["linktree"] / "index.html").exists()
        assert (result["site"] / "index.html").exists()

        publish_html = (result["publish"] / "site" / "index.html").read_text(encoding="utf-8")
        assert "Cleverson Borges" in publish_html
        assert "editorial-site" in publish_html
        assert "area-card" in publish_html
        assert "Onde atuo" in publish_html
        assert 'href="styles.css"' in publish_html
        assert 'href="editorial.css"' in publish_html
        assert len(list((result["publish"] / "site" / "assets").glob("*_thumb.jpg"))) >= 0
        assert len(list((result["publish"] / "site" / "assets").glob("thumb.jpg"))) == 1

        linktree_html = (result["publish"] / "index.html").read_text(encoding="utf-8")
        assert 'href="styles.css"' in linktree_html
        assert (result["publish"] / "favicon.svg").exists()
        assert (result["publish"] / "site" / "favicon.svg").exists()
        assert 'href="favicon.svg"' in publish_html

    def test_linktree_avatar_uses_profile_pic(self, tmp_path: Path, sample_lawyer_context):
        output = tmp_path / "lawyer"
        output.mkdir()
        media = output / "media"
        assets = output / "assets"
        media.mkdir()
        assets.mkdir()

        profile_bytes = b"PROFILE_PIC_UNIQUE_BYTES"
        thumb_bytes = b"THUMB_DIFFERENT_BYTES"
        (media / "profile_pic.jpg").write_bytes(profile_bytes)
        (media / "thumb.jpg").write_bytes(thumb_bytes)

        site_data = __import__("pipeline.parse_context", fromlist=["parse_context"]).parse_context(
            sample_lawyer_context
        )
        (output / "site_data.json").write_text(json.dumps(site_data), encoding="utf-8")

        assert copy_profile_avatar(media, assets) is True
        assert (assets / "avatar.jpg").read_bytes() == profile_bytes

        result = generate_demo(output)
        assert (result["publish"] / "assets" / "avatar.jpg").read_bytes() == profile_bytes
        assert (result["linktree"] / "assets" / "avatar.jpg").read_bytes() == profile_bytes

        linktree_html = (result["publish"] / "index.html").read_text(encoding="utf-8")
        assert 'src="assets/avatar.jpg"' in linktree_html

    def test_publish_uses_absolute_og_image(self, tmp_path: Path, sample_lawyer_context):
        output = tmp_path / "lawyer"
        output.mkdir()
        media = output / "media"
        media.mkdir()
        (media / "profile_pic.jpg").write_bytes(b"fake")
        (media / "thumb.jpg").write_bytes(b"fake")

        site_data = __import__("pipeline.parse_context", fromlist=["parse_context"]).parse_context(
            sample_lawyer_context
        )
        site_data["username"] = "cleversonborges.adv"
        site_data["publish_url"] = "https://cleversonborges-adv.netlify.app"
        (output / "site_data.json").write_text(json.dumps(site_data), encoding="utf-8")

        result = generate_demo(output)
        linktree_html = (result["publish"] / "index.html").read_text(encoding="utf-8")
        site_html = (result["publish"] / "site" / "index.html").read_text(encoding="utf-8")

        assert (
            'property="og:image" content="https://cleversonborges-adv.netlify.app/assets/og-cleversonborges-adv.jpg"'
            in linktree_html
        )
        assert (
            'property="og:url" content="https://cleversonborges-adv.netlify.app"' in linktree_html
        )
        assert (
            'property="og:image" content="https://cleversonborges-adv.netlify.app/site/assets/og-cleversonborges-adv.jpg"'
            in site_html
        )
        assert (result["publish"] / "assets" / "og-cleversonborges-adv.jpg").exists()
