"""
MkDocs hook: ビルド時の自動設定

1. Material テーマのパレット CSS 生成（PDF で JS 非実行でも色を反映）
2. Mermaid 配色を accent カラーに連動
3. Copyright に西暦を自動付与
4. to-pdf プラグインの出力パス・copyright 設定
5. PDF リンクをブラウザ内表示に変更
"""

import logging
import os

log = logging.getLogger("mkdocs.hooks.build_config")

MATERIAL_COLORS = {
    "red": {
        "main": "#f44336",
        "light": "#ffcdd2",
        "vlight": "#ffebee",
        "dark": "#c62828",
    },
    "pink": {
        "main": "#e91e63",
        "light": "#f8bbd0",
        "vlight": "#fce4ec",
        "dark": "#c2185b",
    },
    "purple": {
        "main": "#9c27b0",
        "light": "#e1bee7",
        "vlight": "#f3e5f5",
        "dark": "#7b1fa2",
    },
    "deep-purple": {
        "main": "#673ab7",
        "light": "#d1c4e9",
        "vlight": "#ede7f6",
        "dark": "#4527a0",
    },
    "indigo": {
        "main": "#3f51b5",
        "light": "#c5cae9",
        "vlight": "#e8eaf6",
        "dark": "#283593",
    },
    "blue": {
        "main": "#2196f3",
        "light": "#bbdefb",
        "vlight": "#e3f2fd",
        "dark": "#1565c0",
    },
    "light-blue": {
        "main": "#03a9f4",
        "light": "#b3e5fc",
        "vlight": "#e1f5fe",
        "dark": "#0277bd",
    },
    "cyan": {
        "main": "#00bcd4",
        "light": "#b2ebf2",
        "vlight": "#e0f7fa",
        "dark": "#00838f",
    },
    "teal": {
        "main": "#009688",
        "light": "#b2dfdb",
        "vlight": "#e0f2f1",
        "dark": "#00796b",
    },
    "green": {
        "main": "#4caf50",
        "light": "#c8e6c9",
        "vlight": "#e8f5e9",
        "dark": "#2e7d32",
    },
    "light-green": {
        "main": "#8bc34a",
        "light": "#dcedc8",
        "vlight": "#f1f8e9",
        "dark": "#558b2f",
    },
    "lime": {
        "main": "#cddc39",
        "light": "#f0f4c3",
        "vlight": "#f9fbe7",
        "dark": "#9e9d24",
    },
    "yellow": {
        "main": "#ffeb3b",
        "light": "#fff9c4",
        "vlight": "#fffde7",
        "dark": "#f9a825",
    },
    "amber": {
        "main": "#ffc107",
        "light": "#ffecb3",
        "vlight": "#fff8e1",
        "dark": "#ff8f00",
    },
    "orange": {
        "main": "#ff9800",
        "light": "#ffe0b2",
        "vlight": "#fff3e0",
        "dark": "#e65100",
    },
    "deep-orange": {
        "main": "#ff5722",
        "light": "#ffccbc",
        "vlight": "#fbe9e7",
        "dark": "#d84315",
    },
    "brown": {
        "main": "#795548",
        "light": "#d7ccc8",
        "vlight": "#efebe9",
        "dark": "#4e342e",
    },
    "grey": {
        "main": "#9e9e9e",
        "light": "#e0e0e0",
        "vlight": "#fafafa",
        "dark": "#424242",
    },
    "blue-grey": {
        "main": "#607d8b",
        "light": "#cfd8dc",
        "vlight": "#eceff1",
        "dark": "#37474f",
    },
    "black": {
        "main": "#000000",
        "light": "#bdbdbd",
        "vlight": "#e0e0e0",
        "dark": "#000000",
    },
    "white": {
        "main": "#ffffff",
        "light": "#ffffff",
        "vlight": "#ffffff",
        "dark": "#bdbdbd",
    },
}

DEFAULT_COLOR = MATERIAL_COLORS["indigo"]

# ──────────────────────────────────────────────
#  カスタムカラー（ここを変えるだけで全体に反映）
# ──────────────────────────────────────────────
CUSTOM_COLOR = "#0288D1"


# ──────────────────────────────────────────────
#  ユーティリティ
# ──────────────────────────────────────────────
def _hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _is_dark(hex_color):
    r, g, b = _hex_to_rgb(hex_color)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 < 0.5


def _text_on(bg):
    return "#ffffff" if _is_dark(bg) else "#1a1a1a"


def _rgba(hex_color, alpha):
    r, g, b = _hex_to_rgb(hex_color)
    return f"rgba({r},{g},{b},{alpha})"


def _blend_white(hex_color, factor):
    """hex_color を白に向けて factor (0–1) だけ近づける"""
    r, g, b = _hex_to_rgb(hex_color)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _blend_black(hex_color, factor):
    """hex_color を黒に向けて factor (0–1) だけ近づける"""
    r, g, b = _hex_to_rgb(hex_color)
    return f"#{int(r*(1-factor)):02x}{int(g*(1-factor)):02x}{int(b*(1-factor)):02x}"


