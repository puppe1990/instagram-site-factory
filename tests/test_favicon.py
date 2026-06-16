from __future__ import annotations

from pathlib import Path

from pipeline.lib.favicon import build_favicon_svg, icon_name_for_category, write_favicon


class TestFavicon:
    def test_advocacia_uses_scale_icon(self):
        assert icon_name_for_category("Advocacia") == "scale"

    def test_builds_valid_svg(self):
        svg = build_favicon_svg("Advocacia", variant="site")
        assert svg.startswith('<?xml version="1.0"')
        assert "<svg" in svg
        assert 'stroke="#c9a227"' in svg
        assert "M12 3v18" in svg

    def test_linktree_theme(self):
        svg = build_favicon_svg("Advocacia", variant="linktree")
        assert 'fill="#15110f"' in svg
        assert 'stroke="#e07a5f"' in svg

    def test_writes_file(self, tmp_path: Path):
        path = write_favicon(tmp_path, "Salão de Beleza", variant="site")
        assert path.name == "favicon.svg"
        content = path.read_text(encoding="utf-8")
        assert "scissors" not in content
        assert "<path" in content