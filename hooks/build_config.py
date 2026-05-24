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
import shutil
from pathlib import Path

log = logging.getLogger("mkdocs.hooks.build_config")

# on_config で設定し、on_post_page / on_post_build で参照するモジュールレベル変数
_mermaid_dark_config: dict = {}
_pdf_scheme_global: str = "default"
_schemes_global: list = []  # (scheme_name, primary_palette, accent_palette) のリスト

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
        "cover_logo": "_assets/melyuh_lightmode.png",
        "hide_class": "logo-dark",  # ライト背景なので暗いロゴは不要
    },
    "slate": {
        "cover_logo": "_assets/melyuh_darkmode.png",
        "hide_class": "logo-light",  # 暗い背景なので明るいロゴは不要
    },
}


def _write_if_changed(path: str, content: str) -> None:
    existing = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing = f.read()
    if existing != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


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
    return f"#{int(r * (1 - factor)):02x}{int(g * (1 - factor)):02x}{int(b * (1 - factor)):02x}"


def _rgb_to_hsl(r, g, b):
    r, g, b = r / 255, g / 255, b / 255
    hi, lo = max(r, g, b), min(r, g, b)
    lightness = (hi + lo) / 2
    if hi == lo:
        return 0.0, 0.0, lightness
    d = hi - lo
    s = d / (2 - hi - lo) if lightness > 0.5 else d / (hi + lo)
    if hi == r:
        h = (g - b) / d % 6
    elif hi == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h / 6, s, lightness


def _hsl_to_hex(h, s, lightness):
    if s == 0:
        v = round(lightness * 255)
        return f"#{v:02x}{v:02x}{v:02x}"
    q = lightness * (1 + s) if lightness < 0.5 else lightness + s - lightness * s
    p = 2 * lightness - q

    def _f(t):
        t %= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 0.5:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    def _c(v):
        return min(round(v * 255), 255)

    return f"#{_c(_f(h + 1 / 3)):02x}{_c(_f(h)):02x}{_c(_f(h - 1 / 3)):02x}"


def _heading_color(hex_color, is_dark):
    """primary の色相だけ継承し、スキームの明暗に応じた読みやすい見出し色を返す。
    彩度は 25% に上限を設け、明度は固定（ダーク=94% / ライト=18%）。"""
    r, g, b = _hex_to_rgb(hex_color)
    h, s, _ = _rgb_to_hsl(r, g, b)
    return _hsl_to_hex(h, min(s, 0.25), 0.94 if is_dark else 0.18)


def _make_custom_palette(color):
    return {
        "main": color,
        "light": _blend_white(color, 0.4),
        "vlight": _blend_white(color, 0.82),
        "dark": _blend_black(color, 0.1),
    }