def _make_custom_palette(color):
    return {
        "main":   color,
        "light":  _blend_white(color, 0.4),
        "vlight": _blend_white(color, 0.82),
        "dark":   _blend_black(color, 0.1),
    }


MATERIAL_COLORS["custom"] = _make_custom_palette(CUSTOM_COLOR)


# ──────────────────────────────────────────────
#  1. パレット CSS（PDF 用 — JS 非実行でも色を適用）
# ──────────────────────────────────────────────
def _build_palette_css(primary, accent):
    """Material テーマの CSS 変数を明示的に設定する CSS を生成"""
    primary_bg = "#fff" if _is_dark(primary["main"]) else "#000"
    accent_bg = "#fff" if _is_dark(accent["main"]) else "#000"

    return f"""\
/* Auto-generated by hooks/build_config.py — DO NOT EDIT */
:root {{
  --md-primary-fg-color:             {primary["main"]};
  --md-primary-fg-color--light:      {primary["light"]};
  --md-primary-fg-color--dark:       {primary["dark"]};
  --md-primary-bg-color:             {primary_bg};
  --md-primary-bg-color--light:      {primary_bg}99;
  --md-accent-fg-color:              {accent["main"]};
  --md-accent-fg-color--transparent: {accent["main"]}10;
  --md-accent-bg-color:              {accent_bg};
}}
[data-md-color-scheme="slate"] {{
  --md-default-h-color: {primary["vlight"]};
}}
"""


# ──────────────────────────────────────────────
#  2. Mermaid 配色（accent のみ使用）
# ──────────────────────────────────────────────
def _build_mermaid_theme_variables(accent):
    """accent カラーのみで Mermaid の配色を構築"""
    return {
        "background": "#ffffff",
        "titleColor": "#1a1a1a",
        "primaryColor": accent["vlight"],
        "primaryTextColor": _text_on(accent["vlight"]),
        "primaryBorderColor": accent["main"],
        "secondaryColor": accent["vlight"],
        "secondaryTextColor": _text_on(accent["vlight"]),
        "secondaryBorderColor": accent["main"],
        "tertiaryColor": "#f5f5f5",
        "tertiaryTextColor": "#1a1a1a",
        "tertiaryBorderColor": "#bdbdbd",
        "lineColor": accent["main"],
        "arrowheadColor": accent["main"],
        "mainBkg": accent["vlight"],
        "nodeBorder": accent["main"],
        "clusterBkg": accent["vlight"],
        "clusterBorder": accent["main"],
        "edgeLabelBackground": "#ffffff",
        "actorBkg": accent["vlight"],
        "actorBorder": accent["main"],
        "actorTextColor": _text_on(accent["vlight"]),
        "actorLineColor": accent["light"],
        "signalColor": accent["main"],
        "signalTextColor": "#37474f",
        "activationBkgColor": accent["light"],
        "activationBorderColor": accent["main"],
        "labelBoxBkgColor": "#ffffff",
        "labelBoxBorderColor": accent["main"],
        "labelTextColor": "#1a1a1a",
        "loopTextColor": "#37474f",
        "sequenceNumberColor": _text_on(accent["main"]),
        "noteBkgColor": "#fff9c4",
        "noteTextColor": "#1a1a1a",
        "noteBorderColor": accent["main"],
        "sectionBkgColor": _rgba(accent["main"], 0.08),
        "sectionBkgColor2": _rgba(accent["main"], 0.04),
        "taskBkgColor": accent["main"],
        "taskTextColor": _text_on(accent["main"]),
        "taskBorderColor": accent["dark"],
        "activeTaskBkgColor": accent["light"],
        "activeTaskBorderColor": accent["main"],
        "doneTaskBkgColor": "#cfd8dc",
        "doneTaskBorderColor": "#90a4ae",
        "critBkgColor": "#ef5350",
        "critBorderColor": "#c62828",
        "todayLineColor": accent["main"],
    }


