"""PDF text extraction service using pdfplumber."""

import pdfplumber


def extract_text_from_pdf(file_path: str) -> tuple[str, int]:
    """Extract text from a PDF file.

    Returns:
        Tuple of (extracted_text, page_count)
    """
    pages_text = []
    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                pages_text.append(f"--- Page {i + 1} ---\n{text}")

    full_text = "\n\n".join(pages_text)
    return full_text, page_count