# ──────────────────────────────────────────────
#  1. パレット CSS（ブラウザ変数 + PDF print 用）
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
            # Material slate の実値に合わせる (--md-hue=225)
            bg = "hsla(225,15%,14%,1)"
            bg_light = "hsla(225,15%,18%,1)"
            bg_lighter = "hsla(225,15%,21%,1)"
            bg_lightest = "hsla(225,15%,25%,1)"
            fg = "hsla(225,15%,90%,.82)"
            fg_light = "hsla(225,15%,90%,.56)"
            fg_lighter = "hsla(225,15%,90%,.32)"
            fg_lightest = "hsla(225,15%,90%,.12)"
            code_fg = "hsla(225,18%,86%,.82)"
            code_bg = "hsla(225,15%,18%,1)"
            # シンタックスハイライト色 (Material slate の @media screen 値を引き継ぐ)
            hl_number = "#e6695b"
            hl_special = "#f06090"
            hl_function = "#c973d9"
            hl_constant = "#9383e2"
            hl_keyword = "#6791e0"
            hl_string = "#2fb170"
        else:
            bg = "#ffffff"
            bg_light = "hsla(0,0%,96%,1)"
            bg_lighter = "hsla(0,0%,98%,1)"
            bg_lightest = "hsla(0,0%,100%,1)"
            fg = "hsla(0,0%,0%,.87)"
            fg_light = "hsla(0,0%,0%,.54)"
            fg_lighter = "hsla(0,0%,0%,.32)"
            fg_lightest = "hsla(0,0%,0%,.12)"
            code_fg = "hsla(200,18%,26%,1)"
            code_bg = "hsla(0,0%,96%,1)"
            # シンタックスハイライト色 (Material default の :root 値と同一)
            hl_number = "#d52a2a"
            hl_special = "#db1457"
            hl_function = "#a846b9"
            hl_constant = "#6e59d9"
            hl_keyword = "#3f6ec6"
            hl_string = "#1c7d4d"

        h_color = _heading_color(p_primary["main"], is_dark)
        logo_cfg = _PDF_LOGO_CONFIG.get(p_scheme, _PDF_LOGO_CONFIG["default"])
        hide_logo_class = logo_cfg["hide_class"]

        lines.append(f"""@media print {{
  :root {{
    --md-hue:                          225;
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
    --md-code-hl-number-color:         {hl_number};
    --md-code-hl-special-color:        {hl_special};
    --md-code-hl-function-color:       {hl_function};
    --md-code-hl-constant-color:       {hl_constant};
    --md-code-hl-keyword-color:        {hl_keyword};
    --md-code-hl-string-color:         {hl_string};
    --md-default-h-color:              {h_color};
    --md-typeset-color:                {fg};
    --md-typeset-a-color:              {p_primary["main"]};
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
  /* PDF スキームに対応しない mermaid 図を非表示 */
  .mermaid-{"slate" if is_dark else "default"} {{ display: none !important; }}
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


def _build_mermaid_theme_variables_dark(accent):
    """スレートスキーム（ダークモード）用の Mermaid 配色"""
    node_bg = _blend_black(accent["main"], 0.3)
    border_color = accent["light"]
    return {
        "background": "transparent",
        "titleColor": "#e0e0e0",
        "primaryColor": node_bg,
        "primaryTextColor": "#ffffff",
        "primaryBorderColor": border_color,
        "secondaryColor": _blend_black(accent["main"], 0.4),
        "secondaryTextColor": "#e0e0e0",
        "secondaryBorderColor": border_color,
        "tertiaryColor": "#424242",
        "tertiaryTextColor": "#e0e0e0",
        "tertiaryBorderColor": "#757575",
        "lineColor": border_color,
        "arrowheadColor": border_color,
        "mainBkg": node_bg,
        "nodeBorder": border_color,
        "clusterBkg": "#2d2d2d",
        "clusterBorder": border_color,
        "edgeLabelBackground": "transparent",
        "actorBkg": node_bg,
        "actorBorder": border_color,
        "actorTextColor": "#ffffff",
        "actorLineColor": accent["main"],
        "signalColor": border_color,
        "signalTextColor": "#e0e0e0",
        "activationBkgColor": _blend_black(accent["main"], 0.5),
        "activationBorderColor": border_color,
        "labelBoxBkgColor": "#424242",
        "labelBoxBorderColor": border_color,
        "labelTextColor": "#e0e0e0",
        "loopTextColor": "#e0e0e0",
        "sequenceNumberColor": "#ffffff",
        "noteBkgColor": "#4a4000",
        "noteTextColor": "#e0e0e0",
        "noteBorderColor": "#ffd600",
        "sectionBkgColor": _rgba(accent["main"], 0.25),
        "sectionBkgColor2": _rgba(accent["main"], 0.12),
        "taskBkgColor": _blend_black(accent["main"], 0.2),
        "taskTextColor": "#ffffff",
        "taskBorderColor": accent["main"],
        "activeTaskBkgColor": accent["main"],
        "activeTaskBorderColor": accent["light"],
        "doneTaskBkgColor": "#37474f",
        "doneTaskBorderColor": "#546e7a",
        "critBkgColor": "#b71c1c",
        "critBorderColor": "#ef5350",
        "todayLineColor": border_color,
    }


# ──────────────────────────────────────────────
#  3. Mermaid ブラウザ向け初期化 JS（serve 時の配色を反映）
# ──────────────────────────────────────────────
def _generate_mermaid_config_js(schemes: list) -> str:
    """serve 時のブラウザ Mermaid レンダリング向け JS を生成する。

    mermaid.min.js が window.mermaid をセットするのを Object.defineProperty で捕捉し、
    initialize() をラップして themeVariables を注入する。テーマ切替時は MutationObserver
    で div.mermaid コンテナを置き換えて mermaid.run() で再描画する。
    """
    import json

    first_accent = schemes[0][2] if schemes else DEFAULT_COLOR

    vars_by_scheme = {}
    for scheme, _primary, _accent in schemes:
        if scheme == "slate":
            vars_by_scheme[scheme] = _build_mermaid_theme_variables_dark(first_accent)
        else:
            vars_by_scheme[scheme] = _build_mermaid_theme_variables(first_accent)

    if "default" not in vars_by_scheme and vars_by_scheme:
        vars_by_scheme["default"] = next(iter(vars_by_scheme.values()))

    vars_json = json.dumps(vars_by_scheme, ensure_ascii=False, indent=2)

    return f"""/* Auto-generated by hooks/build_config.py — DO NOT EDIT */
(function () {{
  var THEME_VARS = {vars_json};

  /* テーマ切替時の再描画用: Material は pre.mermaid を div.mermaid（closed Shadow DOM）
     に replaceWith するため element 参照でなくソーステキストだけを保存する */
  var _sources = [];
  document.querySelectorAll("pre.mermaid").forEach(function (el) {{
    _sources.push(el.textContent.trim());
  }});

  function getScheme() {{
    return (document.body || document.documentElement)
      .getAttribute("data-md-color-scheme") || "default";
  }}

  /* mermaid.min.js が window.mermaid をセットするのを捕捉して initialize() をラップする。
     themeCSS を除去し theme:"base" を強制することで themeVariables のみで色を制御し
     ビルド出力（mmdc）と一致させる。Material は theme を渡さないため "base" を指定しないと
     themeVariables が無視される。 */
  var _api;
  Object.defineProperty(window, "mermaid", {{
    configurable: true,
    get: function () {{ return _api; }},
    set: function (m) {{
      if (m && typeof m.initialize === "function" && !m.__themed__) {{
        var _orig = m.initialize.bind(m);
        m.initialize = function (cfg) {{
          cfg = cfg || {{}};
          var myVars = THEME_VARS[getScheme()] || THEME_VARS["default"];
          var out = Object.assign({{}}, cfg);
          delete out.themeCSS;
          out.theme          = "base";
          out.flowchart      = Object.assign({{ htmlLabels: false }}, cfg.flowchart || {{}});
          out.class          = Object.assign({{ htmlLabels: false }}, cfg.class     || {{}});
          out.themeVariables = Object.assign({{}}, myVars, cfg.themeVariables || {{}});
          return _orig(out);
        }};
        m.__themed__ = true;
      }}
      _api = m;
      Object.defineProperty(window, "mermaid", {{
        value: _api, writable: true, configurable: true, enumerable: true
      }});
    }}
  }});

  /* テーマ切替時: 再初期化 + 再描画
     初回: div.mermaid（Material の Shadow DOM コンテナ）を置換
     2 回目以降: code[data-mermaid-rerender] を置換 */
  document.addEventListener("DOMContentLoaded", function () {{
    if (!_sources.length) return;
    new MutationObserver(function () {{
      var m = window.mermaid;
      if (!m || !m.initialize || !m.run) return;
      var myVars = THEME_VARS[getScheme()] || THEME_VARS["default"];
      m.initialize({{
        startOnLoad: false, theme: "base",
        flowchart: {{ htmlLabels: false }}, class: {{ htmlLabels: false }},
        themeVariables: myVars
      }});
      var containers = Array.from(document.querySelectorAll(
        "div.mermaid, code[data-mermaid-rerender]"
      ));
      if (!containers.length) return;
      var newEls = [];
      containers.forEach(function (container, i) {{
        var src = _sources[i];
        if (!src) return;
        var newEl = document.createElement("code");
        newEl.className = "mermaid";
        newEl.textContent = src;
        newEl.setAttribute("data-mermaid-rerender", i);
        if (container.parentNode) {{
          container.parentNode.replaceChild(newEl, container);
          newEls.push(newEl);
        }}
      }});
      if (newEls.length) {{
        m.run({{ nodes: newEls }});
      }}
    }}).observe(document.body, {{
      attributes: true, attributeFilter: ["data-md-color-scheme"]
    }});
  }});
}})();
"""


# ──────────────────────────────────────────────
#  4. PDF カスタムスタイル（custom_template_path/styles.scss）
#     to-pdf は report-print.scss → cover.scss → styles.scss の順でコンパイルし
#     最後に <style> として追記する。doc-toc の h1 は _toc.scss が
#     specificity(0,1,2) で色を固定しているため !important で上書きする。
#
#     SVG アイコンの fill は WeasyPrint で CSS カスケードが効かないため、
#     on_post_page フックで BeautifulSoup 要素に直接 style= 属性を設定する。
# ──────────────────────────────────────────────
def _generate_pdf_styles(template_dir: str, pdf_scheme: str):
    """PDF スキームに合わせたテキスト色を styles.scss に出力する"""
    is_dark = pdf_scheme == "slate"
    fg = "hsla(0,0%,100%,.87)" if is_dark else "hsla(0,0%,0%,.87)"
    fg_light = "hsla(0,0%,100%,.54)" if is_dark else "hsla(0,0%,0%,.54)"

    # styles.scss は to-pdf が全ページの <style> として挿入するため、
    # ウェブサイトにも適用される。スキームセレクタで両テーマを明示的に制御し、
    # PDF 専用ルールは @media print に閉じ込める。
    scss = f"""// Auto-generated by hooks/build_config.py (PDF_SCHEME={pdf_scheme})
// ── ウェブサイト: スキームごとにアイコン色を制御 ──
[data-md-color-scheme="default"] .md-source-file,
[data-md-color-scheme="default"] .md-source-file__fact,
[data-md-color-scheme="default"] .md-source-file__fact .md-icon,
[data-md-color-scheme="default"] [class*="git-revision-date-localized-plugin"] {{
  color: hsla(0,0%,0%,.54);
}}
[data-md-color-scheme="slate"] .md-source-file,
[data-md-color-scheme="slate"] .md-source-file__fact,
[data-md-color-scheme="slate"] .md-source-file__fact .md-icon,
[data-md-color-scheme="slate"] [class*="git-revision-date-localized-plugin"] {{
  color: hsla(0,0%,100%,.54);
}}
// ── PDF 専用 (@media print) ──
@media print {{
  .md-source-file,
  .md-source-file__fact,
  .md-source-file__fact .md-icon,
  [class*="git-revision-date-localized-plugin"] {{
    color: {fg_light};
  }}
  /* 目次ページ: _toc.scss が article#doc-toc > h1 {{ color: rgba(0,0,0,.54) }} を
     specificity (0,1,2) で定義しているため !important で上書きする */
  article#doc-toc > h1,
  article#doc-toc li > a {{
    color: {fg} !important;
  }}
}}
"""
    os.makedirs(template_dir, exist_ok=True)
    styles_path = os.path.join(template_dir, "styles.scss")
    _write_if_changed(styles_path, scss)
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

    # to-pdf の "主" スキームは palette の先頭エントリから決定する
    # 両スキームとも on_post_build で生成するため環境変数による切り替えは不要
    pdf_scheme = schemes[0][0] if schemes else "default"
    log.info(f"PDF primary scheme: {pdf_scheme}")

    # モジュールレベル変数を更新（on_post_page / on_post_build で参照）
    global _mermaid_dark_config, _pdf_scheme_global, _schemes_global
    _pdf_scheme_global = pdf_scheme
    _schemes_global = schemes
    _mermaid_dark_config = {
        "theme": "base",
        "themeVariables": _build_mermaid_theme_variables_dark(first_accent),
        "flowchart": {"htmlLabels": False},
        "class": {"htmlLabels": False},
    }

    # --- パレット CSS を生成 ---
    docs_dir = config["docs_dir"]
    css_dir = os.path.join(docs_dir, "_stylesheets")
    os.makedirs(css_dir, exist_ok=True)
    css_path = os.path.join(css_dir, "_palette.css")

    css_content = _build_palette_css(schemes, pdf_scheme)
    _write_if_changed(css_path, css_content)
    log.info(f"Generated palette CSS: {css_path}")

    # --- to-pdf styles.scss を生成 (plugin が disabled でも常に実行) ---
    project_root = os.path.dirname(docs_dir)
    _generate_pdf_styles(os.path.join(project_root, "templates"), pdf_scheme)

    # extra_css の先頭に追加（Material デフォルトを上書き）
    css_ref = "_stylesheets/_palette.css"
    extra_css = config.get("extra_css", [])
    if css_ref not in extra_css:
        extra_css.insert(0, css_ref)

    # --- Mermaid ブラウザ向け初期化 JS を生成（serve 時の配色反映） ---
    js_dir = os.path.join(docs_dir, "_javascripts")
    os.makedirs(js_dir, exist_ok=True)
    js_path = os.path.join(js_dir, "_mermaid_config.js")
    js_content = _generate_mermaid_config_js(schemes)
    _write_if_changed(js_path, js_content)
    log.info(f"Generated mermaid config JS: {js_path}")

    js_ref = "_javascripts/_mermaid_config.js"
    extra_js = config.get("extra_javascript", [])
    if js_ref not in extra_js:
        # mermaid.min.js より前に挿入して window.mermaid を先行設定する
        mermaid_idx = next(
            (i for i, x in enumerate(extra_js) if "mermaid" in str(x)), 0
        )
        extra_js.insert(mermaid_idx, js_ref)

    plugins = config.get("plugins", {})

    try:
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

    try:
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
            # dual PDF 生成用: WeasyPrint に渡す HTML を保存しておく
            pdf_plugin._options.html_path = "_pdf_source.html"
            # PDF 内の画像リンクを除去するフックを差し込む（EventHookHandler の公式機構をバイパス）
            pdf_plugin._options.hook.pre_pdf_render = _pre_pdf_render
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

    # ページの深さに応じてサイトルートへの相対パスを計算
    page_dir = os.path.dirname(page.file.dest_path)
    if page_dir:
        viewer_href = os.path.relpath(viewer_file, page_dir).replace(os.sep, "/")
    else:
        viewer_href = viewer_file

    # <link rel="alternate" ... pdf ...> を除去（ダウンロード誘発防止）
    output = re.sub(r"<link[^>]*" + re.escape(pdf_file) + r"[^>]*>", "", output)

    # PDF アイコンの href を viewer に変更 + target="_blank"
    output = re.sub(
        r'href=["\']?[^"\'>\s]*'
        + re.escape(pdf_file)
        + r'["\']?\s*title=["\']?PDF["\']?',
        f'href="{viewer_href}" title="PDF" target="_blank"',
        output,
    )

    # to-pdf プラグインが on_post_page で page.pdf-article（BeautifulSoup 要素）を
    # セットした後、このフックが実行される。WeasyPrint では CSS による SVG fill の
    # 継承が機能しないため、要素に style= を直接付与してインラインスタイルで上書きする。
    pdf_article = getattr(page, "pdf-article", None)
    if pdf_article is not None:
        icon_fill = (
            "rgba(255,255,255,0.54)"
            if _pdf_scheme_global == "slate"
            else "rgba(0,0,0,0.54)"
        )
        _fix_source_file_icon_fill(pdf_article, icon_fill)
        text_fill = (
            "rgba(255,255,255,0.82)"
            if _pdf_scheme_global == "slate"
            else "rgba(0,0,0,0.87)"
        )
        _fix_inline_icon_fill(pdf_article, text_fill)
        grid_fill = "#1a1a1a" if _pdf_scheme_global == "slate" else "#ffffff"
        _fix_grid_card_icon_fill(pdf_article, grid_fill)
        arrow_fill = next(
            (p["main"] for s, p, _ in _schemes_global if s == _pdf_scheme_global),
            "#26C6DA",
        )
        _fix_grid_card_arrow_fill(pdf_article, arrow_fill)

    # mermaid PNG をライト/ダーク両モードで生成し HTML を差し替える。
    # to-pdf の on_post_build（PDF レンダリング）より先に実行されるため、
    # WeasyPrint が PDF をレンダリングする時点では透明 PNG が存在する。
    output = _fix_mermaid_pngs_for_page(output, page, config)

    return output


def _pre_pdf_render(html_string: str) -> str:
    """WeasyPrint レンダリング直前に HTML を加工する。

    1. 画像リンクの href を除去してクリック不可にする
    2. 全インラインアイコンにスキームの文字色を設定する（fix_twemoji 変換後）
    3. グリッドカード固有アイコンで上書きする

    to-pdf の EventHookHandler.pre_pdf_render をインスタンス属性で上書きして差し込む。
    このタイミングは WeasyPrint 呼び出し前かつ html_path 保存前なので
    _pdf_source.html にも変更が反映される。
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_string, "html.parser")

    # 画像リンクの href を除去
    for a in soup.find_all("a", href=True):
        if a.find("img"):
            del a["href"]

    # 1. 全インラインアイコン（span.twemoji）にスキームの文字色を設定
    text_fill = (
        "rgba(255,255,255,0.82)"
        if _pdf_scheme_global == "slate"
        else "rgba(0,0,0,0.87)"
    )
    _fix_converted_inline_icon_fill(soup, text_fill)
    log.info(f"pre_pdf_render: inline icon fill set to {text_fill}")
    # 2. グリッドカードタイトルアイコンを上書き
    grid_fill = "#1a1a1a" if _pdf_scheme_global == "slate" else "#ffffff"
    _fix_converted_twemoji_fill(soup, grid_fill)
    log.info(f"pre_pdf_render: grid card title icon fill set to {grid_fill}")
    # 3. グリッドカード矢印アイコンを上書き
    arrow_fill = next(
        (p["main"] for s, p, _ in _schemes_global if s == _pdf_scheme_global),
        "#26C6DA",
    )
    _fix_converted_arrow_fill(soup, arrow_fill)
    log.info(f"pre_pdf_render: arrow icon fill set to {arrow_fill}")

    return str(soup)


