"""パレット色計算と CSS 生成"""

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

PDF_LOGO_CONFIG = {
    "default": {
        "cover_logo": "_assets/melyuh_lightmode.png",
        "hide_class": "logo-dark",
    },
    "slate": {
        "cover_logo": "_assets/melyuh_darkmode.png",
        "hide_class": "logo-light",
    },
}


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def is_dark(hex_color: str) -> bool:
    r, g, b = hex_to_rgb(hex_color)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 < 0.5


def text_on(bg: str) -> str:
    return "#ffffff" if is_dark(bg) else "#1a1a1a"


def rgba(hex_color: str, alpha: float) -> str:
    r, g, b = hex_to_rgb(hex_color)
    return f"rgba({r},{g},{b},{alpha})"


def blend_white(hex_color: str, factor: float) -> str:
    r, g, b = hex_to_rgb(hex_color)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def blend_black(hex_color: str, factor: float) -> str:
    r, g, b = hex_to_rgb(hex_color)
    return (
        f"#{int(r * (1 - factor)):02x}"
        f"{int(g * (1 - factor)):02x}"
        f"{int(b * (1 - factor)):02x}"
    )


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    rv, gv, bv = r / 255, g / 255, b / 255
    hi, lo = max(rv, gv, bv), min(rv, gv, bv)
    lightness = (hi + lo) / 2
    if hi == lo:
        return 0.0, 0.0, lightness
    d = hi - lo
    s = d / (2 - hi - lo) if lightness > 0.5 else d / (hi + lo)
    if hi == rv:
        h = (gv - bv) / d % 6
    elif hi == gv:
        h = (bv - rv) / d + 2
    else:
        h = (rv - gv) / d + 4
    return h / 6, s, lightness


def hsl_to_hex(h: float, s: float, lightness: float) -> str:
    if s == 0:
        v = round(lightness * 255)
        return f"#{v:02x}{v:02x}{v:02x}"
    q = lightness * (1 + s) if lightness < 0.5 else lightness + s - lightness * s
    p = 2 * lightness - q

    def _f(t: float) -> float:
        t %= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 0.5:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    def _c(v: float) -> int:
        return min(round(v * 255), 255)

    return f"#{_c(_f(h + 1 / 3)):02x}{_c(_f(h)):02x}{_c(_f(h - 1 / 3)):02x}"


def heading_color(hex_color: str, is_dark_scheme: bool) -> str:
    """primary の色相だけ継承し、スキームの明暗に応じた読みやすい見出し色を返す。
    彩度は 25% に上限を設け、明度は固定（ダーク=94% / ライト=18%）。"""
    r, g, b = hex_to_rgb(hex_color)
    h, s, _ = rgb_to_hsl(r, g, b)
    return hsl_to_hex(h, min(s, 0.25), 0.94 if is_dark_scheme else 0.18)


def make_custom_palette(color: str) -> dict:
    return {
        "main": color,
        "light": blend_white(color, 0.4),
        "vlight": blend_white(color, 0.82),
        "dark": blend_black(color, 0.1),
    }


def build_palette_css(schemes: list, pdf_scheme: str = "default") -> str:
    """schemes: list of (scheme_name, primary_palette, accent_palette)
    pdf_scheme: PDF に適用するスキーム名 ("default" または "slate")
    """
    lines = ["/* Auto-generated by hooks/build_config.py — DO NOT EDIT */"]

    for scheme, primary, accent in schemes:
        sel = f'[data-md-color-scheme="{scheme}"]'
        is_dark_scheme = scheme == "slate"
        p_bg = "#fff" if is_dark(primary["main"]) else "#000"
        a_bg = "#fff" if is_dark(accent["main"]) else "#000"

        lines.append(
            f"""{sel} {{
  --md-primary-fg-color:             {primary["main"]};
  --md-primary-fg-color--light:      {primary["light"]};
  --md-primary-fg-color--dark:       {primary["dark"]};
  --md-primary-bg-color:             {p_bg};
  --md-primary-bg-color--light:      {p_bg}99;
  --md-accent-fg-color:              {accent["main"]};
  --md-accent-fg-color--transparent: {accent["main"]}10;
  --md-accent-bg-color:              {a_bg};
  --md-default-h-color:              {heading_color(primary["main"], is_dark_scheme)};
}}"""
        )

    print_entry = next(
        (e for e in schemes if e[0] == pdf_scheme),
        schemes[0] if schemes else None,
    )
    if print_entry:
        p_scheme, p_primary, p_accent = print_entry
        is_dark_scheme = p_scheme == "slate"

        if is_dark_scheme:
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
            hl_number = "#d52a2a"
            hl_special = "#db1457"
            hl_function = "#a846b9"
            hl_constant = "#6e59d9"
            hl_keyword = "#3f6ec6"
            hl_string = "#1c7d4d"

        h_color = heading_color(p_primary["main"], is_dark_scheme)
        logo_cfg = PDF_LOGO_CONFIG.get(p_scheme, PDF_LOGO_CONFIG["default"])
        hide_logo_class = logo_cfg["hide_class"]

        lines.append(
            f"""@media print {{
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
  .mermaid-{"slate" if is_dark_scheme else "default"} {{ display: none !important; }}
}}"""
        )

    return "\n".join(lines) + "\n"
