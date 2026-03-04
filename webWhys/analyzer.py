"""
webWhys - Website & Competitor Analysis Tool
Copyright (C) 2026 Nicole Scott

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.

---

Optimization Analyzer Module
Uses LLM to generate specific, prioritized optimization suggestions
based on website analysis and brand context.
"""

import os
import json
from typing import Optional
import litellm
from document_processor import BrandContextBuilder
from best_practices import (
    GEO_BEST_PRACTICES,
    LLM_BEST_PRACTICES,
    SEO_BEST_PRACTICES,
    AEO_BEST_PRACTICES,
    get_recommendations_for_issues,
    generate_optimization_checklist
)


class OptimizationAnalyzer:
    """Generate AI-powered optimization recommendations."""

    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.brand_builder = BrandContextBuilder()

    async def _infer_missing_audience(self, site_data: dict) -> str:
        """
        If apparent_audience is missing/empty, use LLM to infer it from page content.
        """
        if site_data.get("page_messaging", {}).get("apparent_audience"):
            return site_data["page_messaging"]["apparent_audience"]

        # Build context from page content to infer audience
        seo = site_data.get("seo_factors", {})
        msg = site_data.get("page_messaging", {})
        content = site_data.get("content_analysis", {})

        context = f"""
Title: {seo.get('title', 'N/A')}
H1: {msg.get('primary_message', 'N/A')}
Value Prop: {msg.get('value_proposition', 'N/A')}
Key Claims: {', '.join(msg.get('key_claims', []))}
Main Content: {content.get('main_content', '')[:800]}
"""

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at inferring target audiences from web page content. Return ONLY the audience description as 1-3 words—no punctuation, no special characters, no explanations."
                    },
                    {
                        "role": "user",
                        "content": f"Who is the intended audience for this product/service? Answer with only 1-3 words describing the person type, role, or organization (e.g., 'Enterprise security teams' or 'Small business owners'):\n\nTitle: {context.split('Title: ')[1].split(chr(10))[0] if 'Title: ' in context else 'N/A'}\nKey info: {context[:300]}"
                    }
                ],
                temperature=0.2,  # Very low temperature for deterministic output
                max_tokens=20
            )

            inferred = response.choices[0].message.content.strip()
            print(f"[DEBUG] Raw LLM response for audience: '{inferred}'")

            # Validate output: Accept ONLY clean audience descriptions
            # Pattern: 1-5 words, only letters/spaces/hyphens, no special chars
            import re
            if inferred and len(inferred) > 2 and len(inferred) < 80:
                # Check if it's a valid audience description
                # Allow letters, spaces, hyphens, commas (for lists like "devs, designers")
                if re.match(r'^[a-zA-Z\s\-,]+$', inferred):
                    # Check word count (roughly 1-5 words)
                    word_count = len(inferred.split())
                    if 1 <= word_count <= 5:
                        return inferred

            return "Not explicitly stated"
        except Exception:
            return "Not explicitly stated"

    async def generate_recommendations(
        self,
        your_site: dict,
        competitors: list[dict],
        brand_documents: list[dict],
        focus_areas: list[str]
    ) -> dict:
        """
        Generate prioritized optimization recommendations based on:
        - Your website analysis
        - Competitor website analyses
        - Brand/positioning documents
        - Focus areas specified by user
        """

        # Build brand context from documents
        brand_context = self.brand_builder.build_context(brand_documents)

        # Enrich site data: infer missing audience for your site and competitors
        if not your_site.get("page_messaging", {}).get("apparent_audience"):
            inferred_audience = await self._infer_missing_audience(your_site)
            your_site["page_messaging"]["apparent_audience"] = inferred_audience

        for competitor in competitors:
            if competitor.get("status") == "success" and not competitor.get("page_messaging", {}).get("apparent_audience"):
                inferred_audience = await self._infer_missing_audience(competitor)
                competitor["page_messaging"]["apparent_audience"] = inferred_audience

        # Prepare competitor comparison summary
        competitor_summary = self._summarize_competitors(competitors)

        # Identify gaps between you and competitors
        gaps = self._identify_gaps(your_site, competitors)

        # Generate recommendations using LLM
        recommendations = await self._generate_llm_recommendations(
            your_site=your_site,
            competitor_summary=competitor_summary,
            competitors=competitors,
            gaps=gaps,
            brand_context=brand_context,
            focus_areas=focus_areas
        )

        # Generate priority actions
        priority_actions = self._prioritize_actions(
            recommendations["recommendations"],
            your_site.get("issues", []),
            gaps
        )

        return {
            "recommendations": recommendations["recommendations"],
            "copy_suggestions": recommendations.get("copy_suggestions", []),
            "priority_actions": priority_actions,
            "competitive_gaps": gaps
        }

    def _summarize_competitors(self, competitors: list[dict]) -> dict:
        """Create a summary of competitor strengths and patterns."""
        summary = {
            "total_analyzed": len(competitors),
            "successful_scans": 0,
            "common_strengths": [],
            "seo_patterns": {},
            "content_patterns": {},
            "technical_patterns": {}
        }

        seo_features = {
            "has_og_tags": 0,
            "has_twitter_cards": 0,
            "has_structured_data": 0,
            "has_sitemap": 0,
            "avg_word_count": 0
        }

        for comp in competitors:
            if comp.get("status") == "success":
                summary["successful_scans"] += 1

                seo = comp.get("seo_factors", {})
                tech = comp.get("technical_factors", {})
                content = comp.get("content_analysis", {})

                if seo.get("og_tags"):
                    seo_features["has_og_tags"] += 1
                if seo.get("twitter_cards"):
                    seo_features["has_twitter_cards"] += 1
                if content.get("has_structured_data"):
                    seo_features["has_structured_data"] += 1
                if tech.get("has_sitemap"):
                    seo_features["has_sitemap"] += 1
                seo_features["avg_word_count"] += seo.get("word_count", 0)

                # Track strengths
                for strength in comp.get("strengths", []):
                    summary["common_strengths"].append(strength.get("strength", ""))

        if summary["successful_scans"] > 0:
            seo_features["avg_word_count"] //= summary["successful_scans"]

        summary["seo_patterns"] = seo_features
        return summary

    def _format_competitor_keywords(self, competitors: list[dict]) -> str:
        """Format competitor keyword targets for the LLM prompt."""
        lines = []
        for comp in competitors:
            if comp.get("status") != "success":
                continue
            domain = comp.get("domain", comp.get("url", "Competitor"))
            keywords = comp.get("page_messaging", {}).get("keyword_targets", [])
            title = comp.get("seo_factors", {}).get("title", "")
            h1s = comp.get("seo_factors", {}).get("h1_tags", [])
            if keywords:
                lines.append(f"- {domain}: {', '.join(keywords[:6])}")
            elif title:
                lines.append(f"- {domain}: [derived from title] {title[:100]}")
        return "\n".join(lines) if lines else "No competitor keyword data available"

    def _format_competitor_messaging(self, competitors: list[dict]) -> str:
        """Format competitor messaging angles for the LLM prompt."""
        lines = []
        for comp in competitors:
            if comp.get("status") != "success":
                continue
            domain = comp.get("domain", comp.get("url", "Competitor"))
            msg = comp.get("page_messaging", {})
            primary = msg.get("primary_message", "")
            audience = msg.get("apparent_audience", "")
            tone = msg.get("tone", "")
            if primary:
                line = f"- {domain}: \"{primary[:120]}\""
                if audience:
                    line += f" | Audience: {audience}"
                if tone:
                    line += f" | Tone: {tone}"
                lines.append(line)
        return "\n".join(lines) if lines else "No competitor messaging data available"

    def _identify_gaps(self, your_site: dict, competitors: list[dict]) -> list[dict]:
        """Identify gaps where competitors are doing better."""
        gaps = []

        your_seo = your_site.get("seo_factors", {})
        your_tech = your_site.get("technical_factors", {})
        your_content = your_site.get("content_analysis", {})
        your_geo = your_site.get("geo_factors", {})

        for comp in competitors:
            if comp.get("status") != "success":
                continue

            comp_seo = comp.get("seo_factors", {})
            comp_tech = comp.get("technical_factors", {})
            comp_content = comp.get("content_analysis", {})
            comp_geo = comp.get("geo_factors", {})

            # Word count comparison
            if comp_seo.get("word_count", 0) > your_seo.get("word_count", 0) * 1.5:
                gaps.append({
                    "type": "content_depth",
                    "competitor": comp.get("domain", comp.get("url")),
                    "detail": f"Competitor has {comp_seo.get('word_count')} words vs your {your_seo.get('word_count')}",
                    "impact": "high"
                })

            # Structured data
            if comp_content.get("has_structured_data") and not your_content.get("has_structured_data"):
                gaps.append({
                    "type": "structured_data",
                    "competitor": comp.get("domain", comp.get("url")),
                    "detail": f"Competitor uses {', '.join(comp_content.get('structured_data_types', []))} structured data",
                    "impact": "medium"
                })

            # GEO factors
            if comp_geo.get("statistics_present") and not your_geo.get("statistics_present"):
                gaps.append({
                    "type": "geo_statistics",
                    "competitor": comp.get("domain", comp.get("url")),
                    "detail": "Competitor includes statistics and data points for AI citation",
                    "impact": "medium"
                })

            if comp_geo.get("comparison_tables") and not your_geo.get("comparison_tables"):
                gaps.append({
                    "type": "comparison_content",
                    "competitor": comp.get("domain", comp.get("url")),
                    "detail": "Competitor has comparison tables for easy AI extraction",
                    "impact": "medium"
                })

        # Deduplicate by type
        seen_types = set()
        unique_gaps = []
        for gap in gaps:
            if gap["type"] not in seen_types:
                seen_types.add(gap["type"])
                unique_gaps.append(gap)

        return unique_gaps

    async def _generate_llm_recommendations(
        self,
        your_site: dict,
        competitor_summary: dict,
        competitors: list[dict],
        gaps: list[dict],
        brand_context: dict,
        focus_areas: list[str]
    ) -> list[dict]:
        """Use LLM to generate specific, actionable recommendations."""

        # Build the analysis prompt
        prompt = self._build_analysis_prompt(
            your_site, competitor_summary, competitors, gaps, brand_context, focus_areas
        )

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a senior SEO and content strategist specializing in B2B software. You understand both traditional SEO (Google rankings) and AI/GEO discoverability (how ChatGPT, Perplexity, Gemini, and Claude surface and cite pages).

