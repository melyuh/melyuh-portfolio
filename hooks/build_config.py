"""
MkDocs hook: ビルド時の自動設定

1. Material テーマのパレット CSS 生成（PDF で JS 非実行でも色を反映）
2. Mermaid 配色を accent カラーに連動
3. Copyright に西暦を自動付与
4. to-pdf プラグインの出力パス・カバーロゴ・copyright 設定
5. PDF 内 git プラグインアイコンの fill をインラインスタイルで直接適用
6. PDF viewer HTML を生成し、PDF アイコンのリンクを viewer に変更

環境変数:
  PDF_SCHEME  PDF に適用するカラースキーム ("default" または "slate"、デフォルト: "default")
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

# PDF_SCHEME ごとのカバーロゴと、コンテンツ内で非表示にする img クラス
_PDF_LOGO_CONFIG = {
    "default": {
        "cover_logo": "assets/melyuh_lightmode.png",
        "hide_class": "logo-dark",   # ライト背景なので暗いロゴは不要
    },
    "slate": {
        "cover_logo": "assets/melyuh_darkmode.png",
        "hide_class": "logo-light",  # 暗い背景なので明るいロゴは不要
    },
}


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


def _rgb_to_hsl(r, g, b):
    r, g, b = r / 255, g / 255, b / 255
    hi, lo = max(r, g, b), min(r, g, b)
    l = (hi + lo) / 2
    if hi == lo:
        return 0.0, 0.0, l
    d = hi - lo
    s = d / (2 - hi - lo) if l > 0.5 else d / (hi + lo)
    if hi == r:
        h = (g - b) / d % 6
    elif hi == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h / 6, s, l


def _hsl_to_hex(h, s, l):
    if s == 0:
        v = round(l * 255)
        return f"#{v:02x}{v:02x}{v:02x}"
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q

    def _f(t):
        t %= 1
        if t < 1 / 6: return p + (q - p) * 6 * t
        if t < 0.5:   return q
        if t < 2 / 3: return p + (q - p) * (2 / 3 - t) * 6
        return p

    def _c(v):
        return min(round(v * 255), 255)
    return f"#{_c(_f(h+1/3)):02x}{_c(_f(h)):02x}{_c(_f(h-1/3)):02x}"


def _heading_color(hex_color, is_dark):
    """primary の色相だけ継承し、スキームの明暗に応じた読みやすい見出し色を返す。
    彩度は 25% に上限を設け、明度は固定（ダーク=94% / ライト=18%）。"""
    r, g, b = _hex_to_rgb(hex_color)
    h, s, _ = _rgb_to_hsl(r, g, b)
    return _hsl_to_hex(h, min(s, 0.25), 0.94 if is_dark else 0.18)


def _make_custom_palette(color):
    return {
        "main":   color,
        "light":  _blend_white(color, 0.4),
        "vlight": _blend_white(color, 0.82),
        "dark":   _blend_black(color, 0.1),
    }


# ──────────────────────────────────────────────
#  1. パレット CSS（PDF 用 — JS 非実行でも色を適用）
# ──────────────────────────────────────────────
def _build_palette_css(schemes, pdf_scheme="default"):
    """schemes: list of (scheme_name, primary_palette, accent_palette)
    pdf_scheme: PDF に適用するスキーム名 ("default" または "slate")
    """
    lines = ["/* Auto-generated by hooks/build_config.py — DO NOT EDIT */"]

    for scheme, primary, accent in schemes:
        sel = f'[data-md-color-scheme="{scheme}"]'
        is_dark = scheme == "slate"  # Material の暗いスキームは slate のみ
        p_bg = "#fff" if _is_dark(primary["main"]) else "#000"
        a_bg = "#fff" if _is_dark(accent["main"]) else "#000"

        lines.append(f"""{sel} {{
  --md-primary-fg-color:             {primary["main"]};
  --md-primary-fg-color--light:      {primary["light"]};
  --md-primary-fg-color--dark:       {primary["dark"]};
  --md-primary-bg-color:             {p_bg};
  --md-primary-bg-color--light:      {p_bg}99;
  --md-accent-fg-color:              {accent["main"]};
  --md-accent-fg-color--transparent: {accent["main"]}10;
  --md-accent-bg-color:              {a_bg};
  --md-default-h-color:              {_heading_color(primary["main"], is_dark)};
}}""")

    # WeasyPrint は JS を実行しないため data-md-color-scheme 属性がセットされず、
    # 上記セレクタの CSS 変数が一切適用されない。
    # @media print で :root に直接変数を展開して確実に反映させる。
    # pdf_scheme に一致するエントリを優先し、なければ先頭を使用。
    print_entry = next(
        (e for e in schemes if e[0] == pdf_scheme),
        schemes[0] if schemes else None,
    )
    if print_entry:
        p_scheme, p_primary, p_accent = print_entry
        is_dark = p_scheme == "slate"

        if is_dark:
            bg           = "hsla(232,15%,21%,1)"
            bg_light     = "hsla(232,15%,25%,1)"
            bg_lighter   = "hsla(232,15%,28%,1)"
            bg_lightest  = "hsla(232,15%,32%,1)"
            fg           = "hsla(0,0%,100%,.87)"
            fg_light     = "hsla(0,0%,100%,.54)"
            fg_lighter   = "hsla(0,0%,100%,.32)"
            fg_lightest  = "hsla(0,0%,100%,.12)"
            code_fg      = "hsla(0,0%,100%,.87)"
            code_bg      = "hsla(200,15%,14%,1)"
        else:
            bg           = "#ffffff"
            bg_light     = "hsla(0,0%,96%,1)"
            bg_lighter   = "hsla(0,0%,98%,1)"
            bg_lightest  = "hsla(0,0%,100%,1)"
            fg           = "hsla(0,0%,0%,.87)"
            fg_light     = "hsla(0,0%,0%,.54)"
            fg_lighter   = "hsla(0,0%,0%,.32)"
            fg_lightest  = "hsla(0,0%,0%,.12)"
            code_fg      = "hsla(200,18%,26%,1)"
            code_bg      = "hsla(0,0%,96%,1)"

        h_color = _heading_color(p_primary["main"], is_dark)
        logo_cfg = _PDF_LOGO_CONFIG.get(p_scheme, _PDF_LOGO_CONFIG["default"])
        hide_logo_class = logo_cfg["hide_class"]

        lines.append(f"""@media print {{
  :root {{
    --md-primary-fg-color:             {p_primary["main"]};
    --md-primary-fg-color--light:      {p_primary["light"]};
    --md-primary-fg-color--dark:       {p_primary["dark"]};
    --md-accent-fg-color:              {p_accent["main"]};
    --md-accent-fg-color--transparent: {p_accent["main"]}10;
    --md-default-bg-color:             {bg};
    --md-default-bg-color--light:      {bg_light};
    --md-default-bg-color--lighter:    {bg_lighter};
    --md-default-bg-color--lightest:   {bg_lightest};
    --md-default-fg-color:             {fg};
    --md-default-fg-color--light:      {fg_light};
    --md-default-fg-color--lighter:    {fg_lighter};
    --md-default-fg-color--lightest:   {fg_lightest};
    --md-code-fg-color:                {code_fg};
    --md-code-bg-color:                {code_bg};
    --md-default-h-color:              {h_color};
    --md-typeset-color:                {fg};
    --md-typeset-a-color:              {p_primary["main"]};
    --md-docomo-red:                   #CC0033;
  }}
  /* @page でページ全域（マージン含む）の背景色を指定。
     CSS 変数は @page 内で解決されない場合があるため実値を直接記述する。 */
  @page {{
    background-color: {bg};
  }}
  body {{
    background-color: {bg} !important;
    color: {fg} !important;
  }}
  /* スキーム ({p_scheme}) に対応しないロゴを非表示 */
  .md-logo img.{hide_logo_class} {{ display: none !important; }}
}}""")

    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────
#  2. Mermaid 配色（accent のみ使用）
# ──────────────────────────────────────────────
def _build_mermaid_theme_variables(accent):
    """accent カラーのみで Mermaid の配色を構築"""
    return {
        "background": "transparent",
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
#  3. PDF カスタムスタイル（custom_template_path/styles.scss）
#     to-pdf は report-print.scss → cover.scss → styles.scss の順でコンパイルし
#     最後に <style> として追記するため、!important なしで他の CSS より優先される。
#
#     SVG アイコンの fill は WeasyPrint で CSS カスケードが効かないため、
#     on_post_page フックで BeautifulSoup 要素に直接 style= 属性を設定する。
#     ここでは git プラグインのテキスト color のみを補完する。
# ──────────────────────────────────────────────
def _generate_pdf_styles(template_dir: str, pdf_scheme: str):
    """PDF スキームに合わせた git プラグインのテキスト色を styles.scss に出力する"""
    fg_light = "hsla(0,0%,100%,.54)" if pdf_scheme == "slate" else "hsla(0,0%,0%,.54)"

    scss = f"""// Auto-generated by hooks/build_config.py (PDF_SCHEME={pdf_scheme})
