"""
services/resume_parser.py
─────────────────────────────────────────────────────────────────────────────
TruthLens / Zaira AI — Professional Resume and Document Parser.

Supports:
  • Adobe PDF (.pdf) via pypdf
  • Microsoft Word (.docx) via python-docx
  • Plain text / Markdown (.txt, .md, .rtf)
"""

from __future__ import annotations
import io
import os
import re
from typing import Dict, Any, Optional

def extract_text_from_pdf(file_bytes: bytes) -> tuple[str, int]:
    """Extract plain text and page count from PDF binary data."""
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    page_count = len(reader.pages)
    text_chunks = []
    for idx, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        if page_text.strip():
            text_chunks.append(page_text.strip())
    
    full_text = "\n\n".join(text_chunks)
    return full_text, page_count

def extract_text_from_docx(file_bytes: bytes) -> tuple[str, int]:
    """Extract plain text from Word .docx binary data."""
    import docx
    doc = docx.Document(io.BytesIO(file_bytes))
    text_chunks = []
    
    for p in doc.paragraphs:
        if p.text.strip():
            text_chunks.append(p.text.strip())
            
    for table in doc.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                text_chunks.append(" | ".join(row_cells))
                
    full_text = "\n".join(text_chunks)
    return full_text, 1

def clean_extracted_resume_text(raw_text: str) -> str:
    """Cleans up OCR/PDF formatting artifacts, redundant whitespace, and orphan hyphens."""
    if not raw_text:
        return ""
    # Replace soft hyphens and form feeds
    t = raw_text.replace("\x0c", "\n").replace("\xa0", " ")
    # Replace excessive horizontal whitespace
    t = re.sub(r"[ \t]+", " ", t)
    # Replace excessive vertical whitespace (more than 2 consecutive newlines)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def parse_resume_document(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Parses an uploaded resume file and returns normalized plain text and metadata.
    """
    ext = os.path.splitext(filename.lower())[1]
    
    if not file_bytes or len(file_bytes) == 0:
        return {
            "success": False,
            "filename": filename,
            "text": "",
            "word_count": 0,
            "char_count": 0,
            "page_count": 0,
            "error": "The uploaded resume file is empty (0 bytes)."
        }
        
    try:
        if ext == ".pdf":
            raw_text, pages = extract_text_from_pdf(file_bytes)
        elif ext in [".docx", ".doc"]:
            raw_text, pages = extract_text_from_docx(file_bytes)
        elif ext in [".txt", ".md", ".rtf", ".text"]:
            try:
                raw_text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raw_text = file_bytes.decode("latin-1", errors="ignore")
            pages = 1
        else:
            return {
                "success": False,
                "filename": filename,
                "text": "",
                "word_count": 0,
                "char_count": 0,
                "page_count": 0,
                "error": f"Unsupported file extension '{ext}'. Please upload a PDF (.pdf), Word document (.docx), or plain text (.txt) file."
            }
            
        cleaned_text = clean_extracted_resume_text(raw_text)
        words = re.findall(r"\b\w+\b", cleaned_text)
        
        if not cleaned_text:
            return {
                "success": False,
                "filename": filename,
                "text": "",
                "word_count": 0,
                "char_count": 0,
                "page_count": pages,
                "error": "No text could be extracted from this document. It may be a scanned image-only PDF without embedded OCR text."
            }
            
        return {
            "success": True,
            "filename": filename,
            "text": cleaned_text,
            "word_count": len(words),
            "char_count": len(cleaned_text),
            "page_count": pages,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "filename": filename,
            "text": "",
            "word_count": 0,
            "char_count": 0,
            "page_count": 0,
            "error": f"Failed to parse resume document: {str(e)}"
        }
