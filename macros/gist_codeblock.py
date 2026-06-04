from typing import Optional, Tuple
from pathlib import Path
import re
import logging

import requests
from pygments.lexers import guess_lexer, TextLexer

log = logging.getLogger("mkdocs.macros.gist_codeblock")

_EXT_TO_LANG = {
    ".sh": "bash",
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".css": "css",
    ".scss": "scss",
    ".html": "html",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".php": "php",
    ".rb": "ruby",
    ".sql": "sql",
    ".md": "markdown",
    ".dockerfile": "dockerfile",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".psd1": "powershell",
}

_PYGMENTS_TO_MD = {
    "python": "python",
    "python3": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "bash": "bash",
    "console": "bash",
    "shell": "bash",
    "sh": "bash",
    "ruby": "ruby",
    "php": "php",
    "go": "go",
    "rust": "rust",
}


def _get_raw_url(gist_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Gist URL から (raw_url, filename, error) を返す。"""
    if gist_url.startswith("https://gist.githubusercontent.com/"):
        filename = gist_url.split("/")[-1]
        return gist_url, filename, None

    m = re.match(r"https://gist\.github\.com/([^/]+)/([a-f0-9]+)", gist_url)
    if not m:
        return None, None, "Invalid Gist URL format"

    username, gist_id = m.groups()
    try:
        resp = requests.get(f"https://gist.github.com/{username}/{gist_id}", timeout=10)
        if resp.status_code != 200:
            return None, None, f"Failed to fetch Gist: HTTP {resp.status_code}"
        raw_m = re.search(r'href="(/[^/]+/[^/]+/raw/[^"]+)"', resp.text)
        if raw_m:
            raw_path = raw_m.group(1)
            raw_url = f"https://gist.githubusercontent.com{raw_path}"
            return raw_url, raw_path.split("/")[-1], None
        return None, None, "Could not find raw file URL in Gist"
    except requests.RequestException as e:
        return None, None, f"Request error: {e}"


def _detect_lang(content: str, filename: Optional[str]) -> str:
    if filename:
        ext = Path(filename).suffix.lower()
        if ext in _EXT_TO_LANG:
            return _EXT_TO_LANG[ext]
    try:
        lexer = guess_lexer(content)
        if isinstance(lexer, TextLexer):
            return "text"
        name = lexer.aliases[0] if lexer.aliases else lexer.name.lower()
        return _PYGMENTS_TO_MD.get(name, "text")
    except Exception:
        return "text"


def create_gist_codeblock(
    gist_url: str, indent: int = 0, ext: Optional[str] = None
) -> str:
    raw_url, filename, error = _get_raw_url(gist_url)
    if error or raw_url is None:
        return f"Error: {error or 'Failed to get raw URL'}"

    try:
        resp = requests.get(raw_url, timeout=10)
        if resp.status_code != 200:
            return f"Error: Failed to fetch Gist content: HTTP {resp.status_code}"
        content = resp.text
    except requests.RequestException as e:
        return f"Error fetching Gist content: {e}"

    lang = ext or _detect_lang(content, filename)

    content = (
        content.replace("\\$", "$")
        .replace("\\`", "`")
        .replace("\\{", "{")
        .replace("\\}", "}")
    )
    pad = " " * (4 * indent)
    lines = [
        "",
        f"{pad}```{lang}",
        *[f"{pad}{line}" for line in content.splitlines()],
        f"{pad}```",
        "",
    ]
    return "\n".join(lines)


def define_env(env) -> None:
    @env.macro
    def gist_codeblock(
        gist_url: str, indent: int = 0, ext: Optional[str] = None
    ) -> str:
        """Gist URL からコードブロックを生成する。

        Args:
            gist_url: GitHub Gist の URL または raw URL
            indent: インデントレベル（4スペース × レベル）
            ext: 言語を明示的に指定（省略時は自動検出）
        """
        return create_gist_codeblock(gist_url, indent, ext)
