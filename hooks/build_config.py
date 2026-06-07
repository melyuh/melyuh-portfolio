"""
MkDocs hook: ビルド時の自動設定

1. Material テーマのパレット CSS 生成（PDF で JS 非実行でも色を反映）
2. Mermaid 配色を accent カラーに連動
3. Copyright に西暦を自動付与
4. to-pdf プラグインの出力パス・カバーロゴ・copyright 設定
5. PDF 内 git プラグインアイコンの fill をインラインスタイルで直接適用
6. PDF 内の画像リンク href を除去してクリック不可にする（pre_pdf_render フック）
7. ライト/ダーク両スキームの PDF を生成し、viewer でスキームに応じて切り替え
"""

import logging
import os
import re

from mkdocs.structure.nav import Section

from _pdf.icon_fill import (
    fix_grid_card_arrow_fill,
    fix_grid_card_icon_fill,
    fix_inline_icon_fill,
    fix_source_file_icon_fill,
)
from _pdf.mermaid import (
    build_mermaid_theme_variables,
    build_mermaid_theme_variables_dark,
    fix_mermaid_pngs_for_page,
    fix_mermaid_svgs,
    generate_mermaid_config_js,
)
from _pdf.palette import (
    DEFAULT_COLOR,
    MATERIAL_COLORS,
    PDF_LOGO_CONFIG,
    build_palette_css,
    make_custom_palette,
)
from _pdf.pdf_render import (
    generate_both_pdfs,
    generate_pdf_styles,
    pre_pdf_render,
    write_if_changed,
)

log = logging.getLogger("mkdocs.hooks.build_config")

# on_config で設定し、on_post_page / on_post_build で参照するモジュールレベル変数
_mermaid_dark_config: dict = {}
_pdf_scheme_global: str = "default"
_schemes_global: list = []
_blog_post_articles: list = []  # ナビゲーション外ブログ記事の PDF 注入用


