"""
Blog Extractor
Uses an LLM to transform raw blog text + brand doc into structured brief content.
Returns validated JSON ready for pdf_generator.py.
"""

import json
import os
import re
from typing import Optional


async def extract_brief(
    blog_text: str,
    blog_title: str,
    brand_doc_text: str,
    page_preference: int = 2,
    inline_images: Optional[list] = None
) -> dict:
    """
    Call LLM to extract structured brief content from blog text.
    Returns dict with: title, subtitle, exec_summary, takeaways[], sections[],
    elevator_pitch_header, elevator_pitch_body, cta_text, cta_url,
    needs_extra_page, image_suggestions[], faqs[]
    """
    try:
        import litellm
    except ImportError:
        raise RuntimeError("litellm not installed. Run: pip install litellm")

    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    images_context = ""
    if inline_images:
        imgs = [f"- {img.get('alt', 'image')} ({img['src'][:80]})" for img in inline_images[:3]]
        images_context = "\n\nImages found in blog:\n" + "\n".join(imgs)

    # 3 sections keeps sections full + leaves room for content
    section_count = 3

    # Determine if we're generating for 3-page template
    is_3page = page_preference == 3

    # Build schema based on page preference
    if is_3page:
        schema_str = """{
  "title": "Compelling title derived from blog (max 60 chars, punchy)",
  "subtitle": "One-line framing of the key insight or argument (max 90 chars)",
  "exec_summary": "Summary paragraph for Page 1. 2-3 sentences. Aim for 50-70 words. Punchy, direct insight into the blog's core argument.",
  "introduction": "Page 2 introduction. 2 substantial paragraphs introducing the topic and setting context. Aim for 150-180 words total. No filler.",
  "takeaways": [
    "Key takeaway 1 - a specific insight or actionable point (full sentence, 15-25 words)",
    "Key takeaway 2 - a specific insight or actionable point (full sentence, 15-25 words)",
    "Key takeaway 3 - a specific insight or actionable point (full sentence, 15-25 words)"
  ],
  "sections": [
    {{
      "header": "Meaningful section header from blog content",
      "body": "SECTION 1 — Page 2 after cards. 90-110 words. Substantive, specific, with details from the blog."
    }},
    {{
      "header": "Second section header",
      "body": "SECTION 2 — also Page 2 (below section 1). 80-100 words. Specific details from the blog."
    }},
    {{
      "header": "Third section header",
      "body": "SECTION 3 — Page 3. 60-80 words. Concise, specific, adds new detail not covered in sections 1-2."
    }}
  ],
  "continuing_content": "Page 3 continuation paragraph. 1 paragraph continuing the narrative. Aim for 60-80 words. Concise and substantive.",
  "conclusion": "NOT USED - removed from 3-page design. Leave empty.",
  "stats_or_faq_type": "stats OR checklist OR faq (choose one based on blog content - what would readers find most useful?)",
  "stats_or_faq_items": [
    {{
      "label": "For stats: the stat/number. For checklist: action item. For FAQ: question.",
      "value": "For stats: what it represents (1 sentence). For checklist: explanation. For FAQ: answer (1-2 sentences max)."
    }}
  ],
  "faqs": [
    {{
      "question": "Question from blog or synthesized",
      "answer": "Answer in 1-2 sentences max. 30-40 words."
    }}
  ],
  "elevator_pitch_body": "The press-release 'About the company' paragraph from the brand doc, copied WORD FOR WORD. If not found, write ONE sentence (20-30 words, third person, company name first) summarizing the company's core purpose from the brand doc.",
  "cta_text": "CTA text from brand doc (e.g. 'Watch demo'). If not found, use empty string.",
  "cta_url": "CTA URL from brand doc. If not found, use empty string.",
  "image_suggestions": [
    {{
      "section_index": 1,
      "description": "What kind of image would work here (1 sentence)",
      "prompt": "Detailed image generation prompt if needed"
    }}
  ]
}}"""
    else:
        schema_str = """{
  "title": "Compelling title derived from blog (max 60 chars, punchy)",
  "subtitle": "One-line framing of the key insight or argument (max 90 chars)",
  "exec_summary": "4-5 sentence summary. Cover: what problem this addresses, the core argument or finding, who should care and why it matters NOW. Be specific, direct, substantive. Aim for 120-150 words. Enough detail to fill the page.",
  "takeaways": [
    "Insight-driven takeaway 1 - a full sentence making a specific, actionable point (not a topic label). Aim for 20-30 words.",
    "Insight-driven takeaway 2 - a full sentence making a specific, actionable point. Aim for 20-30 words.",
    "Insight-driven takeaway 3 - a full sentence making a specific, actionable point. Aim for 20-30 words."
  ],
  "faqs": [
    {{
      "question": "First question from blog or synthesized",
      "answer": "Answer in 1-2 sentences. Max 40 words."
    }},
    {{
      "question": "Second question",
      "answer": "Answer in 1-2 sentences. Max 40 words."
    }},
    {{
      "question": "Third question",
      "answer": "Answer in 1-2 sentences. Max 40 words."
    }},
    {{
      "question": "Fourth question",
      "answer": "Answer in 1-2 sentences. Max 40 words."
    }},
    {{
      "question": "Fifth question",
      "answer": "Answer in 1-2 sentences. Max 40 words."
    }}
  ],
  "sections": [
    {{
      "header": "Meaningful section header that reflects blog content (not 'Section 1')",
      "body": "Substantive 3-4 sentence paragraph. Include specific details and context from the blog. Aim for 80-100 words (concise but complete). IMPORTANT: Always end with a complete sentence (period required). No trailing clauses or incomplete thoughts. No filler - every sentence must add information."
    }}
  ],
  "elevator_pitch_body": "The press-release 'About the company' paragraph from the brand doc, copied WORD FOR WORD. If not found, write ONE sentence (20-30 words, third person, company name first) summarizing the company's core purpose from the brand doc.",
  "cta_text": "CTA button/link text extracted from brand doc (e.g. 'Watch the demo'). If not found, use empty string.",
  "cta_url": "CTA URL from brand doc. If not found, use empty string.",
  "image_suggestions": [
    {{
      "section_index": 0,
      "description": "What kind of image would work here and why (1 sentence)",
      "prompt": "Detailed image generation prompt if user wants AI to create it"
    }}
  ]
}}"""

    # Build rules section conditionally
    base_rules = f"""- faqs: REQUIRED — you MUST produce a minimum of 3 FAQ pairs, maximum 5. If the blog has an explicit FAQ section, extract up to 5 verbatim. If no FAQ section exists, SYNTHESIZE at least 3 insightful Q&A pairs from the blog content — questions a reader would realistically ask after reading this article. Each answer 1-2 sentences, max 40 words. Returning 1 or 2 FAQ pairs is not acceptable.
- sections array: include exactly {section_count} sections. Each section body must be 100-120 words - do not truncate or pad with filler.
- exec_summary: 4-5 sentences, ~120-150 words. Substantive and detailed. No em dashes, no smart quotes, no buzzword soup. Plain English. Enough content to fill page 1.
- takeaways: derive real insights, not topic headings. Bad: "Security matters". Good: "Network-level isolation beats endpoint agents because it stops lateral movement before credentials are stolen, cutting breach radius by 80%."
- elevator_pitch_body: Find the "About the company" boilerplate — the kind of paragraph you would find at the bottom of a press release. Identifying characteristics: (1) Written in THIRD PERSON, typically opens with the company name (e.g. "[Company] is the...", "[Company] gives organizations...", "[Company] was founded by..."). (2) 50-150 words, single prose paragraph. (3) Describes what the company does, who it serves, and its value. (4) Reads like an external-facing statement, not internal messaging guidance. Brand docs often contain multiple pitches at different lengths ("Short pitch", "Elevator pitch", "Long pitch") — these are INTERNAL MESSAGING GUIDES, not the boilerplate. The boilerplate is the paragraph that would appear unchanged in a press release or document footer, typically starting with the company name with no surrounding heading needed. Copy WORD FOR WORD if found. If no such paragraph exists, synthesize ONE sentence (20-30 words, third person, starting with the company name) that captures the company's core purpose based on the overall brand doc. Never use empty string if a brand doc was provided.
- image_suggestions: include 1-2 spots where a visual would genuinely help comprehension. Only suggest if it adds value.
- All text: no em dashes (use - or :), no smart quotes, use straight quotes only.
- Forbidden words/phrases: NEVER use: "landscape", "digital landscape", "cybersecurity landscape", "threat landscape", "today's landscape", or ANY phrase of the form "[adjective] landscape" (e.g. "evolving landscape", "complex landscape", "modern landscape"). Also forbidden: "ever-evolving", "rapidly evolving", "rapidly changing", "rapidly changing [x] environment", "evolving threat", "vague", "paradigm shift", "game changer", "best practices", "at the end of the day", "at scale", "stakeholders", "synergy", "leverage", "empower". Write with specific, concrete language instead.
- Humanize content: Use specific examples, data, names, and concrete scenarios instead of abstract jargon. Replace corporate speak with plain, direct statements.
- IMPORTANT: Write to fill the page. Thin, short content defeats the purpose of the brief."""

    extra_rules_3page = (
        "\n- introduction: 2 substantial paragraphs setting context for Page 2. 150-180 words total."
        "\n- sections[0] body: 90-110 words — Page 2 first section after Key Takeaways cards. End with a complete sentence."
        "\n- sections[1] body: 80-100 words — Page 2 second section below section 1. End with a complete sentence."
        "\n- sections[2] body: 70-90 words — Page 3 top section. This is the LAST content the reader sees before being directed to the full article. Write it so it ends naturally — a complete thought that feels satisfying but leaves the reader wanting more. CRITICAL: The final character of this field MUST be a period, exclamation mark, or question mark. Never end with a comma, semicolon, or mid-sentence word. Do NOT write a conclusion."
        "\n- continuing_content: Leave empty. Not used in the current layout."
        "\n- conclusion: NOT USED - leave empty."
        "\n- stats_or_faq_type: MUST be 'faq' - generate 3-4 FAQ questions and answers extracted from or synthesized from blog content."
        "\n- stats_or_faq_items: 3-4 FAQ items (prefer 4 if the blog has enough distinct questions). Each has 'label' (question) and 'value' (answer, 1-2 sentences, max 40 words)."
    )

    rules_section = base_rules + (extra_rules_3page if is_3page else "")

    prompt = f"""You are a B2B marketing content specialist. Transform this blog post into structured content for a polished executive brief PDF. The PDF needs to fill the page - write rich, substantive content.

## Blog Title
{blog_title}

## Blog Content
{blog_text[:12000]}
{images_context}

## Brand Document (extract elevator pitch and CTA from this)
{brand_doc_text[:8000] if brand_doc_text else "[No brand document provided - use empty strings for elevator pitch fields]"}

## Your Task
Return ONLY valid JSON matching this exact schema. No markdown, no explanation, just JSON.

{schema_str}

## Rules
{rules_section}
"""

    response = await litellm.acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=6000  # Increased from 4800 to prevent mid-sentence truncation
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        # Try to extract JSON from response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"LLM returned invalid JSON: {e}\n\nRaw response:\n{raw[:500]}")

    # Validate and fill defaults
    data = _validate_and_fill(data)
    return data