Your recommendations must follow these rules without exception:
1. BRAND ACCURACY: Use the exact product/brand name from the documents. Never shorten, alter, or genericize it.
2. NO INVENTED CLAIMS: Never invent statistics, capabilities, or proof points not present in the brand documents. If you want to recommend adding data, say so as a strategy — don't fabricate it.
3. KEYWORD COMPETITION: Reference the specific keywords competitors appear to be targeting (provided in competitor analysis). Recommend how to compete for, differentiate from, or flank those terms.
4. REAL SEO PRACTICES: Search intent alignment, semantic keyword clustering, E-E-A-T signals, title/meta optimization using actual page content.
5. REAL AI DISCOVERABILITY: Direct-answer content formatting, FAQ schema, citation-worthy framing, structured content AI can extract and quote verbatim.
6. COPY SPECIFICITY: When suggesting copy, write real candidate headlines/titles/descriptions specific to this brand's actual positioning — never use placeholder patterns like "Company X solves Y for Z teams."
7. COMPETITIVE INSIGHT: Identify where competitors are strong on specific query types and recommend content or structural changes to compete.
8. REFLECT THE BRAND'S ACTUAL PRIMARY MESSAGE: Read the brand documents carefully. Use the positioning angles, audience language, and differentiators that are most prominent in those docs — not generic industry buzzwords. If the brand documents don't emphasize a particular term or concept, don't lead with it. Mirror the hierarchy and priorities in the docs."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=6000
            )

            result = json.loads(response.choices[0].message.content)
            return {
                "recommendations": result.get("recommendations", []),
                "copy_suggestions": result.get("copy_suggestions", [])
            }

        except Exception as e:
            # Log error instead of silently failing
            error_msg = str(e)
            print(f"[ERROR] LLM recommendations API call failed: {error_msg}")
            import traceback
            traceback.print_exc()

            return {
                "error": f"LLM API call failed: {error_msg}. Check your OpenAI API key is valid and has credits.",
                "recommendations": [],
                "copy_suggestions": []
            }

    def _build_analysis_prompt(
        self,
        your_site: dict,
        competitor_summary: dict,
        competitors: list[dict],
        gaps: list[dict],
        brand_context: dict,
        focus_areas: list[str]
    ) -> str:
        """Build the analysis prompt for the LLM."""

        # Build brand grounding — prefer uploaded docs; fall back to rich page-derived context
        has_brand_docs = bool(brand_context.get('combined_content', '').strip())

        if has_brand_docs:
            brand_section_label = "Brand & Messaging Documents (uploaded by user)"
            brand_section_note = (
                "CRITICAL: These documents are the ONLY approved source for copy suggestions and brand language.\n"
                "The copy suggestions must sound like they came from these docs — not from the competitor analysis above.\n"
                "Use the exact product name, approved value propositions, and messaging hierarchy found here.\n"
                "If a competitor keyword does NOT appear in these brand docs, do NOT use it in copy suggestions.\n"
                "You may mention it in recommendations as a competitor term to be aware of, but not in the brand's own copy."
            )
            brand_section_content = brand_context['combined_content'][:12000]
        else:
            # No docs uploaded — synthesize brand context from scraped page content
            import re as _re
            msg = your_site.get('page_messaging', {})
            seo = your_site.get('seo_factors', {})
            content = your_site.get('content_analysis', {})

            h1s = seo.get('h1_tags', [])
            h2s = seo.get('h2_tags', [])
            h3s = seo.get('h3_tags', [])
            ctas = msg.get('cta_language', [])
            kws  = msg.get('keyword_targets', [])

            synthesized = []
            synthesized.append(f"PRODUCT/BRAND NAME: {your_site.get('domain', 'Unknown')}")
            synthesized.append(f"PAGE TITLE: {seo.get('title', '')}")
            if msg.get('primary_message'):
                synthesized.append(f"PRIMARY HEADLINE (H1): {msg['primary_message']}")
            if msg.get('value_proposition'):
                synthesized.append(f"VALUE PROPOSITION (first visible paragraph):\n{msg['value_proposition']}")
            if msg.get('apparent_audience'):
                synthesized.append(f"APPARENT AUDIENCE: {msg['apparent_audience']}")
            if msg.get('tone'):
                synthesized.append(f"PAGE TONE: {msg['tone']}")
            if h1s and len(h1s) > 1:
                synthesized.append("ALL H1 TAGS ON PAGE:\n" + "\n".join(f"- {h}" for h in h1s[:8]))
            if h2s:
                synthesized.append("H2 SECTION HEADINGS:\n" + "\n".join(f"- {h}" for h in h2s[:12]))
            if h3s:
                synthesized.append("H3 SUBHEADINGS:\n" + "\n".join(f"- {h}" for h in h3s[:10]))
            if ctas:
                synthesized.append("CTA / BUTTON LANGUAGE ON PAGE:\n" + "\n".join(f"- {c}" for c in ctas))
            if kws:
                synthesized.append("KEYWORD SIGNALS FROM PAGE:\n" + "\n".join(f"- {k}" for k in kws))
            meta = seo.get('meta_description', '')
            if meta:
                synthesized.append(f"META DESCRIPTION: {meta}")
            main_content = content.get('main_content', '')
            if main_content:
                plain = _re.sub(r'<[^>]+>', ' ', main_content)
                plain = _re.sub(r'\s{2,}', ' ', plain).strip()
                if len(plain) > 100:
                    synthesized.append(f"MAIN CONTENT EXTRACT (first ~1500 chars):\n{plain[:1500]}")

            brand_section_label = "Brand Context Derived from Page (no documents uploaded)"
            brand_section_note = (
                "No brand documents were uploaded. The context below was synthesized from the scraped page content.\n"
                "CRITICAL: Use ONLY the language, terminology, product names, and positioning found in this page context for copy suggestions.\n"
                "Do NOT invent product capabilities, statistics, certifications, or customer counts not present in the page.\n"
                "If a competitor keyword does NOT appear in the page's own content, do NOT use it in copy suggestions.\n"
                "Copy suggestions must mirror the brand voice and hierarchy evident from the headings and value proposition — not generic B2B patterns.\n"
                "The copy suggestions should read as if written by someone who studied only this page — grounded in its actual language, not the category's clichés."
            )
            brand_section_content = "\n\n".join(synthesized)

        prompt = f"""Analyze this website and provide optimization recommendations.

## Your Website Analysis
URL: {your_site.get('url')}
Domain: {your_site.get('domain')}

### Page Messaging (what the page actually says)
- Primary Message (H1/Hero): {your_site.get('page_messaging', {}).get('primary_message', 'Not found')}
- Value Proposition: {your_site.get('page_messaging', {}).get('value_proposition', 'Not found')}
- Apparent Audience: {your_site.get('page_messaging', {}).get('apparent_audience', 'Not stated')}
- Page Tone: {your_site.get('page_messaging', {}).get('tone', 'Unknown')}
- Key H2 Claims: {your_site.get('page_messaging', {}).get('key_claims', [])}
- CTA Language Found: {your_site.get('page_messaging', {}).get('cta_language', [])}

### SEO Factors
- Title: {your_site.get('seo_factors', {}).get('title', 'Not found')}
- Title Length: {your_site.get('seo_factors', {}).get('title_length', 0)} chars
- Meta Description: {(your_site.get('seo_factors', {}).get('meta_description') or 'Not found')[:150]}
- H1 Tags: {your_site.get('seo_factors', {}).get('h1_tags', [])}
- Word Count: {your_site.get('seo_factors', {}).get('word_count', 0)}
- Images without alt: {your_site.get('seo_factors', {}).get('images_without_alt', 0)}

### Technical Factors
- HTTPS: {your_site.get('technical_factors', {}).get('https', False)}
- Has Sitemap: {your_site.get('technical_factors', {}).get('has_sitemap', False)}
- Has Robots.txt: {your_site.get('technical_factors', {}).get('has_robots_txt', False)}

### LLM Discoverability
- Structured Content: {your_site.get('llm_discoverability', {}).get('structured_content', False)}
- FAQ Schema: {your_site.get('llm_discoverability', {}).get('faq_schema', False)}
- Citations/Sources: {your_site.get('llm_discoverability', {}).get('citations_and_sources', 0)}

### GEO Factors
- Statistics Present: {your_site.get('geo_factors', {}).get('statistics_present', False)}
- Lists/Bullets: {your_site.get('geo_factors', {}).get('lists_and_bullets', 0)}
- Comparison Tables: {your_site.get('geo_factors', {}).get('comparison_tables', False)}
- Citation Ready: {your_site.get('geo_factors', {}).get('citation_ready', False)}

### Current Issues
{json.dumps(your_site.get('issues', []), indent=2)}

### Current Strengths
{json.dumps(your_site.get('strengths', []), indent=2)}

## Competitor Intelligence
- Competitors Analyzed: {competitor_summary.get('successful_scans', 0)}
- Competitors with Structured Data: {competitor_summary.get('seo_patterns', {}).get('has_structured_data', 0)}
- Average Competitor Word Count: {competitor_summary.get('seo_patterns', {}).get('avg_word_count', 0)}

### Competitor Keyword Targets (terms COMPETITORS appear to be optimizing for):
NOTE: These are competitor keywords — useful to know for competitive strategy, but do NOT use them as the brand's own positioning language in copy suggestions unless the brand context below also uses them.
{self._format_competitor_keywords(competitors)}

### Competitor Messaging Angles:
{self._format_competitor_messaging(competitors)}

## Competitive Gaps Identified
{json.dumps(gaps, indent=2)}

## {brand_section_label}
{brand_section_note}

{brand_section_content}

## Focus Areas Requested
{focus_areas if focus_areas else 'General optimization across SEO, AI discoverability, and messaging'}

---

Based on this analysis, provide 8-12 specific, prioritized recommendations AND brand-accurate copy suggestions.

OUTPUT FORMAT — return only valid JSON:
{{
  "recommendations": [
    {{
      "id": 1,
      "category": "SEO|AI Discoverability|Technical|Messaging|Competitive",
      "title": "Specific, action-oriented title",
      "description": "2-3 sentences: what to do, why it matters for this specific site, and how it relates to what competitors are doing. Must reference actual content from this site or brand context — no generic advice.",
      "impact": "high|medium|low",
      "effort": "low|medium|high",
      "specific_actions": [
        "Concrete step 1 — specific to this site's actual content",
        "Concrete step 2",
        "Concrete step 3"
      ],
      "expected_outcome": "Specific, measurable outcome — e.g. 'Appear in AI responses for [query type]' or 'Improve click-through for [topic] searches'"
    }}
  ],
  "copy_suggestions": [
    {{
      "category": "Page Title",
      "current": "current title tag text",
      "why": "[SPECIFIC REASON: e.g., 'Current title doesn't include [keyword] that competitors are ranking for' or 'At [X] chars, exceeds optimal 50-60 char range']",
      "suggestions": [
        "Suggested title option 1 — 50-60 chars, keyword first, grounded in actual page language",
        "Suggested title option 2",
        "Suggested title option 3"
      ]
    }},
    {{
      "category": "Main Headline (H1)",
      "current": "current H1 text",
      "why": "[SPECIFIC REASON: e.g., 'Current H1 focuses on [feature], but competitors emphasize [different benefit] — consider which resonates with target audience']",
      "suggestions": [
        "Suggested H1 option 1 — benefit-driven, uses this brand's actual language",
        "Suggested H1 option 2",
        "Suggested H1 option 3"
      ]
    }},
    {{
      "category": "Meta Description",
      "current": "current meta description",
      "why": "[SPECIFIC REASON: e.g., 'Current description is [X] chars but optimal is 150-160' or 'Missing CTA that could improve click-through']",
      "suggestions": [
        "Suggested meta description 1 — 150-160 chars, includes CTA, grounded in actual page content",
        "Suggested meta description 2",
        "Suggested meta description 3"
      ]
    }},
    {{
      "category": "Hero Value Proposition",
      "current": "current hero/value prop text",
      "why": "[SPECIFIC REASON: e.g., 'Current value prop emphasizes [feature], but target audience [audience] cares more about [outcome]']",
      "suggestions": [
        "Suggested value prop 1 — outcome-first, uses the actual positioning language from this page",
        "Suggested value prop 2",
        "Suggested value prop 3"
      ]
    }},
    {{
      "category": "Differentiation Statement",
      "current": "(assessment of current differentiation on page)",
      "why": "[SPECIFIC REASON: e.g., 'Page doesn't clearly explain what makes it different from [competitor]' or 'Differentiation language is generic — could be more specific']",
      "suggestions": [
        "Suggested differentiator 1 — grounded in what this page actually claims, not category clichés",
        "Suggested differentiator 2",
        "Suggested differentiator 3"
      ]
    }},
    {{
      "category": "FAQ Copy (for AI & Search)",
      "current": "[ASSESSMENT: Does the page have an FAQ section? Is it schema-marked? If yes, describe what's covered. If no, state 'No FAQ section or schema found']",
      "why": "[SPECIFIC REASON: e.g., 'Page lacks FAQ schema; adding FAQs would answer [common buyer question] and boost AI/voice search visibility']",
      "suggestions": [
        "Q: [question a real buyer of THIS product would ask]\\nA: [direct answer drawn from what this page actually says about the product]",
        "Q: [another real buyer question for this specific product]\\nA: [answer grounded in this page's actual content]",
        "Q: [competitor comparison question relevant to this category]\\nA: [answer that highlights what this page says about its differentiators]",
        "Q: [question about implementation, time-to-value, or getting started]\\nA: [answer from this page's actual content about how customers adopt/use the product]",
        "Q: [objection-handling question: 'How does this compare to...' or 'What if we already use...']\\nA: [answer that positions this product's advantage based on what the page claims]"
      ]
    }}
  ]
}}

COPY SUGGESTIONS RULES — critical:
- Ground every suggestion in the brand context section above — use the actual language, product names, and positioning found there
- Never invent statistics, customer counts, certifications, or capabilities not present in the brand context
- Do NOT use generic industry buzzwords (e.g. "next-gen", "AI-powered", "cutting-edge") unless those exact terms appear prominently in the brand context above
- FAQ answers must be answerable from what the page actually says — if the page doesn't say something, don't make it up; instead flag that the brand should add that content
- Suggestions should be immediately usable with zero editing needed — no [placeholder] text except for stats the client must fill from their own data (clearly marked)
- The copy suggestions should read as if written by someone who studied only this brand's actual page and voice — not a generic B2B copywriter
- **CRITICAL: "why" field** — This MUST be SPECIFIC to THIS SITE'S SITUATION. Examples:
  * Instead of "Why the H1 matters": Write "Your current H1 doesn't mention [feature], but competitors emphasize it. Adding it would address this competitive gap."
  * Instead of "Why this matters for SEO": Write "The current title is [current], which doesn't include your primary keyword [keyword]. Titles are the strongest SEO signal."
  * The "why" should explain the SPECIFIC PROBLEM with the current copy and why this site should fix it — not generic advice about why good copy matters

STRICT RECOMMENDATION RULES:
- Use "AI Discoverability" for all GEO/LLM recommendations (not separate categories)
- Zero duplicate recommendations — each card must address a distinct issue
- Every description must reference this site's actual title, H1, content, or brand context — no generic advice that would apply to any B2B website
- Technical issues get a single "Technical" card covering all of them
- At least 2 recommendations must directly address competitor keyword or messaging gaps
- At least 1 recommendation must address AI answer-engine discoverability (how to get cited by ChatGPT/Perplexity)

Prioritize in this order:
1. High-severity technical/SEO issues (blocks everything else)
2. Competitive keyword/messaging gaps where competitors are positioned and this site is not
3. AI discoverability and citation-readiness
4. Messaging alignment and copy quality
5. Quick wins (high impact, low effort)"""

        return prompt

    def _generate_fallback_recommendations(
        self,
        your_site: dict,
        gaps: list[dict],
        focus_areas: list[str]
    ) -> list[dict]:
        """Generate comprehensive rule-based recommendations using best practices."""
        recommendations = []
        rec_id = 1

        issues = your_site.get("issues", [])
        seo = your_site.get("seo_factors", {})
        tech = your_site.get("technical_factors", {})
        llm = your_site.get("llm_discoverability", {})
        geo = your_site.get("geo_factors", {})

        # Get recommendations based on detected issues
        issue_recs = get_recommendations_for_issues(issues)
        for practice in issue_recs[:5]:
            recommendations.append({
                "id": rec_id,
                "category": practice["category"],
                "title": practice["title"],
                "description": practice["description"],
                "impact": practice["impact"],
                "effort": practice["effort"],
                "specific_actions": practice["actions"],
                "expected_outcome": f"Improved {practice['category'].lower()} performance"
            })
            rec_id += 1

        # Address high severity issues not covered by best practices
        for issue in issues:
            if issue.get("severity") == "high" and rec_id <= 12:
                recommendations.append({
                    "id": rec_id,
                    "category": issue.get("category", "SEO"),
                    "title": f"Fix: {issue.get('issue')}",
                    "description": f"Address this critical issue: {issue.get('issue')}",
                    "impact": "high",
                    "effort": "low",
                    "specific_actions": [f"Resolve: {issue.get('issue')}"],
                    "expected_outcome": "Improved search visibility and user experience"
                })
                rec_id += 1

        # AI Discoverability (GEO + LLM combined — they are the same goal)
        # Combine into one card if multiple signals are missing, to avoid duplicate cards
        ai_issues = []
        ai_actions = []

        if not geo.get("citation_ready"):
            ai_issues.append("content is not optimized to be cited by AI systems")
            ai_actions += [
                "Add specific statistics and data points with cited sources (e.g. '94% of web-based attacks are prevented')",
                "Include expert quotes or authoritative references with attribution",
                "Use bulleted lists for key claims — AI systems extract these easily",
            ]

        if not geo.get("statistics_present"):
            ai_issues.append("no specific numbers or statistics found")
            ai_actions += [
                "Replace vague claims ('significantly reduces risk') with specific numbers ('reduces incidents by 94%')",
                "Add deployment stats, customer counts, or benchmark data",
                "Update statistics at least annually and cite sources",
            ]

        if not llm.get("faq_schema"):
            ai_issues.append("no FAQ schema markup")
            ai_actions += [
                "Create a FAQ section answering the top 5 questions buyers ask",
                "Implement FAQPage JSON-LD schema markup on the page",
                "Write questions exactly as buyers would phrase them to AI assistants",
            ]

        if not llm.get("structured_content"):
            ai_issues.append("content lacks clear heading hierarchy")
            ai_actions += [
                "Ensure each major topic has its own H2 heading",
                "Start each section with a summary sentence that works standalone",
                "Use H3s for subtopics under each H2",
            ]

        if ai_issues and rec_id <= 12:
            # Deduplicate actions
            seen_actions = set()
            unique_ai_actions = []
            for a in ai_actions:
                if a not in seen_actions:
                    seen_actions.add(a)
                    unique_ai_actions.append(a)

            recommendations.append({
                "id": rec_id,
                "category": "AI Discoverability",
                "title": "Optimize for AI Search & Generative Engines",
                "description": (
                    "AI tools like ChatGPT, Perplexity, and Gemini are increasingly where buyers start their research. "
                    "To appear in AI-generated answers, your content needs to be structured, data-rich, and explicitly answerable. "
                    f"Issues found: {'; '.join(ai_issues)}."
                ),
                "impact": "high",
                "effort": "medium",
                "specific_actions": unique_ai_actions[:8],
                "expected_outcome": (
                    "Higher likelihood of being cited in AI search results (ChatGPT, Perplexity, Gemini). "
                    "FAQ schema can also trigger Google 'People Also Ask' rich results, increasing organic click-through."
                )
            })
            rec_id += 1

        # Technical recommendations — explicitly check for missing technical factors
        tech_issues = []
        tech_actions = []

        if not tech.get("has_sitemap"):
            tech_issues.append("no sitemap.xml found")
            tech_actions += [
                "Create a sitemap.xml file listing all indexable pages",
                "Submit the sitemap to Google Search Console and Bing Webmaster Tools",
                "Include lastmod dates to signal freshness to crawlers",
            ]

        if not tech.get("has_robots_txt"):
            tech_issues.append("no robots.txt found")
            tech_actions += [
                "Create a robots.txt file at the domain root",
                "Reference your sitemap URL inside robots.txt",
                "Ensure robots.txt doesn't accidentally block important pages",
            ]

        if not tech.get("https"):
            tech_issues.append("not using HTTPS")
            tech_actions += [
                "Install an SSL certificate (free via Let's Encrypt)",
                "Set up 301 redirects from HTTP to HTTPS",
                "Update all internal links to use HTTPS URLs",
            ]

        if not tech.get("mobile_friendly_hints"):
            tech_issues.append("no viewport meta tag detected (likely not mobile-optimized)")
            tech_actions += [
                "Add <meta name='viewport' content='width=device-width, initial-scale=1'> to the page <head>",
                "Test mobile layout using Google's Mobile-Friendly Test",
                "Ensure touch targets (buttons, links) are at least 44px tall",
            ]

        # Security headers
        for issue in issues:
            if issue.get("category") == "Technical" and issue.get("severity") in ("high", "medium"):
                if issue.get("issue") not in [ti for ti in tech_issues]:
                    tech_issues.append(issue.get("issue", ""))
                    tech_actions.append(f"Resolve: {issue.get('issue', '')}")

        if tech_issues and rec_id <= 14:
            seen_tech = set()
            unique_tech_actions = []
            for a in tech_actions:
                if a not in seen_tech:
                    seen_tech.add(a)
                    unique_tech_actions.append(a)

            recommendations.append({
                "id": rec_id,
                "category": "Technical",
                "title": "Fix Technical SEO Foundations",
                "description": (
                    "Technical issues don't affect design, but they directly impact how well search engines "
                    "and AI crawlers can discover, index, and trust your site. "
                    f"Issues found: {'; '.join(i for i in tech_issues if i)}."
                ),
                "impact": "high",
                "effort": "low",
                "specific_actions": unique_tech_actions[:8],
                "expected_outcome": (
                    "Improved crawlability and indexing. Search engines can fully discover your site, "
                    "and HTTPS + security headers increase trust signals for both users and ranking algorithms."
                )
            })
            rec_id += 1

        # Add AEO recommendations
        if rec_id <= 12:
            aeo_practice = AEO_BEST_PRACTICES.get("featured_snippets", {})
            recommendations.append({
                "id": rec_id,
                "category": "AEO",
                "title": aeo_practice.get("title", "Optimize for Featured Snippets"),
                "description": aeo_practice.get("description", "Win position zero in search results"),
                "impact": "high",
                "effort": "medium",
                "specific_actions": aeo_practice.get("actions", [
                    "Answer questions directly in 40-50 words",
                    "Create numbered/bulleted lists",
                    "Include comparison tables"
                ]),
                "expected_outcome": "Increased visibility in search features"
            })
            rec_id += 1

        # Add Messaging & Copy recommendations
        if rec_id <= 15:
            recommendations.append({
                "id": rec_id,
                "category": "Messaging",
                "title": "Strengthen Value Proposition",
                "description": "Make your unique value clear in the first 5 seconds. Visitors should immediately understand what you do and why it matters to them.",
                "impact": "high",
                "effort": "medium",
                "specific_actions": [
                    "Lead with the customer problem you solve, not your product features",
                    "Use specific, quantifiable benefits (e.g., '10x faster' not 'faster')",
                    "Include a clear differentiator from competitors in your headline",
                    "Test your headline: Can someone understand your value in 5 seconds?"
                ],
                "expected_outcome": "Lower bounce rate, higher engagement"
            })
            rec_id += 1

        if rec_id <= 15:
            recommendations.append({
                "id": rec_id,
                "category": "Messaging",
                "title": "Add Social Proof & Trust Signals",
                "description": "Build credibility with evidence that others trust you. AI systems also favor content with authoritative signals.",
                "impact": "high",
                "effort": "medium",
                "specific_actions": [
                    "Add customer logos or 'Trusted by X companies' section",
                    "Include specific testimonials with names and titles",
                    "Display security certifications, compliance badges, or awards",
                    "Add case study snippets with measurable outcomes"
                ],
                "expected_outcome": "Increased trust and conversion rates"
            })
            rec_id += 1

        if rec_id <= 15:
            recommendations.append({
                "id": rec_id,
                "category": "Messaging",
                "title": "Clarify Your Differentiation",
                "description": "Help visitors understand why to choose you over alternatives. This is critical for both humans and AI recommendations.",
                "impact": "high",
                "effort": "medium",
                "specific_actions": [
                    "Create a 'Why Us' or 'How We're Different' section",
                    "Use comparison language: 'Unlike X, we...' or 'The only solution that...'",
                    "Highlight your unique methodology, technology, or approach",
                    "Address common objections proactively"
                ],
                "expected_outcome": "Better competitive positioning in search and AI results"
            })
            rec_id += 1

        if rec_id <= 15:
            recommendations.append({
                "id": rec_id,
                "category": "Messaging",
                "title": "Optimize Call-to-Action Copy",
                "description": "Your CTAs should be specific and value-focused, not generic. 'Get Started' tells nothing; 'Start Your Free Security Audit' tells everything.",
                "impact": "medium",
                "effort": "low",
                "specific_actions": [
                    "Replace generic CTAs ('Learn More', 'Get Started') with specific ones",
                    "Include the benefit in the CTA: 'See How Much You Can Save'",
                    "Add urgency or specificity: 'Get Your Report in 2 Minutes'",
                    "Test different CTA variations"
                ],
                "expected_outcome": "Higher click-through and conversion rates"
            })
            rec_id += 1

        # Address competitive gaps — with plain-language descriptions
        gap_explanations = {
            "content_depth": {
                "title": "Expand Content Depth to Match Competitors",
                "what": (
                    "One or more competitors have significantly more content on their homepage/landing page. "
                    "Search engines and AI systems interpret more comprehensive content as a signal of expertise and authority."
                ),
                "actions": [
                    "Identify the specific topics competitors cover that you don't",
                    "Add sections addressing buyer questions: How it works, Use cases, Who it's for, Pricing overview",
                    "Expand existing sections with more detail rather than adding filler",
                    "Aim for 800–1,500 words on key landing pages",
                ],
                "outcome": "Better ranking for competitive keywords; more content for AI systems to cite when recommending your solution."
            },
            "structured_data": {
                "title": "Add Structured Data (Schema Markup) Like Competitors",
                "what": (
                    "One or more competitors use schema.org structured data markup on their pages. "
                    "This is code you add to your page (invisible to visitors) that tells search engines exactly what your page is about — "
                    "your organization, product, pricing, FAQ, etc. It enables rich results (star ratings, FAQ dropdowns) in Google "
                    "and makes your page more citable by AI systems."
                ),
                "actions": [
                    "Add Organization schema: your company name, description, logo, social links",
                    "Add Product or SoftwareApplication schema with your key features and pricing info",
                    "Add FAQPage schema for your FAQ section",
                    "Validate implementation with Google's Rich Results Test",
                ],
                "outcome": "Eligibility for rich results in Google search (higher click-through rates), and better AI discoverability."
            },
            "geo_statistics": {
                "title": "Add Statistics & Data Points (Competitors Already Have These)",
                "what": (
                    "Competitors include specific numbers and statistics on their pages. "
                    "AI systems like ChatGPT and Perplexity strongly prefer citing sources with concrete data. "
                    "Pages with statistics are viewed as more credible by both humans and AI."
                ),
                "actions": [
                    "Add specific performance metrics: reduction in threats, deployment time, customer count",
                    "Include industry statistics with cited sources to build authority",
                    "Replace vague language ('significant reduction') with numbers ('94% fewer incidents')",
                    "Add a data/results section to your page",
                ],
                "outcome": "Higher AI citation rate; builds credibility with buyers; content seen as more authoritative."
            },
            "comparison_content": {
                "title": "Add Comparison Tables to Win 'Best X' and 'X vs Y' Searches",
                "what": (
                    "Competitors have comparison tables on their pages. "
                    "Comparison tables are highly effective for winning featured snippets in Google for 'best [product]' and 'X vs Y' queries. "
                    "AI systems also extract table data directly when answering comparison questions."
                ),
                "actions": [
                    "Create a features comparison table: your product vs. category alternatives",
                    "Add a 'Why choose us vs. [competitor category]' table",
                    "Include use-case rows: which scenarios each option is best for",
                    "Ensure the table is HTML (not an image) so it's machine-readable",
                ],
                "outcome": "Better visibility for comparison searches; increased chance of AI recommendations when buyers ask 'what's the best [category]?'"
            }
        }

        seen_gap_types = set()
        for gap in gaps[:3]:
            gap_type = gap.get("type", "")
            competitor = gap.get("competitor", "a competitor")
            if rec_id <= 18 and gap_type not in seen_gap_types:
                seen_gap_types.add(gap_type)
                exp = gap_explanations.get(gap_type, {})
                recommendations.append({
                    "id": rec_id,
                    "category": "Competitive",
                    "title": exp.get("title", f"Close Competitive Gap: {gap_type.replace('_', ' ').title()}"),
                    "description": (
                        f"{exp.get('what', gap.get('detail', ''))} "
                        f"(Detected vs. {competitor}.)"
                    ),
                    "impact": gap.get("impact", "medium"),
                    "effort": "medium",
                    "specific_actions": exp.get("actions", [gap.get("detail", "")]),
                    "expected_outcome": exp.get(
                        "outcome",
                        f"Close the gap with {competitor} and match their capabilities in this area."
                    )
                })
                rec_id += 1

        return recommendations

    def _prioritize_actions(
        self,
        recommendations: list[dict],
        issues: list[dict],
        gaps: list[dict]
    ) -> list[dict]:
        """Create a prioritized action list from recommendations."""
        priority_actions = []

        # Score and sort recommendations
        scored = []
        seen_titles = set()  # Track titles to avoid duplicates

        for rec in recommendations:
            # Skip duplicates
            title = rec.get("title", "")
            if title in seen_titles:
                continue
            seen_titles.add(title)

            score = 0
            # Impact scoring
            if rec.get("impact") == "high":
                score += 30
            elif rec.get("impact") == "medium":
                score += 20
            else:
                score += 10

            # Effort scoring (lower effort = higher priority)
            if rec.get("effort") == "low":
                score += 20
            elif rec.get("effort") == "medium":
                score += 10
            else:
                score += 5

            # Category bonuses
            if rec.get("category") in ["GEO", "LLM", "AI Discoverability", "Messaging"]:
                score += 10  # Prioritize AI and messaging optimizations

            scored.append((score, rec))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Take top 5 as priority actions (no duplicates)
        for i, (score, rec) in enumerate(scored[:5]):
            priority_actions.append({
                "priority": i + 1,
                "title": rec.get("title"),
                "category": rec.get("category"),
                "impact": rec.get("impact"),
                "effort": rec.get("effort"),
                "first_step": rec.get("specific_actions", [""])[0] if rec.get("specific_actions") else "",
                "description": rec.get("description", ""),
                "all_actions": rec.get("specific_actions", [])
            })

        return priority_actions