def on_config(config):
    """theme.palette の primary/accent を読み取り、CSS と mermaid 設定に反映"""

    palette = config["theme"].get("palette", {})
    if isinstance(palette, list):
        entries = palette
    elif isinstance(palette, dict):
        entries = [palette]
    else:
        entries = []

    def _resolve_color(val):
        v = str(val).strip()
        if v.startswith("#"):
            return make_custom_palette(v)
        return MATERIAL_COLORS.get(v.lower().replace(" ", "-"), DEFAULT_COLOR)

    schemes = []
    for entry in entries:
        scheme = str(entry.get("scheme", "default"))
        primary_val = str(entry.get("primary", "indigo")).strip()
        accent_val = str(entry.get("accent", "indigo")).strip()
        primary = _resolve_color(primary_val)
        accent = _resolve_color(accent_val)
        schemes.append((scheme, primary, accent))
        log.info(
            f"Palette [{scheme}]: primary={primary_val} ({primary['main']}), "
            f"accent={accent_val} ({accent['main']})"
        )

    first_accent = schemes[0][2] if schemes else DEFAULT_COLOR
    pdf_scheme = schemes[0][0] if schemes else "default"
    log.info(f"PDF primary scheme: {pdf_scheme}")

    global \
        _mermaid_dark_config, \
        _pdf_scheme_global, \
        _schemes_global, \
        _blog_post_articles
    _pdf_scheme_global = pdf_scheme
    _schemes_global = schemes
    _blog_post_articles = []
    _mermaid_dark_config = {
        "theme": "base",
        "themeVariables": build_mermaid_theme_variables_dark(first_accent),
        "flowchart": {"htmlLabels": False},
        "class": {"htmlLabels": False},
    }

    docs_dir = config["docs_dir"]
    css_dir = os.path.join(docs_dir, "_stylesheets")
    os.makedirs(css_dir, exist_ok=True)
    css_path = os.path.join(css_dir, "_palette.css")
    write_if_changed(css_path, build_palette_css(schemes, pdf_scheme))
    log.info(f"Generated palette CSS: {css_path}")

    project_root = os.path.dirname(docs_dir)
    generate_pdf_styles(os.path.join(project_root, "templates"), pdf_scheme)

    css_ref = "_stylesheets/_palette.css"
    extra_css = config.get("extra_css", [])
    if css_ref not in extra_css:
        extra_css.insert(0, css_ref)

    js_dir = os.path.join(docs_dir, "_javascripts")
    os.makedirs(js_dir, exist_ok=True)
    js_path = os.path.join(js_dir, "_mermaid_config.js")
    write_if_changed(js_path, generate_mermaid_config_js(schemes, DEFAULT_COLOR))
    log.info(f"Generated mermaid config JS: {js_path}")

    js_ref = "_javascripts/_mermaid_config.js"
    extra_js = config.get("extra_javascript", [])
    if js_ref not in extra_js:
        mermaid_idx = next(
            (i for i, x in enumerate(extra_js) if "mermaid" in str(x)), 0
        )
        extra_js.insert(mermaid_idx, js_ref)

    plugins = config.get("plugins", {})

    try:
        plugin = plugins["mermaid-to-svg"]
        mc = plugin.config.get("mermaid_config", {}) or {}
        mc["theme"] = "base"
        mc["themeVariables"] = build_mermaid_theme_variables(first_accent)
        mc.setdefault("flowchart", {})["htmlLabels"] = False
        mc.setdefault("class", {})["htmlLabels"] = False
        plugin.config["mermaid_config"] = mc
        log.info(
            f"mermaid-to-svg config updated: {len(mc['themeVariables'])} variables"
        )
    except (KeyError, TypeError):
        log.debug("mermaid-to-svg plugin not found or disabled")

    from datetime import datetime

    year = datetime.now().year
    raw_copyright = config.get("copyright", "")
    if raw_copyright and str(year) not in raw_copyright:
        config["copyright"] = f"Copyright (C) {year} {raw_copyright}"
    log.info(f"copyright: {config['copyright']}")

    try:
        pdf_plugin = plugins["to-pdf"]
        site_name = config.get("site_name", "docs")
        pdf_plugin.config["output_path"] = f"{site_name}.pdf"

        logo_cfg = PDF_LOGO_CONFIG.get(pdf_scheme, PDF_LOGO_CONFIG["default"])
        cover_logo = logo_cfg["cover_logo"]
        pdf_plugin.config["cover_logo"] = cover_logo
        log.info(f"to-pdf: cover_logo={cover_logo}")

        if hasattr(pdf_plugin, "_options") and pdf_plugin._options is not None:
            pdf_plugin._options._copyright = config["copyright"]
            pdf_plugin._options._cover_logo = cover_logo
            pdf_plugin._options.html_path = "_pdf_source.html"
            pdf_plugin._options.hook.pre_pdf_render = _pre_pdf_render_hook
            log.info(
                "to-pdf: _copyright, _cover_logo, html_path, pre_pdf_render updated"
            )

        log.info(f"to-pdf: output={site_name}.pdf, copyright={config['copyright']}")
    except (KeyError, TypeError, AttributeError):
        log.debug("to-pdf plugin not found or disabled")

    return config