def _fix_grid_card_icon_fill(article, fill_color: str):
    """グリッドカード先頭行のアイコン SVG に fill を SVG 属性として直接設定する。

    WeasyPrint は CSS の fill プロパティ（インラインスタイル含む）を SVG 要素に
    適用しないため、SVG ネイティブの fill 属性（fill="color"）を直接付与する。

    on_post_page で pdf_article に対して呼び出す用途（fix_twemoji 変換前）。
    fix_twemoji 変換後（pre_pdf_render / _generate_both_pdfs）は
    _fix_converted_twemoji_fill を使用する。
    """
    svg_count = 0
    for span in article.select("span.twemoji.lg.middle"):
        for svg in span.find_all("svg"):
            svg["fill"] = fill_color
            for el in svg.find_all(["path", "polygon", "circle", "rect"]):
                el["fill"] = fill_color
            svg_count += 1
    if svg_count:
        log.info(
            f"_fix_grid_card_icon_fill: {svg_count} SVG(s) updated → fill={fill_color}"
        )
    else:
        log.debug(f"_fix_grid_card_icon_fill: no SVG found (fill={fill_color})")


def _fix_grid_card_arrow_fill(article, fill_color: str):
    """グリッドカードリンク行（p:last-child）の矢印アイコン SVG に fill を設定する。

    on_post_page で pdf_article に対して呼び出す用途（fix_twemoji 変換前）。
    fix_twemoji 変換後は _fix_converted_arrow_fill を使用する。
    """
    svg_count = 0
    for p in article.select(".grid.cards li > p:last-child"):
        for span in p.find_all("span", class_="twemoji"):
            for svg in span.find_all("svg"):
                svg["fill"] = fill_color
                for el in svg.find_all(["path", "polygon", "circle", "rect"]):
                    el["fill"] = fill_color
                svg_count += 1
    if svg_count:
        log.info(
            f"_fix_grid_card_arrow_fill: {svg_count} SVG(s) updated → fill={fill_color}"
        )
    else:
        log.debug(f"_fix_grid_card_arrow_fill: no SVG found (fill={fill_color})")