.md-source-file,
.md-source-file__fact,
.md-source-file__fact .md-icon,
[class*="git-revision-date-localized-plugin"] {{
  color: {fg_light};
}}
"""
    os.makedirs(template_dir, exist_ok=True)
    styles_path = os.path.join(template_dir, "styles.scss")
    existing = ""
    if os.path.exists(styles_path):
        with open(styles_path, encoding="utf-8") as f:
            existing = f.read()
    if existing != scss:
        with open(styles_path, "w", encoding="utf-8") as f:
            f.write(scss)
    log.info(f"to-pdf: styles.scss generated ({pdf_scheme}) → {styles_path}")


# ──────────────────────────────────────────────
#  Hook エントリポイント
# ──────────────────────────────────────────────
def on_config(config):
    """theme.palette の primary/accent を読み取り、CSS と mermaid 設定に反映"""

    # --- palette から全エントリを取得 ---
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
            return _make_custom_palette(v)
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

    # mermaid には最初のエントリの accent を使用
    first_accent = schemes[0][2] if schemes else DEFAULT_COLOR

    # PDF カラースキームを環境変数から取得（未設定または不正値は "default" にフォールバック）
    pdf_scheme = os.environ.get("PDF_SCHEME", "default")
    if pdf_scheme not in ("default", "slate"):
        log.warning(f"PDF_SCHEME={pdf_scheme!r} は無効です。'default' を使用します。")
        pdf_scheme = "default"
    log.info(f"PDF scheme: {pdf_scheme}")

    # --- パレット CSS を生成 ---
    docs_dir = config["docs_dir"]
    css_dir = os.path.join(docs_dir, "stylesheets")
    os.makedirs(css_dir, exist_ok=True)
    css_path = os.path.join(css_dir, "_palette.css")

    css_content = _build_palette_css(schemes, pdf_scheme)
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
        mc["themeVariables"] = _build_mermaid_theme_variables(first_accent)
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

        # カバーロゴを PDF_SCHEME に合わせて選択
        logo_cfg = _PDF_LOGO_CONFIG.get(pdf_scheme, _PDF_LOGO_CONFIG["default"])
        cover_logo = logo_cfg["cover_logo"]
        pdf_plugin.config["cover_logo"] = cover_logo
        log.info(f"to-pdf: cover_logo={cover_logo}")

        # Options は既に作成済み → 内部変数を直接書き換える
        if hasattr(pdf_plugin, "_options") and pdf_plugin._options is not None:
            pdf_plugin._options._copyright = config["copyright"]
            pdf_plugin._options._cover_logo = cover_logo
            log.info("to-pdf: _copyright and _cover_logo updated directly")

            # custom_template_path/styles.scss を動的生成。
            # to-pdf はこのファイルを最後にコンパイル・追記するため、
            # !important なしで他の CSS より優先される。
            _generate_pdf_styles(
                pdf_plugin._options.custom_template_path,
                pdf_scheme,
            )

        log.info(f"to-pdf: output={site_name}.pdf, copyright={config['copyright']}")
    except (KeyError, TypeError, AttributeError):
        log.debug("to-pdf plugin not found or disabled")

    return config


def on_post_page(output, page, config):
    """PDF リンクを viewer HTML 経由で新しいタブに表示し、
    git プラグインアイコンの fill をインラインスタイルで直接適用する"""
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

    # to-pdf プラグインが on_post_page で page.pdf-article（BeautifulSoup 要素）を
    # セットした後、このフックが実行される。WeasyPrint では CSS による SVG fill の
    # 継承が機能しないため、要素に style= を直接付与してインラインスタイルで上書きする。
    pdf_article = getattr(page, "pdf-article", None)
    if pdf_article is not None:
        pdf_scheme = os.environ.get("PDF_SCHEME", "default")
        icon_fill = "rgba(255,255,255,0.54)" if pdf_scheme == "slate" else "rgba(0,0,0,0.54)"
        _fix_source_file_icon_fill(pdf_article, icon_fill)

    # to-pdf の on_post_build（PDF レンダリング）より先に mermaid PNG を透明化する。
    # on_post_build では既に PDF 生成済みのため、ここで処理する必要がある。
    _fix_mermaid_pngs_for_page(output, page, config)

    return output


def _fix_source_file_icon_fill(article, fill_color: str):
    """md-source-file__fact 内の SVG アイコンに fill をインラインスタイルで直接設定する。

    WeasyPrint では CSS セレクタによる fill の継承が機能しないため、
    BeautifulSoup 要素に style='fill: ...' をインラインで付与する。
    インラインスタイルはセレクタ CSS より優先度が高いため確実に適用される。
    """
    for fact_span in article.find_all(class_="md-source-file__fact"):
        for icon_span in fact_span.find_all(class_="md-icon"):
            for svg in icon_span.find_all("svg"):
                _set_fill_style(svg, fill_color)
                for path in svg.find_all("path"):
                    _set_fill_style(path, fill_color)


def _set_fill_style(tag, fill_color: str):
    """既存の style 属性を保持しつつ fill プロパティを末尾に追加する"""
    existing = tag.get("style", "").strip().rstrip(";")
    parts = [p for p in existing.split(";") if p.strip() and not p.strip().startswith("fill")]
    parts.append(f"fill: {fill_color}")
    tag["style"] = "; ".join(p.strip() for p in parts) + ";"


def _fix_mermaid_svgs(site_dir):
    """on_post_build 用: mermaid SVG の background-color を transparent に修正する。

    PNG の透明化は on_post_page 内の _fix_mermaid_pngs_for_page で処理済みのため、
    ここでは SVG ファイル自体の修正のみ行う（直接 SVG を参照する場合の対策）。
    """
    import re
    from pathlib import Path

    images_dir = Path(site_dir) / "images"
    if not images_dir.exists():
        return

    for svg_path in images_dir.glob("*_mermaid_*.svg"):
        text = svg_path.read_text(encoding="utf-8")
        fixed = re.sub(r"background-color\s*:\s*white\b", "background-color: transparent", text)
        if fixed != text:
            svg_path.write_text(fixed, encoding="utf-8")
            log.info(f"mermaid SVG background fixed: {svg_path.name}")


def _fix_mermaid_pngs_for_page(output, page, config):
    """on_post_page 用: ページ内の mermaid PNG を透明背景で再生成する。

    to-pdf は on_post_page で HTML を収集し on_post_build で PDF を生成する。
    on_post_page 内で PNG ファイルを透明化しておくことで、WeasyPrint が PDF を
    レンダリングする時点では透明背景の PNG が存在するようになる。
    """
    import re
    from pathlib import Path

    # minify プラグインが先に実行されるため、属性値の引用符が省略されている場合がある
    # 例: src="images/foo.png" → src=images/foo.png
    png_srcs = re.findall(
        r'src=["\']?([^"\'>\s]*_mermaid_[^"\'>\s]*\.png)["\']?', output
    )
    if not png_srcs:
        return

    site_dir = Path(config["site_dir"])
    page_dir = (site_dir / page.file.dest_path).parent

    png_paths = set()
    for src in png_srcs:
        png_path = (site_dir / src.lstrip("/")) if src.startswith("/") else (page_dir / src).resolve()
        if png_path.exists() and png_path.with_suffix(".svg").exists():
            png_paths.add(png_path)

    if not png_paths:
        return

    # SVG の background-color: white を transparent に置換
    for png_path in png_paths:
        svg_path = png_path.with_suffix(".svg")
        text = svg_path.read_text(encoding="utf-8")
        fixed = re.sub(r"background-color\s*:\s*white\b", "background-color: transparent", text)
        if fixed != text:
            svg_path.write_text(fixed, encoding="utf-8")
            log.info(f"mermaid SVG background fixed: {svg_path.name}")

    # Playwright で透明背景 PNG を再生成
    # MkDocs が asyncio ループを使用しているため、sync API は別スレッドで実行する
    errors = []

    def _render_pngs():
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch()
                for png_path in png_paths:
                    svg_content = png_path.with_suffix(".svg").read_text(encoding="utf-8")

                    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg_content)
                    vw = int(float(m.group(1))) + 20 if m else 800
                    vh = int(float(m.group(2))) + 20 if m else 600

                    html = (
                        f'<html style="background:transparent;margin:0">'
                        f'<body style="margin:0;background:transparent">'
                        f'{svg_content}</body></html>'
                    )
                    pw_page = browser.new_page(viewport={"width": vw, "height": vh})
                    pw_page.set_content(html)
                    bbox = pw_page.locator("svg").bounding_box()
                    pw_page.screenshot(
                        path=str(png_path),
                        clip=bbox if bbox else None,
                        full_page=bbox is None,
                        omit_background=True,
                    )
                    pw_page.close()
                    log.info(f"mermaid PNG re-rendered (transparent): {png_path.name}")
                browser.close()
        except Exception as e:
            errors.append(str(e))

    import threading
    t = threading.Thread(target=_render_pngs)
    t.start()
    t.join(timeout=120)
    if errors:
        log.warning(f"mermaid PNG re-render skipped: {errors[0]}")


def on_post_build(config):
    """PDF viewer HTML を生成（iframe で直接表示）"""
    from urllib.parse import quote

    _fix_mermaid_svgs(config["site_dir"])

    try:
        site_name = config.get("site_name", "docs")
        pdf_file = f"{site_name}.pdf"
        pdf_url = quote(pdf_file)
        site_dir = config["site_dir"]

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
<iframe src="{pdf_url}"></iframe>
</body>
</html>"""

        viewer_path = os.path.join(site_dir, f"{site_name}_pdf.html")
        with open(viewer_path, "w", encoding="utf-8") as f:
            f.write(viewer_html)
        log.info(f"PDF viewer: {viewer_path}")
    except Exception:
        log.debug("PDF viewer generation skipped")