# ──────────────────────────────────────────────
#  Hook エントリポイント
# ──────────────────────────────────────────────
def on_config(config):
    """theme.palette の primary/accent を読み取り、CSS と mermaid 設定に反映"""

    # --- palette から primary / accent を取得 ---
    palette = config["theme"].get("palette", {})

    if isinstance(palette, list) and len(palette) > 0:
        entry = palette[0]
    elif isinstance(palette, dict):
        entry = palette
    else:
        entry = {}

    primary_name = str(entry.get("primary", "indigo")).lower().strip().replace(" ", "-")
    accent_name = str(entry.get("accent", "indigo")).lower().strip().replace(" ", "-")

    primary = MATERIAL_COLORS.get(primary_name, DEFAULT_COLOR)
    accent = MATERIAL_COLORS.get(accent_name, DEFAULT_COLOR)

    log.info(
        f"Palette: primary={primary_name} ({primary['main']}), "
        f"accent={accent_name} ({accent['main']})"
    )

    # --- パレット CSS を生成 ---
    docs_dir = config["docs_dir"]
    css_dir = os.path.join(docs_dir, "stylesheets")
    os.makedirs(css_dir, exist_ok=True)
    css_path = os.path.join(css_dir, "_palette.css")

    css_content = _build_palette_css(primary, accent)
    existing = ""
    if os.path.exists(css_path):
        with open(css_path, encoding="utf-8") as f:
            existing = f.read()
    if existing != css_content:
        with open(css_path, "w", encoding="utf-8") as f:
            f.write(css_content)
    log.info(f"Generated palette CSS: {css_path}")

    # extra_css の先頭に追加（Material デフォルトを上書き）
    css_ref = "stylesheets/_palette.css"
    extra_css = config.get("extra_css", [])
    if css_ref not in extra_css:
        extra_css.insert(0, css_ref)

    # --- mermaid-to-svg プラグインに反映（accent のみ） ---
    try:
        plugins = config.get("plugins", {})
        plugin = plugins["mermaid-to-svg"]
        mc = plugin.config.get("mermaid_config", {}) or {}
        mc["theme"] = "base"
        mc["themeVariables"] = _build_mermaid_theme_variables(accent)
        mc.setdefault("flowchart", {})["htmlLabels"] = False
        mc.setdefault("class", {})["htmlLabels"] = False
        plugin.config["mermaid_config"] = mc
        log.info(
            f"mermaid-to-svg config updated: {len(mc['themeVariables'])} variables"
        )
    except (KeyError, TypeError):
        log.debug("mermaid-to-svg plugin not found or disabled")

    # --- copyright に西暦を動的に付与 ---
    from datetime import datetime

    year = datetime.now().year
    raw_copyright = config.get("copyright", "")
    if raw_copyright and str(year) not in raw_copyright:
        config["copyright"] = f"Copyright (C) {year} {raw_copyright}"
    log.info(f"copyright: {config['copyright']}")

    # --- to-pdf プラグインの動的設定 ---
    try:
        plugins = config.get("plugins", {})
        pdf_plugin = plugins["to-pdf"]

        # output_path を <site_name>.pdf にする
        site_name = config.get("site_name", "docs")
        pdf_plugin.config["output_path"] = f"{site_name}.pdf"

        # Options は既に作成済み → 内部変数を直接書き換える
        if hasattr(pdf_plugin, "_options") and pdf_plugin._options is not None:
            pdf_plugin._options._copyright = config["copyright"]
            log.info("to-pdf: _copyright updated directly")

        log.info(f"to-pdf: output={site_name}.pdf, copyright={config['copyright']}")
    except (KeyError, TypeError, AttributeError):
        log.debug("to-pdf plugin not found or disabled")

    return config


def on_post_page(output, page, config):
    """PDF リンクを viewer HTML 経由で新しいタブに表示"""
    import re

    site_name = config.get("site_name", "docs")
    pdf_file = f"{site_name}.pdf"
    viewer_file = f"{site_name}_pdf.html"

    # <link rel="alternate" ... pdf ...> を除去（ダウンロード誘発防止）
    output = re.sub(r"<link[^>]*" + re.escape(pdf_file) + r"[^>]*>", "", output)

    # PDF アイコンの href を viewer に変更 + target="_blank"
    output = re.sub(
        r'href=["\']?[^"\'>\s]*'
        + re.escape(pdf_file)
        + r'["\']?\s*title=["\']?PDF["\']?',
        f'href="{viewer_file}" title="PDF" target="_blank"',
        output,
    )

    return output


def on_post_build(config):
    """PDF viewer HTML を生成（blob URL で確実にブラウザ内表示）"""
    try:
        site_name = config.get("site_name", "docs")
        pdf_file = f"{site_name}.pdf"
        site_dir = config["site_dir"]

        viewer_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>{site_name} - PDF</title>
<style>
html, body {{ margin:0; padding:0; height:100%; overflow:hidden; }}
iframe {{ width:100%; height:100%; border:none; }}
#loading {{
    display:flex; justify-content:center; align-items:center;
    height:100%; font-family:sans-serif; color:#666; font-size:1.2em;
}}
</style>
</head>
<body>
<div id="loading">PDF を読み込み中...</div>
<iframe id="pdf" style="display:none"></iframe>
<script>
fetch("{pdf_file}")
  .then(function(r) {{ return r.blob(); }})
  .then(function(blob) {{
    var url = URL.createObjectURL(new Blob([blob], {{type:"application/pdf"}}));
    var iframe = document.getElementById("pdf");
    iframe.src = url;
    iframe.style.display = "block";
    document.getElementById("loading").style.display = "none";
  }})
  .catch(function() {{
    document.getElementById("loading").textContent = "PDF の読み込みに失敗しました";
  }});
</script>
</body>
</html>"""

        viewer_path = os.path.join(site_dir, f"{site_name}_pdf.html")
        with open(viewer_path, "w", encoding="utf-8") as f:
            f.write(viewer_html)
        log.info(f"PDF viewer: {viewer_path}")
    except Exception:
        log.debug("PDF viewer generation skipped")