def _fix_inline_icon_fill(article, fill_color: str):
    """全インラインアイコン（span.twemoji svg）に fill を設定する。

    グリッドカード固有のアイコンはこの後で上書きするため、先に呼び出す。
    fix_twemoji 変換後は _fix_converted_inline_icon_fill を使用する。
    """
    svg_count = 0
    for span in article.find_all("span", class_="twemoji"):
        for svg in span.find_all("svg"):
            svg["fill"] = fill_color
            for el in svg.find_all(["path", "polygon", "circle", "rect"]):
                el["fill"] = fill_color
            svg_count += 1
    if svg_count:
        log.info(
            f"_fix_inline_icon_fill: {svg_count} SVG(s) updated → fill={fill_color}"
        )
    else:
        log.debug(f"_fix_inline_icon_fill: no SVG found (fill={fill_color})")


def _recolor_converted_spans(spans, fill_color: str, label: str = "") -> int:
    """span 要素リスト内の fix_twemoji 変換後 base64 SVG img の fill を書き換える共通ヘルパー。"""
    import base64
    from bs4 import BeautifulSoup as _SVGSoup

    count = 0
    prefix = "data:image/svg+xml;charset=utf-8;base64,"
    for span in spans:
        for img in span.find_all("img", class_="converted-twemoji"):
            src = img.get("src", "")
            if not src.startswith(prefix):
                continue
            try:
                svg_str = base64.b64decode(src[len(prefix) :]).decode("utf-8")
                svg_soup = _SVGSoup(svg_str, "html.parser")
                for svg_el in svg_soup.find_all("svg"):
                    svg_el["fill"] = fill_color
                    svg_el["style"] = f"fill: {fill_color};"
                    for el in svg_el.find_all(["path", "polygon", "circle", "rect"]):
                        el["fill"] = fill_color
                img["src"] = prefix + base64.b64encode(
                    str(svg_soup).encode("utf-8")
                ).decode("ascii")
                count += 1
            except Exception as e:
                log.warning(f"_recolor_converted_spans ({label}): {e}")
    return count


