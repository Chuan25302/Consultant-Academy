"""
Smoke tests for tools/build_site.py — exercises template rendering + slug
helpers without needing Drive auth. Uses synthetic Posts so we can run
this on every PR (CI doesn't have Drive credentials).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.build_site import Post, is_meaningful_cluster, render_site, slugify


# ---------- slug helper -----------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Pumps", "pumps"),
    ("Heat Exchangers", "heat-exchangers"),
    ("M&A Diligence", "m-a-diligence"),
    ("HVAC-Chillers", "hvac-chillers"),
    ("  spacey   value  ", "spacey-value"),
    ("", "general"),
])
def test_slugify_ascii(text, expected):
    assert slugify(text) == expected


@pytest.mark.parametrize("name,expected", [
    ("Pumps & Compressors", True),
    ("Carbon Accounting", True),
    ("ปั๊มหอยโข่ง", True),
    ("General", False),        # default bucket — not a curated topic
    ("1", False),              # calendar typo: numeric value
    ("23", False),
    ("", False),
    (" ", False),
    ("A", False),              # too short to be a meaningful label
])
def test_is_meaningful_cluster(name, expected):
    assert is_meaningful_cluster(name) is expected


def test_render_skips_junk_cluster_page(tmp_path):
    """A post with cluster='1' (calendar typo) must NOT generate a
    /clusters/1/ page, and the chip on the post must be hidden so
    readers don't see a useless '🎯 1' link."""
    posts = [
        Post(date="2026-05-12", title="Sample", pillar="TECHNICAL",
             cluster="1", level=1, industry="General", keywords=[],
             body_html='<div class="wrap"><div class="bd"><p>body</p></div></div>',
             tldr="x"),
    ]
    out = tmp_path / "docs"
    render_site(posts, out)
    assert not (out / "clusters" / "1" / "index.html").exists()
    post_html = (out / "posts" / "2026" / "05" / "12" / "index.html").read_text("utf-8")
    # The chip would link to /clusters/1/ if rendered — confirm it's not there
    assert 'clusters/1/' not in post_html
    assert "🎯 1" not in post_html


def test_slugify_thai_falls_back_to_hash():
    """All-Thai cluster names route to a stable hash slug so they're
    still individually addressable on the site."""
    slug_a = slugify("ปั๊มหอยโข่ง")
    slug_b = slugify("ปั๊มหอยโข่ง")
    slug_c = slugify("หม้อแปลงไฟฟ้า")
    assert slug_a.startswith("c-")
    assert slug_a == slug_b           # deterministic
    assert slug_a != slug_c           # distinguishable


# ---------- end-to-end render ----------------------------------------------

def _sample_posts() -> list[Post]:
    """Three synthetic posts across two clusters + three levels — enough
    to populate every section of the site (homepage cards, archive,
    pillar, cluster, post)."""
    body = (
        '<div class="wrap"><div class="bd">'
        '<p>นี่คือบทความตัวอย่างสำหรับ smoke test ของ build pipeline.</p>'
        '<h2>หัวข้อย่อย</h2><p>เนื้อหาต่อ...</p>'
        '</div></div>'
    )
    return [
        Post(date="2026-05-12", title="ทำความรู้จักปั๊มหอยโข่ง",
             pillar="TECHNICAL", cluster="Pumps", level=1,
             industry="Refining", keywords=["pump", "centrifugal"],
             body_html=body,
             tldr="แนะนำหลักการทำงานของปั๊มหอยโข่งฉบับเริ่มต้น"),
        Post(date="2026-05-13", title="วิเคราะห์ Pump Curve ขั้นกลาง",
             pillar="TECHNICAL", cluster="Pumps", level=2,
             industry="Refining", keywords=["pump", "curve"],
             body_html=body,
             tldr="อ่าน pump curve เป็น แล้วใช้เลือก operating point"),
        Post(date="2026-05-14", title="กรอบ MECE ในการ Diagnose โรงงาน",
             pillar="FRAMEWORK", cluster="Diagnostic", level=1,
             industry="General", keywords=["mece"],
             body_html=body,
             tldr="แนะนำการคิดแบบ MECE"),
    ]


def test_render_site_produces_expected_files(tmp_path):
    posts = _sample_posts()
    out = tmp_path / "docs"
    render_site(posts, out)

    must_exist = [
        "index.html",
        "assets/style.css",
        ".nojekyll",
        "archive/index.html",
        "archive/2026/index.html",
        "archive/2026/05/index.html",
        "pillars/index.html",
        "pillars/technical/index.html",
        "pillars/framework/index.html",
        "clusters/index.html",
        "clusters/pumps/index.html",
        "clusters/diagnostic/index.html",
        "posts/2026/05/12/index.html",
        "posts/2026/05/13/index.html",
        "posts/2026/05/14/index.html",
    ]
    for rel in must_exist:
        assert (out / rel).exists(), f"missing file: {rel}"


def test_post_page_includes_body_and_related(tmp_path):
    posts = _sample_posts()
    render_site(posts, tmp_path / "docs")
    post_html = (tmp_path / "docs" / "posts" / "2026" / "05" / "12" / "index.html").read_text("utf-8")
    # Body of the embedded email is preserved
    assert "ปั๊มหอยโข่ง" in post_html
    # Related sidebar appears, showing the sibling pump post
    assert "Pump Curve" in post_html
    # MECE post is in a different cluster — must NOT appear as related
    assert "MECE" not in post_html
    # Breadcrumb back to pillar
    assert 'pillars/technical/' in post_html


def test_cluster_page_shows_learning_path(tmp_path):
    posts = _sample_posts()
    render_site(posts, tmp_path / "docs")
    cluster_html = (tmp_path / "docs" / "clusters" / "pumps" / "index.html").read_text("utf-8")
    # Learning path block surfaces L1 and L2 counts
    assert "learn-path" in cluster_html
    assert "L1" in cluster_html
    assert "L2" in cluster_html


def test_homepage_shows_hero_and_pillars(tmp_path):
    posts = _sample_posts()
    render_site(posts, tmp_path / "docs")
    home = (tmp_path / "docs" / "index.html").read_text("utf-8")
    assert "Consultant Academy" in home
    assert "บทความล่าสุด" in home
    # CTA points at newest post
    assert 'posts/2026/05/14/' in home


def test_card_link_is_relative(tmp_path):
    """Cards must use relative URLs so the same docs/ output works under
    any base path (e.g. github.io/Consultant-Academy/)."""
    posts = _sample_posts()
    render_site(posts, tmp_path / "docs")
    home = (tmp_path / "docs" / "index.html").read_text("utf-8")
    # Relative link, never absolute
    assert 'href="posts/2026/05/' in home
    assert 'href="/posts/' not in home  # absolute path would break under a subpath
