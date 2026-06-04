import re
import logging

log = logging.getLogger("mkdocs.macros.x_twitter_card")

_VALID_PATTERNS = [
    r"https?://(?:mobile\.)?twitter\.com/\w+/status/\d+",
    r"https?://(?:mobile\.)?x\.com/\w+/status/\d+",
]


def create_x_twitter_card(url: str) -> str:
    if not any(re.match(p, url) for p in _VALID_PATTERNS):
        raise ValueError(f"Invalid X/Twitter URL: {url}")

    url = url.replace("x.com", "twitter.com")

    return f"""
    <div class="x-twitter-embed" data-url="{url}">
        <blockquote class="twitter-tweet">
            <a href="{url}"></a>
        </blockquote>
    </div>
    """


def define_env(env) -> None:
    @env.macro
    def x_twitter_card(url: str) -> str:
        """X/Twitter のツイート URL から埋め込みウィジェットを生成する。

        Args:
            url: ツイートの URL（twitter.com または x.com）
        """
        return create_x_twitter_card(url)