def on_post_page(output, page, config):
    """PDF リンクを viewer HTML 経由で新しいタブに表示し、
    git プラグインアイコンの fill をインラインスタイルで直接適用する"""
    site_name = config.get("site_name", "docs")
    pdf_file = f"{site_name}.pdf"
    viewer_file = f"{site_name}_pdf.html"

    page_dir = os.path.dirname(page.file.dest_path)
    if page_dir:
        viewer_href = os.path.relpath(viewer_file, page_dir).replace(os.sep, "/")
    else:
        viewer_href = viewer_file

    output = re.sub(r"<link[^>]*" + re.escape(pdf_file) + r"[^>]*>", "", output)
    output = re.sub(
        r'href=["\']?[^"\'>\s]*'
        + re.escape(pdf_file)
        + r'["\']?\s*title=["\']?PDF["\']?',
        f'href="{viewer_href}" title="PDF" target="_blank"',
        output,
    )

    pdf_article = getattr(page, "pdf-article", None)
    if pdf_article is not None:
        # navigation.indexes が有効な場合、セクションインデックスページ（dir/index.md）は
        # PDF のセクション見出しと H1 が重複する。H1 を除去して重複を防ぐ。
        if (
            page.file.name == "index"
            and isinstance(page.parent, Section)
            and not page.file.src_path.startswith("blog/")
        ):
            h1 = pdf_article.find("h1")
            if h1:
                h1.decompose()
                # H2〜H6 を1段昇格（H2→H1、H3→H2…）してセクション見出しに正しく接続する
                for level in range(2, 7):
                    for h in pdf_article.find_all(f"h{level}"):
                        h.name = f"h{level - 1}"
                log.info(
                    f"on_post_page: promoted headings in section index: {page.file.src_path}"
                )

        # ブログ一覧ページ（blog/index.md 等）はセクション見出しと H1 が重複し、
        # かつ記事タイトルの H2 に章番号が付く。H1 を除去し H2/H3 を H4 に降格する。
        if page.file.src_path.startswith("blog/") and page.file.name == "index":
            h1 = pdf_article.find("h1")
            if h1:
                h1.decompose()
            for h in pdf_article.find_all(["h2", "h3"]):
                h.name = "h4"
                h["style"] = (
                    "font-size: 1.2em; font-weight: 600; "
                    "text-transform: none; "
                    "margin-top: 0.8em; margin-bottom: 0.2em;"
                )
            log.info(
                f"on_post_page: flattened blog index headings: {page.file.src_path}"
            )

        icon_fill = (
            "rgba(255,255,255,0.54)"
            if _pdf_scheme_global == "slate"
            else "rgba(0,0,0,0.54)"
        )
        fix_source_file_icon_fill(pdf_article, icon_fill)
        text_fill = (
            "rgba(255,255,255,0.82)"
            if _pdf_scheme_global == "slate"
            else "rgba(0,0,0,0.87)"
        )
        fix_inline_icon_fill(pdf_article, text_fill)
        grid_fill = "#1a1a1a" if _pdf_scheme_global == "slate" else "#ffffff"
        fix_grid_card_icon_fill(pdf_article, grid_fill)
        arrow_fill = next(
            (p["main"] for s, p, _ in _schemes_global if s == _pdf_scheme_global),
            "#26C6DA",
        )
        fix_grid_card_arrow_fill(pdf_article, arrow_fill)

    output = fix_mermaid_pngs_for_page(
        output, page, config, _mermaid_dark_config, _pdf_scheme_global
    )

    if page.file.src_path.startswith("blog/posts/"):
        try:
            pdf_plugin = config["plugins"]["to-pdf"]
            if pdf_plugin.enabled:
                from mkdocs_to_pdf.utils.soup_util import clone_element

                gen = pdf_plugin.generator
                article = getattr(page, "pdf-article", None)
                if article:
                    page_path = gen._page_path_for_id(page)
                    section = clone_element(article)
                    section.name = "section"
                    section["id"] = f"{page_path}:"
                    section["data-url"] = f"/{page_path}"
                    _blog_post_articles.append(str(section))
                    log.info(f"on_post_page: blog post collected for PDF: {page_path}")
        except Exception as e:
            log.debug(f"on_post_page: blog post collection skipped: {e}")

    return output


def _pre_pdf_render_hook(html_string: str) -> str:
    """to-pdf の pre_pdf_render フック: モジュール状態を束縛して pre_pdf_render を呼ぶ。"""
    return pre_pdf_render(
        html_string, _pdf_scheme_global, _schemes_global, _blog_post_articles
    )


def on_post_build(config):
    """PDF viewer HTML を生成し、両スキームの PDF を生成する"""
    from urllib.parse import quote

    fix_mermaid_svgs(config["site_dir"])
    generate_both_pdfs(config, _pdf_scheme_global, _schemes_global)

    try:
        site_name = config.get("site_name", "docs")
        site_dir = config["site_dir"]
        default_url = quote(f"{site_name}_default.pdf")
        slate_url = quote(f"{site_name}_slate.pdf")

        viewer_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>{site_name} - PDF</title>
<style>
html, body {{ margin:0; padding:0; height:100%; overflow:hidden; }}
iframe {{ width:100%; height:100%; border:none; }}
</style>
</head>
<body>
<iframe id="pdf-frame" src=""></iframe>
<script>
(function () {{
  var pdfs = {{ default: '{default_url}', slate: '{slate_url}' }};
  var scheme = new URLSearchParams(location.search).get('scheme') || 'default';
  document.getElementById('pdf-frame').src = pdfs[scheme] || pdfs['default'];
}})();
</script>
</body>
</html>"""

        viewer_path = os.path.join(site_dir, f"{site_name}_pdf.html")
        with open(viewer_path, "w", encoding="utf-8") as f:
            f.write(viewer_html)
        log.info(f"PDF viewer: {viewer_path}")
    except Exception:
        log.debug("PDF viewer generation skipped")
