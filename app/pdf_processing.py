"""PDF text extraction + chunking (Step 1 of the pipeline)."""
from pypdf import PdfReader


def extract_text(pdf_path: str) -> str:
    """Extracts all text from a PDF, page by page."""
    reader = PdfReader(pdf_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """
    Splits text into overlapping chunks by character count.
    Overlap keeps context from getting cut mid-idea at chunk boundaries.
    """
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap  # step forward, keeping `overlap` chars in common

    return chunks
