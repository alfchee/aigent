from app.skills.registry import registry
from app.skills.web_browse import web_browse, WebBrowseArgs, WebBrowseResult
from app.skills.smart_search import smart_search, SmartSearchArgs, SmartSearchResult
from app.skills.file_tools import list_artifacts, read_artifact, ListArtifactsArgs, ReadArtifactArgs


def _register_skills() -> None:
    registry.register(
        name="web_browse",
        description=(
            "Browse a URL using headless Chromium. Returns page title, cleaned text content "
            "(up to 10,000 chars), and up to 20 HTTP links found on the page. "
            "Use this when you need to read content from a specific web page."
        ),
        args_schema=WebBrowseArgs,
    )(web_browse)

    registry.register(
        name="smart_search",
        description=(
            "Search the web using Brave Search (with API key) or DuckDuckGo fallback. "
            "Returns title, URL, and snippet for each result. "
            "Supports web, news, and video search types."
        ),
        args_schema=SmartSearchArgs,
    )(smart_search)

    registry.register(
        name="list_artifacts",
        description=(
            "List all artifact files in /workspace/sessions/{session_id}/artifacts. "
            "Returns filename, size, and last-modified timestamp for each file."
        ),
        args_schema=ListArtifactsArgs,
    )(list_artifacts)

    registry.register(
        name="read_artifact",
        description=(
            "Read the content of an artifact file from /workspace/sessions/{session_id}/artifacts/{filename}. "
            "Returns up to 500,000 characters of the file content."
        ),
        args_schema=ReadArtifactArgs,
    )(read_artifact)


_register_skills()
