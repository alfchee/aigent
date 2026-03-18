import pytest
from app.core.content_processor import ContentProcessor


@pytest.mark.asyncio
async def test_content_processor_extract_text_success(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("Hola mundo desde MarkItDown")
    processor = ContentProcessor()
    text, error = await processor.extract_text(str(file_path))
    assert error is None
    assert "Hola mundo" in text


@pytest.mark.asyncio
async def test_content_processor_missing_file():
    processor = ContentProcessor()
    text, error = await processor.extract_text("/tmp/no_existe_markitdown.txt")
    assert text == ""
    assert error == "File not found"
