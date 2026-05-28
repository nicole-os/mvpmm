"""
pitchplanner - Main FastAPI Application
Two-step campaign builder:
  Step 1 /api/analyze  → analyze + match pubs + suggest waves → user selects targets
  Step 2 /api/campaign → scrape articles + draft personalized pitches → full campaign
"""

import os
from dotenv import load_dotenv
load_dotenv()  # must run before any module that reads env vars (pitcher, publication_finder)

import tempfile
import uuid
import time
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from document_processor import DocumentProcessor, BrandContextBuilder

from pitcher import PRPitcher
from publication_finder import PublicationFinder
from article_scraper import ArticleScraper

app = FastAPI(
    title="pitchplanner",
    description="AI-powered media pitch generator for B2B tech",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ──────────────────────────────────────────────────────────────
# Session store — in-memory, 30-minute TTL
# key: session_id (uuid4 string)
# value: {news_analysis, targets, brand_context, news_content,
#          user_constraints, articles_by_pub, timestamp}
# ──────────────────────────────────────────────────────────────
SESSION_STORE: dict = {}
SESSION_TTL_SECONDS = 1800  # 30 minutes

# In-memory custom publication list — None means use the default PUBLICATIONS constant
CUSTOM_PUBLICATIONS: list | None = None


def _get_session(session_id: str) -> Optional[dict]:
    """Retrieve a session, returning None if missing or expired."""
    session = SESSION_STORE.get(session_id)
    if not session:
        return None
    if time.time() - session["timestamp"] > SESSION_TTL_SECONDS:
        del SESSION_STORE[session_id]
        return None
    return session


def _cleanup_expired_sessions():
    """Remove sessions older than TTL. Called opportunistically."""
    now = time.time()
    expired = [k for k, v in SESSION_STORE.items() if now - v["timestamp"] > SESSION_TTL_SECONDS]
    for k in expired:
        del SESSION_STORE[k]


# ──────────────────────────────────────────────────────────────
# Request model for /api/campaign
# ──────────────────────────────────────────────────────────────
class CampaignRequest(BaseModel):
    session_id: str
    wave_1: Optional[str] = None          # single pub name or null
    wave_2: list[str] = []                # list of pub names
    wave_3: list[str] = []                # list of pub names


# ──────────────────────────────────────────────────────────────
# Shared doc processing helper
# ──────────────────────────────────────────────────────────────
async def _process_docs(docs: list[UploadFile], doc_processor: DocumentProcessor) -> list[dict]:
    """Extract text content from a list of uploaded files."""
    results = []
    for doc in docs:
        if not doc.filename:
            continue
        ext = os.path.splitext(doc.filename)[1]
        content_bytes = await doc.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content_bytes)
            tmp_path = tmp.name
        try:
            extracted = doc_processor.extract_content(tmp_path, doc.filename)
            results.append({"filename": doc.filename, "content": extracted.get("content", "")})
        finally:
            os.unlink(tmp_path)
    return results


# ──────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return FileResponse("static/index.html")


