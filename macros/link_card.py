from typing import Optional
from urllib.parse import urlparse
import logging

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("mkdocs.macros.link_card")

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MkDocs link-card)"}


def _fetch_ogp(url: str) -> dict:
    """対象 URL から OGP メタタグ（og:image / og:title / og:description）を取得する。"""
    try:
        resp = requests.get(url, timeout=5, headers=_HEADERS)
        if resp.status_code != 200:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")
        result = {}
        for prop in ("og:image", "og:title", "og:description"):
            tag = soup.find("meta", property=prop)
            if tag and tag.get("content"):
                result[prop] = tag["content"]
        # Twitter Card フォールバック
        if "og:image" not in result:
            tag = soup.find("meta", attrs={"name": "twitter:image"})
            if tag and tag.get("content"):
                result["og:image"] = tag["content"]
        return result
    except Exception as e:
        log.warning("link_card: OGP fetch failed for %s: %s", url, e)
        return {}


def _clean_url(url: str) -> str:
    """先頭末尾の <> を除去し、連続スラッシュを正規化する。"""
    url = url.strip("<>")
    parts = url.split("://", 1)
    if len(parts) > 1:
        scheme, rest = parts
        rest = "/".join(filter(bool, rest.split("/")))
        return f"{scheme}://{rest}"
    return url


def _extract_domain(url: str) -> str:
    return urlparse(url).netloc or url


def create_link_card(
    url: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    image_url: Optional[str] = None,
    domain: Optional[str] = None,
    external: bool = False,
) -> str:
    clean = _clean_url(url)
    display_domain = domain or _extract_domain(clean)

    ogp = _fetch_ogp(clean)

    final_title = title or ogp.get("og:title") or clean
    final_description = (
        description if description is not None else ogp.get("og:description", "")
    )

    if image_url:
        final_image = image_url
    elif not external:
        final_image = ogp.get("og:image", "")
    else:
        final_image = ""

    image_html = (
        f'<img src="{final_image}" alt="{final_title}" class="custom-link-card-image">'
        if final_image
        else ""
    )

    return f"""
<div class="custom-link-card" onclick="window.location='{clean}'" role="link" tabindex="0">
    <div class="custom-link-card-content">
        <div class="custom-link-card-title" aria-label="{final_title}">{final_title}</div>
        <div class="custom-link-card-description">{final_description}</div>
        <a href="{clean}" class="custom-link-card-domain">{display_domain}</a>
    </div>
    {image_html}
</div>
"""


def define_env(env) -> None:
    @env.macro
    def link_card(
        url: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        image_url: Optional[str] = None,
        domain: Optional[str] = None,
        external: bool = False,
    ) -> str:
        """OGP 情報を自動取得してリンクカードを生成する。

        Args:
            url: リンク先 URL
            title: カードのタイトル（省略時は og:title を使用）
            description: 説明文（省略時は og:description を使用）
            image_url: 画像 URL を明示的に指定（省略時は og:image を使用）
            domain: 表示するドメイン名（省略時は URL から自動抽出）
            external: True にすると画像を表示しない
        """
        return create_link_card(
            url=url,
            title=title,
            description=description,
            image_url=image_url,
            domain=domain,
            external=external,
        )
