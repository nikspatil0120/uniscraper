# pipeline/pdf_extractor.py
# extract_pdfs_from_page(html: str, base_url: str) -> list[dict]
# Finds PDF links, downloads them, extracts text via pdfplumber.
# Handles failures gracefully — always returns a list, never raises.

import logging
import os
import tempfile

import httpx
import pdfplumber
from bs4 import BeautifulSoup

from config import settings
from utils.url_utils import normalize_url, is_pdf_url
from utils.text_cleaner import truncate_text

logger = logging.getLogger(__name__)

_DOWNLOAD_TIMEOUT = 20.0
_PDF_MAX_CHARS = 6000

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


async def _download_and_extract(pdf_url: str) -> dict:
    """Download a single PDF and extract its text. Returns a result dict."""
    tmp_path = None
    try:
        async with httpx.AsyncClient(
            timeout=_DOWNLOAD_TIMEOUT,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            response = await client.get(pdf_url)
            response.raise_for_status()

            # Verify it's actually a PDF
            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type.lower() and not pdf_url.lower().endswith(".pdf"):
                return {
                    "url": pdf_url,
                    "text": None,
                    "error": f"Unexpected content-type: {content_type}",
                    "pages": 0,
                }

            pdf_bytes = response.content

        # Write to a temp file for pdfplumber
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        with pdfplumber.open(tmp_path) as pdf:
            page_count = len(pdf.pages)
            page_texts = []
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    page_texts.append(extracted)

        raw_text = "\n".join(page_texts)

        # Clean up blank lines
        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
        clean_text = "\n".join(lines)

        # Truncate to stay within LLM context budget
        final_text = truncate_text(clean_text, _PDF_MAX_CHARS)

        return {
            "url": pdf_url,
            "text": final_text,
            "error": None,
            "pages": page_count,
        }

    except Exception as e:
        logger.warning(f"[pdf_extractor] failed to extract {pdf_url}: {e}")
        return {
            "url": pdf_url,
            "text": None,
            "error": str(e),
            "pages": 0,
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


async def extract_pdfs_from_page(html: str, base_url: str) -> list[dict]:
    """
    Find all PDF links in the page HTML, download up to MAX_PDFS,
    extract text from each, and return a list of result dicts.

    Each dict: {"url": str, "text": str|None, "error": str|None, "pages": int}
    """
    soup = BeautifulSoup(html, "lxml")
    pdf_urls: list[str] = []
    seen: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "").strip()
        if not href:
            continue
        normalized = normalize_url(href, base_url)
        if normalized is None:
            continue
        if not is_pdf_url(normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        pdf_urls.append(normalized)

    # Respect the configured limit
    pdf_urls = pdf_urls[: settings.max_pdfs]

    results = []
    for pdf_url in pdf_urls:
        result = await _download_and_extract(pdf_url)
        results.append(result)

    logger.info(
        f"[pdf_extractor] extracted {len(results)} PDFs from {base_url}"
    )
    return results