@app.post("/api/analyze")
async def analyze_and_target(
    news_docs: list[UploadFile] = File(default=[]),
    brand_docs: list[UploadFile] = File(default=[]),
    extra_context: Optional[str] = Form(default=""),
    launch_date: Optional[str] = Form(default=""),
    tier_filter: Optional[int] = Form(default=2),
    company_city: Optional[str] = Form(default=""),
    media_contact_name: Optional[str] = Form(default=""),
    media_contact_email: Optional[str] = Form(default=""),
):
    """
    STEP 1 — Research & Targeting.
    Analyzes news, scores publications, suggests wave assignments.
    Returns session_id + targets for user to review and select.
    extra_context is treated as user_constraints (hard rules), NOT merged into news_content.
    """
    _cleanup_expired_sessions()

    doc_processor = DocumentProcessor()
    brand_builder = BrandContextBuilder()
    pitcher = PRPitcher()
    pub_finder = PublicationFinder()

    # Process brand docs
    brand_doc_list = await _process_docs(brand_docs, doc_processor)

    # Process news docs — extra_context kept SEPARATE as user_constraints
    news_doc_list = await _process_docs(news_docs, doc_processor)
    news_parts = [f"[From: {d['filename']}]\n{d['content']}" for d in news_doc_list if d['content']]
    news_content = "\n\n".join(news_parts)

    # extra_context = hard constraints, separate from news content
    user_constraints = extra_context.strip() if extra_context else ""
    launch_date_val = launch_date.strip() if launch_date else ""

    if not news_content.strip():
        return {"status": "error", "message": "Please provide news content to pitch."}

    # Build brand context
    brand_context_obj = brand_builder.build_context(brand_doc_list)
    brand_context = brand_context_obj.get("combined_content", "No brand documents uploaded.")

    # Scan publications — use custom list if set
    pub_summaries, recent_articles = await pub_finder.scan_publications(
        tier_filter=tier_filter,
        publications_override=CUSTOM_PUBLICATIONS,
    )

    # Run Steps 1-3 (no pitches drafted yet)
    result = await pitcher.analyze_and_plan(
        brand_context=brand_context,
        news_content=news_content,
        user_constraints=user_constraints,
        publication_summaries=pub_summaries,
        recent_headlines=recent_articles,
    )

    # Build articles_by_pub lookup for Step 2 scraping
    # (stored in each target's 'articles' field by pitcher)
    articles_by_pub = {}
    for target in result.get("targets", []):
        pub_name = target.get("publication", "")
        articles_by_pub[pub_name] = target.get("articles", [])

    # Store session
    session_id = str(uuid.uuid4())
    SESSION_STORE[session_id] = {
        "news_analysis": result["news_analysis"],
        "targets": result["targets"],
        "brand_context": brand_context,
        "news_content": news_content,
        "user_constraints": user_constraints,
        "launch_date": launch_date_val,
        "company_city": company_city.strip() if company_city else "",
        "media_contact_name": media_contact_name.strip() if media_contact_name else "",
        "media_contact_email": media_contact_email.strip() if media_contact_email else "",
        "articles_by_pub": articles_by_pub,
        "publication_count": len(pub_summaries),
        "articles_scanned": len(recent_articles),
        "timestamp": time.time(),
    }

    return {
        "status": "success",
        "session_id": session_id,
        "news_analysis": result["news_analysis"],
        "targets": result["targets"],
        "campaign_suggestion": result.get("campaign_suggestion", {}),
        "publication_count": len(pub_summaries),
        "articles_scanned": len(recent_articles),
    }


@app.post("/api/campaign")
async def build_campaign(req: CampaignRequest):
    """
    STEP 2 — Deep Personalization & Campaign Build.
    Accepts user's wave selections, scrapes articles, drafts pitches.
    """
    session = _get_session(req.session_id)
    if not session:
        return {
            "status": "error",
            "message": "Session expired or not found. Please run the analysis again."
        }

    pitcher = PRPitcher()
    scraper = ArticleScraper()

    # Gather all selected pub names
    all_selected = []
    if req.wave_1:
        all_selected.append(req.wave_1)
    all_selected.extend(req.wave_2)
    all_selected.extend(req.wave_3)

    if not all_selected:
        return {"status": "error", "message": "No publications selected. Please select at least one Wave 2 target."}

    # Scrape articles for all selected publications in parallel
    articles_by_pub = session["articles_by_pub"]
    scraped_by_pub = await scraper.scrape_articles_for_targets(
        selected_pub_names=all_selected,
        articles_by_pub=articles_by_pub,
        articles_per_pub=3,
    )

    # Draft full campaign
    result = await pitcher.draft_campaign(
        brand_context=session["brand_context"],
        news_content=session["news_content"],
        user_constraints=session["user_constraints"],
        news_analysis=session["news_analysis"],
        targets=session["targets"],
        wave_1_pub=req.wave_1,
        wave_2_pubs=req.wave_2,
        wave_3_pubs=req.wave_3,
        scraped_by_pub=scraped_by_pub,
        launch_date=session.get("launch_date", ""),
        company_city=session.get("company_city", ""),
        media_contact_name=session.get("media_contact_name", ""),
        media_contact_email=session.get("media_contact_email", ""),
    )

    waves = result.get("waves", {})
    return {
        "status": "success",
        "news_analysis": result["news_analysis"],
        "campaign_plan": result.get("campaign_plan", {}),
        "waves": waves,
        "all_targets": result.get("all_targets", []),
        "press_release": result.get("press_release", {}),
        "publication_count": session["publication_count"],
        "articles_scanned": session["articles_scanned"],
        "wave_counts": {
            "wave_1": 1 if waves.get("wave_1") else 0,
            "wave_2": len(waves.get("wave_2", [])),
            "wave_3": len(waves.get("wave_3", [])),
        }
    }


