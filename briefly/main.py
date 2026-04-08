"""
Blog-to-PDF API
FastAPI app: accepts blog URL + brand doc, returns structured preview + base64 PDF.
"""

import base64
import json
import os
import re
import tempfile
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Form, File, UploadFile, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()

# Import our modules
from scraper import fetch_blog
from extractor import extract_brief
from pdf_generator import generate_pdf

# For document parsing (reuse web-scanner logic)
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = FastAPI(
    title="briefly",
    description="Turn blog posts into branded executive briefs.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Pydantic Models ────────────────────────────────────────────────────────

class LogoPathRequest(BaseModel):
    logo_path: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "blog-to-pdf"}


@app.post("/api/validate-logo-path")
async def validate_logo_path(request: LogoPathRequest):
    """
    Validate that a logo file path exists and is readable.
    Returns: { valid: bool, message: str }
    """
    try:
        logo_path = request.logo_path

        if not logo_path:
            return {"valid": False, "message": "No logo path provided"}

        # Check if file exists and is readable
        if os.path.exists(logo_path) and os.path.isfile(logo_path):
            # Verify it's an image file
            valid_extensions = ('.png', '.jpg', '.jpeg', '.svg')
            if logo_path.lower().endswith(valid_extensions):
                return {"valid": True, "message": "Logo file found"}
            else:
                return {"valid": False, "message": "File is not a valid image format (PNG, JPG, SVG)"}
        else:
            return {"valid": False, "message": f"File not found: {logo_path}"}

    except Exception as e:
        return {"valid": False, "message": f"Error validating logo path: {str(e)}"}


@app.post("/api/detect-branding")
async def detect_branding(blog_url: str = Form(...)):
    """
    Auto-detect company name and website from blog URL.
    FAST & SIMPLE: Just extract from domain, no logo/colors/fonts (unreliable).
    Returns: { company_name, company_website, status }
    """
    from scraper import fetch_blog
    from urllib.parse import urlparse
    import requests
    from bs4 import BeautifulSoup

    try:
        parsed_url = urlparse(blog_url)
        # Use domain from blog URL exactly as-is - NO manipulation
        domain_full = parsed_url.netloc.replace("www.", "")
        domain_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        # Company website = domain URL (exact, no guessing)
        company_website = domain_url

        # Default company name from first part of domain (fallback)
        company_name = domain_full.split(".")[0].capitalize()

        # Better extraction: og:site_name > title-suffix pattern > domain default
        try:
            blog_data = await fetch_blog(blog_url)
            if blog_data.get("status") != "error":
                # 1st choice: og:site_name meta tag (cleanest source)
                if blog_data.get("og_site_name"):
                    raw_site = blog_data["og_site_name"]
                    # Strip tagline suffix: "Company | Tagline" → "Company"
                    if " | " in raw_site:
                        raw_site = raw_site.split(" | ")[0].strip()
                    elif " - " in raw_site:
                        raw_site = raw_site.split(" - ")[0].strip()
                    company_name = raw_site
                else:
                    # 2nd choice: company name after " | " or " - " in page title
                    blog_title = blog_data.get("title", "")
                    if " | " in blog_title:
                        company_name = blog_title.split(" | ")[-1].strip()
                    elif " - " in blog_title:
                        parts = blog_title.split(" - ")
                        # Take last part only if it looks like a company (short, no spaces run-on)
                        last = parts[-1].strip()
                        if last and len(last) < 50:
                            company_name = last
        except:
            pass

        return {
            "status": "success",
            "company_name": company_name,
            "company_website": company_website
        }

    except Exception as e:
        print(f"Branding detection error: {e}")
        return {
            "status": "error",
            "company_name": None,
            "company_website": None,
            "error": str(e)
        }