def _validate_and_fill(data: dict) -> dict:
    """Ensure all required fields exist with sensible defaults."""
    defaults = {
        "title": "Executive Brief",
        "subtitle": "",
        "exec_summary": "",
        "introduction": "",  # 3-page only
        "takeaways": ["", "", ""],
        "sections": [{"header": "Key Insights", "body": "Content could not be extracted."}, {"header": "What This Means", "body": "Content could not be extracted."}],
        "continuing_content": "",  # 3-page only
        "conclusion": "",  # 3-page only
        "stats_or_faq_type": "faq",  # 3-page only: "stats", "checklist", or "faq"
        "stats_or_faq_items": [],  # 3-page only
        "elevator_pitch_body": "",
        "cta_text": "",
        "cta_url": "",
        "image_suggestions": [],
        "faqs": []
    }

    for key, default in defaults.items():
        if key not in data or data[key] is None:
            data[key] = default

    # Ensure takeaways has at least 3
    while len(data["takeaways"]) < 3:
        data["takeaways"].append("")
    data["takeaways"] = data["takeaways"][:3]

    # Ensure sections has at least 2
    while len(data["sections"]) < 2:
        data["sections"].append({"header": "Additional Context", "body": ""})

    # Normalize text (remove em dashes, smart quotes)
    def norm(s):
        if not s:
            return s
        for old, new in [("\u2014", "-"), ("\u2013", "-"), ("\u201c", '"'),
                          ("\u201d", '"'), ("\u2018", "'"), ("\u2019", "'")]:
            s = s.replace(old, new)
        return s

    data["title"] = norm(data["title"])
    data["subtitle"] = norm(data["subtitle"])
    data["exec_summary"] = norm(data["exec_summary"])
    data["introduction"] = norm(data.get("introduction", ""))  # 3-page
    data["continuing_content"] = norm(data.get("continuing_content", ""))  # 3-page
    data["conclusion"] = norm(data.get("conclusion", ""))  # 3-page
    data["elevator_pitch_body"] = norm(data["elevator_pitch_body"])
    data["takeaways"] = [norm(t) for t in data["takeaways"]]
    def _fix_section_body(body: str) -> str:
        """Ensure section body ends with terminal punctuation, never mid-sentence."""
        body = norm(body)
        if body and body[-1] not in '.!?':
            # Find last complete sentence
            for ch in ('.', '!', '?'):
                idx = body.rfind(ch)
                if idx > len(body) * 0.5:  # at least halfway through
                    return body[:idx + 1]
        return body

    data["sections"] = [
        {"header": norm(s.get("header", "")), "body": _fix_section_body(s.get("body", ""))}
        for s in data["sections"]
    ]
    data["faqs"] = [
        {"question": norm(f.get("question", "")), "answer": norm(f.get("answer", ""))}
        for f in data.get("faqs", [])
        if f.get("question") and f.get("answer")
    ][:5]  # max 5 FAQ pairs

    # Enforce minimum of 2 FAQ pairs. If LLM returned only 1, duplicate it with a
    # variation so the layout never shows a single lone question.
    if len(data["faqs"]) == 1:
        sole = data["faqs"][0]
        fallback_q = "What are the key takeaways from this article?"
        takeaway_text = " ".join(data.get("takeaways", []))
        fallback_a = (takeaway_text[:120] + "…") if len(takeaway_text) > 120 else (takeaway_text or sole["answer"])
        data["faqs"].append({"question": fallback_q, "answer": fallback_a})

    # Validate and normalize stats_or_faq_items (3-page)
    if "stats_or_faq_items" not in data or not isinstance(data["stats_or_faq_items"], list):
        data["stats_or_faq_items"] = []
    data["stats_or_faq_items"] = [
        {"label": norm(item.get("label", "")), "value": norm(item.get("value", ""))}
        for item in data["stats_or_faq_items"]
        if item.get("label")
    ][:5]  # max 5 items for the shaded section

    # Ensure stats_or_faq_type is valid
    valid_types = ["stats", "checklist", "faq"]
    if data.get("stats_or_faq_type") not in valid_types:
        data["stats_or_faq_type"] = "faq"

    return data