@app.get("/api/publications")
async def list_publications():
    """Return the active publication list (custom if set, else default)."""
    from publication_finder import PUBLICATIONS
    pubs = CUSTOM_PUBLICATIONS if CUSTOM_PUBLICATIONS is not None else PUBLICATIONS
    return {"publications": pubs}


@app.post("/api/publications")
async def save_publications(payload: dict):
    """
    Replace the active publication list with a user-edited version.
    Persists for the lifetime of the server process.
    """
    global CUSTOM_PUBLICATIONS
    pubs = payload.get("publications")
    if not isinstance(pubs, list):
        return {"status": "error", "message": "publications must be a list"}
    # Basic validation — each entry must have at least a name
    for p in pubs:
        if not p.get("name", "").strip():
            return {"status": "error", "message": f"Every publication must have a name."}
    CUSTOM_PUBLICATIONS = pubs
    return {"status": "success", "count": len(pubs)}


@app.post("/api/publications/reset")
async def reset_publications():
    """Reset to the default curated publication list."""
    global CUSTOM_PUBLICATIONS
    CUSTOM_PUBLICATIONS = None
    from publication_finder import PUBLICATIONS
    return {"status": "success", "count": len(PUBLICATIONS)}


class ReanalyzeRequest(BaseModel):
    session_id: str
    tier_filter: Optional[int] = 2


@app.post("/api/reanalyze")
async def reanalyze(req: ReanalyzeRequest):
    """
    Re-run analysis using the text content already stored in a session,
    but with the current (possibly edited) publication list.
    Replaces the session's targets/news_analysis in place and returns
    the same shape as /api/analyze.
    """
    session = _get_session(req.session_id)
    if not session:
        return {"status": "error", "message": "Session expired or not found. Please upload your documents and analyze again."}

    pitcher = PRPitcher()
    pub_finder = PublicationFinder()

    pub_summaries, recent_articles = await pub_finder.scan_publications(
        tier_filter=req.tier_filter,
        publications_override=CUSTOM_PUBLICATIONS,
    )

    result = await pitcher.analyze_and_plan(
        brand_context=session["brand_context"],
        news_content=session["news_content"],
        user_constraints=session["user_constraints"],
        publication_summaries=pub_summaries,
        recent_headlines=recent_articles,
    )

    articles_by_pub = {}
    for target in result.get("targets", []):
        pub_name = target.get("publication", "")
        articles_by_pub[pub_name] = target.get("articles", [])

    # Update the session in-place
    session["news_analysis"] = result["news_analysis"]
    session["targets"] = result["targets"]
    session["articles_by_pub"] = articles_by_pub
    session["publication_count"] = len(pub_summaries)
    session["articles_scanned"] = len(recent_articles)
    session["timestamp"] = time.time()

    return {
        "status": "success",
        "session_id": req.session_id,
        "news_analysis": result["news_analysis"],
        "targets": result["targets"],
        "campaign_suggestion": result.get("campaign_suggestion", {}),
        "publication_count": len(pub_summaries),
        "articles_scanned": len(recent_articles),
    }


# ──────────────────────────────────────────────────────────────
# Export endpoint — generate campaign .docx
# ──────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    session_id: str
    campaign: dict  # the full /api/campaign response payload


@app.post("/api/export/docx")
async def export_docx(req: ExportRequest):
    """Generate a .docx campaign package and return it for download."""
    from fastapi.responses import StreamingResponse
    import io
    from docx_exporter import build_campaign_docx

    session = _get_session(req.session_id)
    docx_bytes = build_campaign_docx(req.campaign, session or {})

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=pitchplanner-campaign.docx"},
    )


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "pitchplanner", "version": "2.0.0"}


# ──────────────────────────────────────────────────────────────
# Legacy single-shot endpoint — kept for backward compatibility
# ──────────────────────────────────────────────────────────────

@app.post("/api/pitch")
async def generate_pitches_legacy(
    news_docs: list[UploadFile] = File(default=[]),
    brand_docs: list[UploadFile] = File(default=[]),
    extra_context: Optional[str] = Form(default=""),
    tier_filter: Optional[int] = Form(default=2),
):
    """
    Legacy single-shot endpoint — runs analysis + targets + wave suggestions
    but skips article scraping and pitch drafting. Redirects to /api/analyze logic.
    """
    return await analyze_and_target(
        news_docs=news_docs,
        brand_docs=brand_docs,
        extra_context=extra_context,
        tier_filter=tier_filter,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