@app.post("/api/generate")
async def generate(
    blog_url: str = Form(...),
    page_preference: str = Form("2"),
    brand_docs: List[UploadFile] = File(default=[]),
    brand_config_json: str = Form(default=""),
    logo: Optional[UploadFile] = File(default=None),
):
    """
    Main endpoint. Accepts blog URL + optional brand docs (multiple allowed).
    Returns JSON: { status, pdf_b64, filename, extracted }
    """
    # ── 1. Fetch blog ─────────────────────────────────────────────────────────
    blog_data = await fetch_blog(blog_url)
    if blog_data.get("status") == "error":
        raise HTTPException(
            status_code=422,
            detail=f"Could not fetch blog: {blog_data.get('error', 'Unknown error')}"
        )

    blog_text  = blog_data.get("text", "")
    blog_title = blog_data.get("title", "")
    inline_images = blog_data.get("inline_images", [])

    if len(blog_text.split()) < 50:
        raise HTTPException(
            status_code=422,
            detail="Could not extract enough text from the blog URL. "
                   "The page may require JavaScript or block scrapers."
        )

    # ── 2. Extract brand docs text (combine all uploaded docs) ────────────────
    brand_doc_text = ""
    valid_docs = [d for d in brand_docs if d and d.filename]
    for brand_doc in valid_docs:
        tmp = tempfile.NamedTemporaryFile(
            suffix=os.path.splitext(brand_doc.filename)[1],
            delete=False
        )
        try:
            content = await brand_doc.read()
            tmp.write(content)
            tmp.flush()
            tmp.close()
            doc_text = _extract_doc_text(tmp.name, brand_doc.filename)
            if doc_text:
                brand_doc_text += f"\n\n--- {brand_doc.filename} ---\n{doc_text}"
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

    # ── 3. Parse custom brand config if provided ─────────────────────────────
    custom_brand = {}
    if brand_config_json and brand_config_json.strip():
        try:
            custom_brand = json.loads(brand_config_json)
            # Validate the config
            from pdf_generator import validate_brand_config
            is_valid, error_msg = validate_brand_config(custom_brand)
            if not is_valid:
                raise HTTPException(status_code=422, detail=f"Invalid brand config: {error_msg}")
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="brand_config_json must be valid JSON")

    # ── 3b. Handle logo (from branding JSON or upload) ─────────────────────────
    logo_path = None

    # First, check if logo_file is specified in branding JSON
    if "logo_file" in custom_brand and custom_brand["logo_file"]:
        logo_file_path = custom_brand["logo_file"]
        if os.path.exists(logo_file_path):
            logo_path = logo_file_path
            print(f"✓ Using logo from branding file: {logo_path}")
        else:
            print(f"⚠ Logo file specified in branding JSON not found: {logo_file_path}")

    # If no logo from JSON, try uploaded logo
    if not logo_path and logo and logo.filename:
        ext = os.path.splitext(logo.filename)[1].lower()
        if ext not in {".png", ".svg", ".jpg", ".jpeg"}:
            raise HTTPException(status_code=422, detail="Logo must be PNG, SVG, JPG, or JPEG")

        tmp_logo = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        try:
            content = await logo.read()
            tmp_logo.write(content)
            tmp_logo.flush()
            tmp_logo.close()
            logo_path = tmp_logo.name
            print(f"✓ Using uploaded logo: {logo_path}")
        except Exception as e:
            try:
                os.unlink(tmp_logo.name)
            except:
                pass
            # Non-fatal: logo upload failed, continue without it
            pass

    # Set logo path in brand config if found
    if logo_path:
        custom_brand["company_logo_path"] = logo_path

    # ── 4. LLM extraction ─────────────────────────────────────────────────────
    pages = int(page_preference) if page_preference in ("2", "3") else 2

    try:
        extracted = await extract_brief(
            blog_text=blog_text,
            blog_title=blog_title,
            brand_doc_text=brand_doc_text,
            page_preference=pages,
            inline_images=inline_images
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI extraction failed: {str(e)}")

    # ── 4. Override elevator pitch + CTA with verbatim brand doc content ─────
    # The LLM tends to paraphrase. If we can find the elevator pitch and CTA
    # directly in the brand doc text, inject them verbatim — but only if the
    # extracted text actually looks like real prose (quality gate).
    verbatim = _extract_brand_verbatim(brand_doc_text)
    if verbatim.get("elevator_pitch_body") and _looks_like_prose(verbatim["elevator_pitch_body"]):
        extracted["elevator_pitch_body"] = verbatim["elevator_pitch_body"]
    if verbatim.get("elevator_pitch_header"):
        extracted["elevator_pitch_header"] = verbatim["elevator_pitch_header"]
    if verbatim.get("cta_text"):
        extracted["cta_text"] = verbatim["cta_text"]
    if verbatim.get("cta_url"):
        extracted["cta_url"] = verbatim["cta_url"]

    # ── 4a. Boilerplate synthesis: dedicated LLM call ────────────────────────
    # When a brand doc is provided, always run a focused synthesis call whose
    # only job is the boilerplate paragraph. The main extraction prompt buries
    # this task inside a large JSON job and gets it wrong on messy brand docs.
    # Exception: if regex verbatim extraction already found clean prose, keep it.
    verbatim_body = verbatim.get("elevator_pitch_body", "")
    verbatim_is_clean = bool(verbatim_body) and _looks_like_prose(verbatim_body)
    if brand_doc_text and not verbatim_is_clean:
        company_name_hint = (custom_brand.get("company_name") or
                             custom_brand.get("colors", {}).get("company_name") or "")
        synthesized = await _synthesize_boilerplate_llm(brand_doc_text, company_name_hint)
        if synthesized:
            extracted["elevator_pitch_body"] = synthesized

    # ── 4b. CTA fallback chain ─────────────────────────────────────────────────
    # Priority: Brand doc CTA > Blog CTA > "Learn more" → brand home page
    blog_cta_text = blog_data.get("cta_text", "")
    blog_cta_url  = blog_data.get("cta_url", "")
    brand_home_url = _extract_root_domain(blog_url)

    # If brand doc didn't provide CTA, try blog's CTA first
    if not extracted.get("cta_url"):
        if blog_cta_url:
            extracted["cta_url"]  = blog_cta_url
            if not extracted.get("cta_text"):
                extracted["cta_text"] = blog_cta_text or "Read more"
        elif brand_home_url:
            # Fallback: "Learn more" → brand home page
            extracted["cta_url"]  = brand_home_url
            extracted["cta_text"] = "Learn more"

    # ── 4c. Resolve logo_bg_mode → logo_bg_color ─────────────────────────────────
    # The UI sends 'dark' or 'light' as a human-readable hint.
    # We translate that into the actual brand color here, before PDF generation.
    logo_bg_mode = custom_brand.pop("logo_bg_mode", None)  # remove from config
    if logo_bg_mode == "dark":
        # User says logo needs dark bg: use primary (we'll check it's actually dark)
        custom_brand["logo_bg_color"] = custom_brand.get("colors", {}).get("primary") or \
                                         custom_brand.get("primary") or "primary"
    elif logo_bg_mode == "light":
        # User says logo needs light bg: use text_light
        custom_brand["logo_bg_color"] = custom_brand.get("colors", {}).get("text_light") or \
                                         custom_brand.get("text_light") or "text_light"
    # If logo_bg_mode is absent or 'auto', logo_bg_color stays unset → detection runs

    # ── 5. Merge brand configs (priority: custom_brand > verbatim from docs > defaults) ────
    # If custom brand was provided, it takes priority over brand doc extraction
    merged_brand = custom_brand.copy() if custom_brand else {}

    # Get verbatim brand info from docs (elevator pitch, CTA) if no custom config
    # But don't override custom config values
    if verbatim:
        if not merged_brand.get("elevator_pitch_body") and verbatim.get("elevator_pitch_body"):
            merged_brand["elevator_pitch_body"] = verbatim["elevator_pitch_body"]
        if not merged_brand.get("elevator_pitch_header") and verbatim.get("elevator_pitch_header"):
            merged_brand["elevator_pitch_header"] = verbatim["elevator_pitch_header"]

    # ── 6. Generate PDF with custom branding ────────────────────────────────
    extracted["blog_url"] = blog_data.get("url", "")
    try:
        pdf_bytes = generate_pdf(extracted, brand_config=merged_brand if merged_brand else None, page_preference=pages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    # ── 6. Build filename ──────────────────────────────────────────────────────
    # Use company name and blog title in filename
    company_name = (merged_brand.get("company_name") or
                   extracted.get("company_name", "brief")).lower()
    company_slug = re.sub(r"[^a-z0-9]+", "-", company_name).strip("-")[:20]
    title_slug = re.sub(r"[^a-z0-9]+", "-", extracted.get("title", "brief").lower()).strip("-")[:40]
    filename = f"{company_slug}-brief-{title_slug}.pdf"

    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    # ── 6b. Cleanup temp logo file ────────────────────────────────────────────
    if logo_path:
        try:
            os.unlink(logo_path)
        except:
            pass

    # Always use brand config company_name if available (overrides auto-detected)
    brand_company = (merged_brand.get("company_name") or
                     custom_brand.get("company_name") or
                     extracted.get("company_name", ""))
    extracted["company_name"] = brand_company

    return {
        "status": "success",
        "pdf_b64": pdf_b64,
        "filename": filename,
        "extracted": extracted,
        "branding_config": merged_brand if merged_brand else {},
        "blog_meta": {
            "url": blog_data.get("url"),
            "title": blog_title,
            "word_count": blog_data.get("word_count", 0),
            "inline_images": inline_images
        }
    }


@app.post("/api/regenerate-with-image")
async def regenerate_with_image(
    brief_json: str = Form(...),
    section_index: int = Form(0),
    image_file: Optional[UploadFile] = File(default=None),
    brand_config_json: str = Form(default=""),
):
    """
    Regenerate PDF with a user-provided image embedded at a specific section.
    Supports optional custom branding.
    """
    import json

    try:
        data = json.loads(brief_json)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid brief JSON")

    # Parse custom brand config if provided
    custom_brand = {}
    if brand_config_json and brand_config_json.strip():
        try:
            custom_brand = json.loads(brand_config_json)
            from pdf_generator import validate_brand_config
            is_valid, error_msg = validate_brand_config(custom_brand)
            if not is_valid:
                raise HTTPException(status_code=422, detail=f"Invalid brand config: {error_msg}")
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="brand_config_json must be valid JSON")

    image_paths = {}
    if image_file and image_file.filename:
        ext = os.path.splitext(image_file.filename)[1].lower()
        if ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            raise HTTPException(status_code=422, detail="Unsupported image format")

        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        try:
            content = await image_file.read()
            tmp.write(content)
            tmp.flush()
            tmp.close()
            image_paths[section_index] = tmp.name

            pdf_bytes = generate_pdf(data, image_paths=image_paths,
                                    brand_config=custom_brand if custom_brand else None)
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
    else:
        pdf_bytes = generate_pdf(data, brand_config=custom_brand if custom_brand else None)

    # Use company name and blog title in filename
    company_name = (custom_brand.get("company_name") or
                   data.get("company_name", "brief")).lower()
    company_slug = re.sub(r"[^a-z0-9]+", "-", company_name).strip("-")[:20]
    title_slug = re.sub(r"[^a-z0-9]+", "-", data.get("title", "brief").lower()).strip("-")[:40]
    filename = f"{company_slug}-brief-{title_slug}.pdf"

    return {
        "status": "success",
        "pdf_b64": base64.b64encode(pdf_bytes).decode("utf-8"),
        "filename": filename
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_root_domain(url: str) -> str:
    """Extract root domain from URL (e.g., https://www.example.com/blog/post → https://www.example.com)"""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc
        if netloc:
            return f"{scheme}://{netloc}"
    except Exception:
        pass
    return ""


def _looks_like_prose(text: str) -> bool:
    """
    Quality gate: return True only if `text` looks like genuine marketing prose.
    Rejects OCR garbage, bullet-point dumps, repeated sentences, and encoding artifacts.
    """
    if not text:
        return False
    words = text.split()
    if len(words) < 25:
        return False
    # Must contain at least one sentence-ending punctuation
    if not any(c in text for c in ".!?"):
        return False
    # Alpha characters should make up >= 60% of non-space characters
    stripped = text.replace(" ", "")
    if stripped:
        alpha_ratio = sum(1 for c in stripped if c.isalpha()) / len(stripped)
        if alpha_ratio < 0.60:
            return False
    # Average word length should be between 3-14 characters
    avg_word_len = sum(len(w.strip(".,;:!?\"'()-")) for w in words) / len(words)
    if avg_word_len < 3.0 or avg_word_len > 14.0:
        return False
    # No more than 30% of "words" should be non-alphabetic tokens
    non_alpha_tokens = sum(1 for w in words if not any(c.isalpha() for c in w))
    if non_alpha_tokens / len(words) > 0.30:
        return False
    # Reject texts with duplicate sentences (sign of a list/fragment dump)
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 20]
    if len(sentences) >= 2:
        lowered = [s.lower() for s in sentences]
        unique = set(lowered)
        if len(unique) < len(lowered):  # any exact duplicate sentence
            return False
        # Also reject if any two sentences share >80% of their words (near-duplicate)
        for i in range(len(lowered)):
            for j in range(i + 1, len(lowered)):
                w1 = set(lowered[i].split())
                w2 = set(lowered[j].split())
                if w1 and w2:
                    overlap = len(w1 & w2) / min(len(w1), len(w2))
                    if overlap > 0.80:
                        return False
    # Reject if more than 40% of lines look like bullet points
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        bullet_lines = sum(1 for l in lines if re.match(r"^[-*•]\s|\d+\.\s", l))
        if bullet_lines / len(lines) > 0.40:
            return False
    return True


async def _synthesize_boilerplate_llm(brand_doc_text: str, company_name: str = "") -> str:
    """
    Dedicated LLM call whose ONLY job is to produce a clean company boilerplate paragraph.
    Called as a fallback when regex extraction and the main LLM extraction both return
    something that fails the prose quality gate.
    Returns the paragraph text, or empty string on failure.
    """
    try:
        import litellm
    except ImportError:
        return ""

    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    company_hint = f" The company name is {company_name}." if company_name else ""

    prompt = (
        "You are a copywriter. Below is a brand or messaging document.\n\n"
        "Your task: Extract or write the company's 'About' boilerplate paragraph - "
        "the kind of 2-3 sentence description that appears at the bottom of a press release.\n\n"
        "Requirements:\n"
        "- Written in THIRD PERSON\n"
        "- Starts with the company name\n"
        "- 40-80 words, single prose paragraph\n"
        "- No bullet points, no internal guidance language, no headings\n"
        "- Describes what the company does, who it serves, and its value\n"
        "- If you cannot find a press-release-style paragraph, synthesize one from the document context\n\n"
        f"Company hint:{company_hint}\n\n"
        "RETURN ONLY THE PARAGRAPH TEXT. No labels, no quotes, no explanation.\n\n"
        f"Brand document:\n{brand_doc_text[:6000]}"
    )

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=200,
        )
        result = response.choices[0].message.content.strip()
        # Strip any accidental labels like "Boilerplate:" or quotes
        result = re.sub(r'^(boilerplate|about|company description|overview)[:\s]+', '', result, flags=re.IGNORECASE)
        result = result.strip('"\'')
        # Light gate only: must have at least 15 words and not be pure bullet points
        words = result.split()
        bullet_lines = sum(1 for l in result.splitlines() if re.match(r'^\s*[-*•]|\d+\.', l))
        total_lines = max(1, len([l for l in result.splitlines() if l.strip()]))
        if len(words) >= 15 and bullet_lines / total_lines < 0.5:
            return result
    except Exception:
        pass
    return ""


