"""PDF 内 SVG アイコンの fill 修正"""

import logging

log = logging.getLogger("mkdocs.hooks.build_config")


def set_fill_style(tag, fill_color: str) -> None:
    existing = tag.get("style", "").strip().rstrip(";")
    parts = [
        p for p in existing.split(";") if p.strip() and not p.strip().startswith("fill")
    ]
    parts.append(f"fill: {fill_color}")
    tag["style"] = "; ".join(p.strip() for p in parts) + ";"


def fix_source_file_icon_fill(article, fill_color: str) -> None:
    """md-source-file__fact 内の SVG アイコンに fill をインラインスタイルで直接設定する。"""
    for fact_span in article.find_all(class_="md-source-file__fact"):
        for icon_span in fact_span.find_all(class_="md-icon"):
            for svg in icon_span.find_all("svg"):
                set_fill_style(svg, fill_color)
                for path in svg.find_all("path"):
                    set_fill_style(path, fill_color)


def fix_inline_icon_fill(article, fill_color: str) -> None:
    """全インラインアイコン（span.twemoji svg）に fill を設定する。

    グリッドカード固有のアイコンはこの後で上書きするため、先に呼び出す。
    fix_twemoji 変換後は fix_converted_inline_icon_fill を使用する。
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
            f"fix_inline_icon_fill: {svg_count} SVG(s) updated → fill={fill_color}"
        )
    else:
        log.debug(f"fix_inline_icon_fill: no SVG found (fill={fill_color})")


def fix_grid_card_icon_fill(article, fill_color: str) -> None:
    """グリッドカード先頭行のアイコン SVG に fill を SVG 属性として直接設定する。

    fix_twemoji 変換後は fix_converted_twemoji_fill を使用する。
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
            f"fix_grid_card_icon_fill: {svg_count} SVG(s) updated → fill={fill_color}"
        )
    else:
        log.debug(f"fix_grid_card_icon_fill: no SVG found (fill={fill_color})")


def fix_grid_card_arrow_fill(article, fill_color: str) -> None:
    """グリッドカードリンク行（p:last-child）の矢印アイコン SVG に fill を設定する。

    fix_twemoji 変換後は fix_converted_arrow_fill を使用する。
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
            f"fix_grid_card_arrow_fill: {svg_count} SVG(s) updated → fill={fill_color}"
        )
    else:
        log.debug(f"fix_grid_card_arrow_fill: no SVG found (fill={fill_color})")


def recolor_converted_spans(spans, fill_color: str, label: str = "") -> int:
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
                log.warning(f"recolor_converted_spans ({label}): {e}")
    return count


def fix_converted_inline_icon_fill(soup, fill_color: str) -> int:
    """全インラインアイコン（span.twemoji）の base64 SVG img に fill を設定する。"""
    count = recolor_converted_spans(
        list(soup.find_all("span", class_="twemoji")), fill_color, "inline"
    )
    log.info(
        f"fix_converted_inline_icon_fill: {count} img(s) updated → fill={fill_color}"
    )
    return count


def fix_converted_twemoji_fill(soup, fill_color: str) -> int:
    """グリッドカードタイトルアイコン（span.twemoji.lg.middle）の base64 SVG img に fill を設定する。"""
    count = recolor_converted_spans(
        soup.select("span.twemoji.lg.middle"), fill_color, "title"
    )
    log.info(f"fix_converted_twemoji_fill: {count} img(s) updated → fill={fill_color}")
    return count


def fix_converted_arrow_fill(soup, fill_color: str) -> int:
    """グリッドカードリンク行（p:last-child）の base64 SVG img に fill を設定する。"""
    spans = [
        span
        for p in soup.select(".grid.cards li > p:last-child")
        for span in p.find_all("span", class_="twemoji")
    ]
    count = recolor_converted_spans(spans, fill_color, "arrow")
    log.info(f"fix_converted_arrow_fill: {count} img(s) updated → fill={fill_color}")
    return count