def _fix_converted_inline_icon_fill(soup, fill_color: str) -> int:
    """全インラインアイコン（span.twemoji）の base64 SVG img に fill を設定する。

    グリッドカード固有のアイコンはこの後で上書きするため、先に呼び出す。
    fix_twemoji 変換前は _fix_inline_icon_fill を使用する。
    """
    count = _recolor_converted_spans(
        list(soup.find_all("span", class_="twemoji")), fill_color, "inline"
    )
    log.info(
        f"_fix_converted_inline_icon_fill: {count} img(s) updated → fill={fill_color}"
    )
    return count


def _fix_converted_twemoji_fill(soup, fill_color: str) -> int:
    """グリッドカードタイトルアイコン（span.twemoji.lg.middle）の base64 SVG img に fill を設定する。

    to-pdf の fix_twemoji は `.twemoji svg` を base64 の `<img class="converted-twemoji">` に変換する。
    fix_twemoji 変換前は _fix_grid_card_icon_fill を使用する。
    """
    count = _recolor_converted_spans(
        soup.select("span.twemoji.lg.middle"), fill_color, "title"
    )
    log.info(f"_fix_converted_twemoji_fill: {count} img(s) updated → fill={fill_color}")
    return count


def _fix_converted_arrow_fill(soup, fill_color: str) -> int:
    """グリッドカードリンク行（p:last-child）の base64 SVG img に fill を設定する。

    fix_twemoji 変換前は _fix_grid_card_arrow_fill を使用する。
    """
    spans = [
        span
        for p in soup.select(".grid.cards li > p:last-child")
        for span in p.find_all("span", class_="twemoji")
    ]
    count = _recolor_converted_spans(spans, fill_color, "arrow")
    log.info(f"_fix_converted_arrow_fill: {count} img(s) updated → fill={fill_color}")
    return count


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
    parts = [
        p for p in existing.split(";") if p.strip() and not p.strip().startswith("fill")
    ]
    parts.append(f"fill: {fill_color}")
    tag["style"] = "; ".join(p.strip() for p in parts) + ";"


