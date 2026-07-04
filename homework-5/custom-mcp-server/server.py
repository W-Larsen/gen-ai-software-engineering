"""Custom MCP server built with FastMCP.

Exposes the contents of ``lorem-ipsum.md`` in two ways:

* a **Resource** (URI ``lorem://ipsum``) that Claude can read from, and
* a **Tool** (``read``) that Claude can call as an action.

Both accept an optional ``word_count`` parameter (default ``30``) and return
exactly that many words from the source file.
"""

from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("Lorem Ipsum Server")

# Path to the source text, resolved relative to this file so the server works
# no matter what the current working directory is when it is launched.
LOREM_FILE = Path(__file__).parent / "lorem-ipsum.md"

DEFAULT_WORD_COUNT = 30


def _read_words(word_count: int = DEFAULT_WORD_COUNT) -> str:
    """Return the first ``word_count`` words from ``lorem-ipsum.md``.

    If ``word_count`` is larger than the number of words available, the whole
    file is returned. Non-positive values yield an empty string.
    """
    if word_count <= 0:
        return ""

    text = LOREM_FILE.read_text(encoding="utf-8")
    words = text.split()
    return " ".join(words[:word_count])


@mcp.resource("lorem://ipsum")
def lorem_resource_default() -> str:
    """Resource URI that returns the default ``30`` words from ``lorem-ipsum.md``.

    Resources are URIs that Claude can read from (e.g. files or APIs). This one
    reads from the local ``lorem-ipsum.md`` file and uses the default
    ``word_count`` of 30.
    """
    return _read_words(DEFAULT_WORD_COUNT)


@mcp.resource("lorem://ipsum/{word_count}")
def lorem_resource(word_count: int = DEFAULT_WORD_COUNT) -> str:
    """Resource template that returns ``word_count`` words from ``lorem-ipsum.md``.

    Reading ``lorem://ipsum/50`` returns the first 50 words, etc.
    """
    return _read_words(word_count)


@mcp.tool()
def read(word_count: int = DEFAULT_WORD_COUNT) -> str:
    """Read ``word_count`` words (default 30) from the lorem-ipsum resource.

    Tools are actions Claude can call to perform operations. This tool reads the
    underlying file and returns exactly ``word_count`` words.
    """
    return _read_words(word_count)


if __name__ == "__main__":
    mcp.run()