def _extract_brand_verbatim(brand_doc_text: str) -> dict:
    """
    Extract elevator pitch and CTA from brand doc text verbatim (no LLM).
    Looks for common patterns: sections labelled "elevator pitch", "about us",
    "why us", "our pitch", and CTA links/buttons.

    Returns dict with keys: elevator_pitch_header, elevator_pitch_body, cta_text, cta_url
    (any may be empty string if not found).
    """
    if not brand_doc_text:
        return {}

    result = {}

    # ── Elevator pitch / Boilerplate ───────────────────────────────────────────
    # Try each pattern in priority order; accept first extraction that passes validation.
    search_patterns = [
        # Priority 1: explicit "boilerplate" label
        re.compile(r"(?m)^[#*_\s]*boilerplate[#*_\s:]*", re.IGNORECASE),
        # Priority 2: narrative / expanded narrative (common in brand decks — very specific)
        re.compile(
            r"(?m)^[#*_\s]*"
            r"(expanded\s+narrative|expanded\s+messaging|company\s+narrative|"
            r"brand\s+narrative|our\s+narrative|full\s+description|long\s+description|"
            r"press\s+release|about\s+the\s+company|company\s+background)"
            r"[#*_\s:]*",
            re.IGNORECASE
        ),
        # Priority 3: specific pitch/about labels (NOT "about\s+\w+" — too broad)
        re.compile(
            r"(?m)^[#*_\s]*"
            r"(elevator\s+pitch|about\s+us|our\s+story|"
            r"who\s+we\s+are|what\s+we\s+do|company\s+overview|"
            r"our\s+pitch|one[- ]liner|value\s+prop(?:osition)?|"
            r"company\s+description|positioning\s+statement|brand\s+statement)"
            r"[#*_\s:]*",
            re.IGNORECASE
        ),
    ]

    def _extract_body_after(text, match_obj):
        """Extract the prose paragraph immediately following a section header."""
        after = text[match_obj.end():]
        lines = after.split("\n")
        body_lines = []
        blank_streak = 0
        char_count = 0
        MAX_CHARS = 800

        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_streak += 1
                # Once we have a full paragraph (40+ words), stop at any blank line
                if blank_streak >= 1 and len(" ".join(body_lines).split()) >= 40:
                    break
                # Otherwise stop at double blank line — that's a new section
                if blank_streak >= 2:
                    break
                continue
            blank_streak = 0

            # Stop at markdown headings
            if re.match(r"^#{1,6}\s", stripped):
                break
            # Stop at all-caps standalone heading (e.g. "CTA", "KEY MESSAGES", "BOILERPLATE")
            if re.match(r"^[A-Z][A-Z0-9 \-/]{2,}:?\s*$", stripped):
                break
            # Stop at common doc section labels (even mixed-case, as first line after blank)
            if blank_streak == 0 and len(body_lines) > 0:
                if re.match(
                    r"^(CTA|Call[- ]to[- ]Action|Key Messages?|Messaging|Positioning|"
                    r"Elevator Pitch|Short Pitch|Long Pitch|Short[- ]Form|Long[- ]Form|"
                    r"\w+ Pitch|One[- ]liner|Value Prop|Why |About |Boilerplate|"
                    r"Company (Info|Description|Overview)|Our (Pitch|Story)|"
                    r"Brand (Statement|Voice)|Social|Email|Subject Line)",
                    stripped, re.IGNORECASE
                ):
                    break

            # Skip leading bullet/numbered lines (not prose yet)
            if re.match(r"^[-*•]\s+\S|^\d+\.\s+\S", stripped) and len(body_lines) == 0:
                continue

            body_lines.append(stripped)
            char_count += len(stripped) + 1
            if char_count > MAX_CHARS:
                break

        candidate = " ".join(body_lines).strip()
        # Strip leading page-number artifacts (e.g. "10 Acme..." → "Acme...")
        candidate = re.sub(r"^\d+\s+", "", candidate)
        # Validate: at least 40 words, not mostly bullet points
        word_count = len(candidate.split())
        bullet_lines = sum(1 for l in body_lines if re.match(r"^[-*•]|\d+\.", l))
        if word_count >= 40 and bullet_lines < len(body_lines) * 0.5:
            return candidate
        return ""

    best_body = ""
    for pattern in search_patterns:
        for m in pattern.finditer(brand_doc_text):
            candidate = _extract_body_after(brand_doc_text, m)
            if candidate:
                best_body = candidate
                break
        if best_body:
            break

    if best_body:
        result["elevator_pitch_body"] = best_body

    # ── CTA text + URL ─────────────────────────────────────────────────────────
    # Look for CTA labels like "CTA:", "Call to action:", "Button:", "Link:"
    cta_label_pattern = re.compile(
        r"(?i)\b(cta|call[- ]to[- ]action|button|primary\s+cta|demo\s+link|"
        r"request\s+a\s+demo|book\s+a\s+demo|schedule\s+a\s+demo|get\s+started)"
        r"\s*[:\-]?\s*(.+)",
        re.IGNORECASE
    )
    url_pattern = re.compile(r"https?://[^\s\)\]\"'<>]+")

    for line in brand_doc_text.split("\n"):
        m = cta_label_pattern.search(line)
        if m:
            remainder = m.group(2).strip()
            # If the remainder contains a URL, split text from URL
            url_m = url_pattern.search(remainder)
            if url_m:
                if not result.get("cta_url"):
                    result["cta_url"] = url_m.group(0).rstrip(".,;)")
                text_part = remainder[:url_m.start()].strip(" -:")
                if text_part and not result.get("cta_text"):
                    result["cta_text"] = text_part
            elif remainder and not result.get("cta_text"):
                result["cta_text"] = remainder[:80]

    # Fallback: look for any URL that suggests a demo/contact page
    if not result.get("cta_url"):
        for url_m in url_pattern.finditer(brand_doc_text):
            url = url_m.group(0).rstrip(".,;)")
            if re.search(r"(demo|contact|get[-_]started|book|schedule|request)", url, re.I):
                result["cta_url"] = url
                break

    return result


def _extract_doc_text(file_path: str, original_filename: str) -> str:
    """Extract plain text from a document file (PDF, DOCX, TXT)."""
    ext = os.path.splitext(original_filename.lower())[1]

    try:
        if ext == ".pdf":
            import pypdf
            import re as _re
            reader = pypdf.PdfReader(file_path)
            pages_text = []
            for p in reader.pages:
                t = p.extract_text(extraction_mode="layout")
                if t:
                    # Fix hyphen-space artifacts from layout mode: "zero- trust" → "zero-trust"
                    t = _re.sub(r'(\w)-\s+(\w)', r'\1-\2', t)
                    pages_text.append(t)
            return "\n\n".join(pages_text)
        elif ext in {".docx", ".doc"}:
            import docx
            doc = docx.Document(file_path)
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        else:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
    except Exception:
        return ""