def _fix_mermaid_svgs(site_dir):
    """on_post_build 用: mermaid SVG の background-color を transparent に修正する（SVG 直参照用）"""
    images_dir = Path(site_dir) / "images"
    if not images_dir.exists():
        return
    for svg_path in images_dir.glob("*_mermaid_*.svg"):
        text = svg_path.read_text(encoding="utf-8")
        fixed = re.sub(
            r"background-color\s*:\s*white\b", "background-color: transparent", text
        )
        if fixed != text:
            svg_path.write_text(fixed, encoding="utf-8")
            log.info(f"mermaid SVG background fixed: {svg_path.name}")


def _generate_dark_svg(mermaid_source: str, project_root) -> "str | None":
    """mmdc を subprocess で実行してダークテーマの SVG を生成する。
    devcontainer 環境では Chrome が断続的にクラッシュするため最大2回リトライする。
    """
    import json
    import subprocess
    import tempfile
    import time

    mmdc = Path(project_root) / "node_modules" / ".bin" / "mmdc"
    if not mmdc.exists():
        log.warning(f"mmdc not found: {mmdc}")
        return None

    puppeteer_cfg = {"args": ["--no-sandbox", "--disable-setuid-sandbox"]}

    for attempt in range(3):
        if attempt > 0:
            time.sleep(1.5)  # Chrome リソース解放を待つ
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "input.mmd").write_text(mermaid_source, encoding="utf-8")
            (td / "config.json").write_text(
                json.dumps(_mermaid_dark_config), encoding="utf-8"
            )
            (td / "puppeteer.json").write_text(
                json.dumps(puppeteer_cfg), encoding="utf-8"
            )
            result = subprocess.run(
                [
                    str(mmdc),
                    "-i",
                    str(td / "input.mmd"),
                    "-o",
                    str(td / "output.svg"),
                    "--configFile",
                    str(td / "config.json"),
                    "--puppeteerConfigFile",
                    str(td / "puppeteer.json"),
                    "-b",
                    "transparent",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(project_root),
            )
            if result.returncode == 0:
                out = td / "output.svg"
                if out.exists():
                    return out.read_text(encoding="utf-8")
            log.warning(
                f"mmdc (dark) attempt {attempt + 1} failed: {result.stderr[:200]}"
            )

    return None


def _render_svg_to_png(browser, svg_content: str, png_path):
    """Playwright ブラウザで SVG → 透明背景 PNG に変換する"""
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg_content)
    vw = int(float(m.group(1))) + 20 if m else 800
    vh = int(float(m.group(2))) + 20 if m else 600

    html = (
        '<html style="background:transparent;margin:0">'
        '<body style="margin:0;background:transparent">'
        f"{svg_content}</body></html>"
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


def _replace_mermaid_in_html(
    html: str, orig_src: str, default_src: str, slate_src: str
) -> str:
    """<a href=X.png><img src=X.png></a> を light/dark の2スパンに差し替える"""
    escaped = re.escape(orig_src)

    def wrap(m):
        block = m.group(0)
        return (
            f'<span class="mermaid-default">{block.replace(orig_src, default_src)}</span>'
            f'<span class="mermaid-slate">{block.replace(orig_src, slate_src)}</span>'
        )

    a_pattern = (
        r"<a\s[^>]*?" + escaped + r"[^>]*?>"
        r"<img\s[^>]*?" + escaped + r"[^>]*?>"
        r"</a>"
    )
    result = re.sub(a_pattern, wrap, html)
    if result != html:
        return result

    return re.sub(r"<img\s[^>]*?" + escaped + r"[^>]*?>", wrap, html)


def _fix_mermaid_pngs_for_page(output: str, page, config) -> str:
    """on_post_page 用: mermaid PNG をライト/ダーク両モードで生成し HTML を修正する。

    実行順序:
      mermaid-to-svg (on_page_content) → to-pdf 収集 (on_post_page) → minify (on_post_page)
      → このフック: light/dark PNG 生成 + HTML 差し替え
      → to-pdf on_post_build: WeasyPrint が X.png（PDF スキーム対応版）でレンダリング
    """
    png_srcs = list(
        dict.fromkeys(
            re.findall(r'src=["\']?([^"\'>\s]*_mermaid_[^"\'>\s]*\.png)["\']?', output)
        )
    )
    if not png_srcs:
        return output

    site_dir = Path(config["site_dir"])
    docs_dir = Path(config["docs_dir"])
    page_dir = (site_dir / page.file.dest_path).parent
    project_root = docs_dir.parent

    # markdown ソースから mermaid ブロックをインデックス順に抽出
    # 4バックティック以上のフェンス（コード表示用）内の ```mermaid を除外するため先に除去する
    md_content = (docs_dir / page.file.src_path).read_text(encoding="utf-8")
    md_stripped = re.sub(
        r"````+[^\n]*\n.*?````+[^\n]*", "", md_content, flags=re.DOTALL
    )
    mermaid_blocks = re.findall(r"```mermaid\n(.*?)```", md_stripped, re.DOTALL)

    # PNG パスとダイアグラムインデックスを解決
    png_info = []  # list of (png_path, diagram_idx, src)
    for src in png_srcs:
        png_path = (
            (site_dir / src.lstrip("/"))
            if src.startswith("/")
            else (page_dir / src).resolve()
        )
        m = re.search(r"_mermaid_(\d+)_", str(png_path))
        if not m:
            continue
        idx = int(m.group(1))
        if not png_path.exists() or not png_path.with_suffix(".svg").exists():
            continue
        png_info.append((png_path, idx, src))

    if not png_info:
        return output

    # ライト SVG の背景修正
    for png_path, idx, src in png_info:
        svg_path = png_path.with_suffix(".svg")
        text = svg_path.read_text(encoding="utf-8")
        fixed = re.sub(
            r"background-color\s*:\s*white\b", "background-color: transparent", text
        )
        if fixed != text:
            svg_path.write_text(fixed, encoding="utf-8")

    # ダーク SVG を mmdc subprocess で生成（asyncio 競合なし）
    dark_svgs = {}
    for png_path, idx, src in png_info:
        if idx >= len(mermaid_blocks):
            continue
        raw = _generate_dark_svg(mermaid_blocks[idx], project_root)
        if raw:
            raw = re.sub(
                r"background-color\s*:\s*white\b", "background-color: transparent", raw
            )
            dark_svgs[src] = raw

    # Playwright で light/dark PNG を透明背景で生成（別スレッドで asyncio 競合を回避）
    errors: list = []

    def _render_all():
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch()
                for png_path, idx, src in png_info:
                    stem = png_path.stem
                    parent = png_path.parent
                    default_path = parent / f"{stem}_default.png"
                    slate_path = parent / f"{stem}_slate.png"

                    light_svg = png_path.with_suffix(".svg").read_text(encoding="utf-8")
                    _render_svg_to_png(browser, light_svg, default_path)
                    log.info(f"mermaid PNG (light): {default_path.name}")

                    if src in dark_svgs:
                        _render_svg_to_png(browser, dark_svgs[src], slate_path)
                        log.info(f"mermaid PNG (dark): {slate_path.name}")
                    else:
                        shutil.copy2(default_path, slate_path)
                        log.warning(f"mermaid dark fallback (copy): {slate_path.name}")

                    # PDF 用: X.png を PDF_SCHEME 対応版で上書き
                    pdf_src = (
                        slate_path if _pdf_scheme_global == "slate" else default_path
                    )
                    shutil.copy2(pdf_src, png_path)

                browser.close()
        except Exception as e:
            errors.append(str(e))

    import threading

    t = threading.Thread(target=_render_all)
    t.start()
    t.join(timeout=180)

    if errors:
        log.warning(f"mermaid PNG render skipped: {errors[0]}")
        return output

    # HTML の mermaid 画像を light/dark 切り替え構造に差し替え
    modified = output
    for png_path, idx, src in png_info:
        stem = png_path.stem
        default_src = src.replace(stem, f"{stem}_default")
        slate_src = src.replace(stem, f"{stem}_slate")
        modified = _replace_mermaid_in_html(modified, src, default_src, slate_src)

    return modified


def _generate_both_pdfs(config):
    """to-pdf が生成した PDF を primary_scheme 版として保存し、
    alternate scheme 版を WeasyPrint で追加生成する。
    両スキームの PDF が site/ に _default.pdf / _slate.pdf として出力される。
    """
    site_dir = Path(config["site_dir"])
    site_name = config.get("site_name", "docs")
    primary = _pdf_scheme_global
    alt = "slate" if primary == "default" else "default"

    orig_pdf = site_dir / f"{site_name}.pdf"
    if not orig_pdf.exists():
        log.debug("PDF not found; skipping dual PDF generation")
        return

    primary_pdf = site_dir / f"{site_name}_{primary}.pdf"
    alt_pdf = site_dir / f"{site_name}_{alt}.pdf"
    shutil.copy2(orig_pdf, primary_pdf)

    # html_path で保存した HTML を読み込む
    saved_html = site_dir / "_pdf_source.html"
    if not saved_html.exists():
        log.warning("Saved HTML not found; alternate PDF will not be generated")
        return

    html = saved_html.read_text(encoding="utf-8")

    try:
        pdf_plugin = config.get("plugins", {})["to-pdf"]
    except KeyError:
        return

    template_dir = pdf_plugin._options.custom_template_path
    palette_path = site_dir / "_stylesheets" / "_palette.css"
    orig_palette = (
        palette_path.read_text(encoding="utf-8") if palette_path.exists() else ""
    )

    # 代替スキームの print CSS（styles.scss を含む）を生成
    _generate_pdf_styles(template_dir, alt)
    from mkdocs_to_pdf.styles import style_for_print

    alt_print_css = style_for_print(pdf_plugin._options)

    # HTML 内の style_for_print ブロック（string-set: を含む）を差し替え
    def swap_print_style(m):
        return (
            f"{m.group(1)}{alt_print_css}{m.group(3)}"
            if "string-set:" in m.group(2)
            else m.group(0)
        )

    alt_html = re.sub(
        r"(<style[^>]*>)(.*?)(</style>)", swap_print_style, html, flags=re.DOTALL
    )

    # カバーロゴを代替スキーム用に差し替え
    orig_logo = _PDF_LOGO_CONFIG[primary]["cover_logo"]
    alt_logo = _PDF_LOGO_CONFIG[alt]["cover_logo"]
    alt_html = alt_html.replace(orig_logo, alt_logo)

    # on_post_page で inline fill が primary スキームの色で設定されているため代替色に置換する
    primary_fill = (
        "rgba(255,255,255,0.54)" if primary == "slate" else "rgba(0,0,0,0.54)"
    )
    alt_fill = "rgba(0,0,0,0.54)" if primary == "slate" else "rgba(255,255,255,0.54)"
    alt_html = alt_html.replace(f"fill: {primary_fill}", f"fill: {alt_fill}")

    # 代替スキーム用アイコン fill を設定（_pdf_source.html は fix_twemoji 変換後）
    from bs4 import BeautifulSoup as _BS

    alt_soup = _BS(alt_html, "html.parser")
    # 1. 全インラインアイコンに代替スキームの文字色を設定
    alt_text_fill = "rgba(255,255,255,0.82)" if alt == "slate" else "rgba(0,0,0,0.87)"
    _fix_converted_inline_icon_fill(alt_soup, alt_text_fill)
    log.info(f"Alternate PDF ({alt}): inline icon fill set to {alt_text_fill}")
    # 2. グリッドカードタイトルアイコンを上書き
    grid_alt_fill = "#ffffff" if alt == "default" else "#1a1a1a"
    _fix_converted_twemoji_fill(alt_soup, grid_alt_fill)
    log.info(f"Alternate PDF ({alt}): grid card title icon fill set to {grid_alt_fill}")
    # 3. グリッドカード矢印アイコンを上書き
    arrow_alt_fill = next(
        (p["main"] for s, p, _ in _schemes_global if s == alt),
        "#00838F",
    )
    _fix_converted_arrow_fill(alt_soup, arrow_alt_fill)
    log.info(f"Alternate PDF ({alt}): arrow icon fill set to {arrow_alt_fill}")
    alt_html = str(alt_soup)

    # mermaid PNG を代替スキーム用に一時差し替え
    images_dir = site_dir / "images"
    png_backups: list = []
    if images_dir.exists():
        for default_png in images_dir.glob("*_mermaid_*_default.png"):
            stem = default_png.stem[: -len("_default")]
            orig_png = images_dir / f"{stem}.png"
            slate_png = images_dir / f"{stem}_slate.png"
            if orig_png.exists() and slate_png.exists():
                backup = images_dir / f"{stem}.png.bak"
                shutil.copy2(orig_png, backup)
                shutil.copy2(slate_png if alt == "slate" else default_png, orig_png)
                png_backups.append((orig_png, backup))

    try:
        palette_path.write_text(
            _build_palette_css(_schemes_global, alt), encoding="utf-8"
        )
        import weasyprint

        weasyprint.HTML(string=alt_html).write_pdf(str(alt_pdf))
        log.info(f"Alternate PDF ({alt}) generated: {alt_pdf.name}")
    except Exception as e:
        log.error(f"Alternate PDF generation failed: {e}")
    finally:
        palette_path.write_text(orig_palette, encoding="utf-8")
        _generate_pdf_styles(template_dir, primary)
        for orig_png, backup in png_backups:
            if backup.exists():
                shutil.copy2(backup, orig_png)
                backup.unlink()
        saved_html.unlink(missing_ok=True)

    # 元の *.pdf は不要（*_default.pdf / *_slate.pdf のみ保持）
    orig_pdf.unlink(missing_ok=True)
    log.info(f"Dual PDFs ready: {primary_pdf.name}, {alt_pdf.name}")


def on_post_build(config):
    """PDF viewer HTML を生成（iframe で直接表示）し、両スキームの PDF を生成する"""
    from urllib.parse import quote

    _fix_mermaid_svgs(config["site_dir"])
    _generate_both_pdfs(config)

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
