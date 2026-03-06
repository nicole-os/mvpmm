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

Website Scraper Module
Extracts and analyzes website content for SEO/GEO/LLM discoverability assessment.
"""

import asyncio
import re
import os
from urllib.parse import urlparse, urljoin
from typing import Optional
import aiohttp
from bs4 import BeautifulSoup
from readability import Document
import tldextract
import litellm
from browser_manager import PlaywrightBrowserManager


class WebsiteScraper:
    """Scrapes and analyzes websites for optimization opportunities."""

    def __init__(self, timeout: int = 30):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.headers = {
            # Use realistic browser User-Agent to avoid WAF/bot detection blocks
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            # Consent mode headers to signal pre-consent state (like Google does)
            "Sec-GPC": "1",  # Global Privacy Control
            "Cookie": "consent_state=pre-consent"  # Signal we're in pre-consent state
        }

    async def analyze_website(self, url: str) -> dict:
        """
        Comprehensive website analysis for SEO/GEO/LLM discoverability.
        """
        # Normalize URL
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        result = {
            "url": url,
            "domain": self._extract_domain(url),
            "status": "success",
            "seo_factors": {},
            "content_analysis": {},
            "technical_factors": {},
            "llm_discoverability": {},
            "geo_factors": {},
            "page_messaging": {},
            "scannability": {},
            "issues": [],
            "strengths": []
        }

        try:
            # Configure TCP connector with larger header limits
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
            async with aiohttp.ClientSession(
                timeout=self.timeout,
                headers=self.headers,
                connector=connector,
                read_bufsize=2**16
            ) as session:
                try:
                    # Fetch main page
                    async with session.get(url, allow_redirects=True) as response:
                        result["http_status"] = response.status
                        result["final_url"] = str(response.url)
                        html = await response.text()
                except ValueError as e:
                    # Handle "got more than 8190 bytes when reading header" error
                    if "header value is too long" in str(e).lower() or "8190 bytes" in str(e):
                        result["status"] = "error"
                        result["error"] = f"Server response headers are oversized. This site may have excessive cookies or headers. {str(e)}"
                        return result
                    raise

                soup = BeautifulSoup(html, "lxml")
                doc = Document(html)

                # Detect bot-protection / CAPTCHA walls and JavaScript-heavy sites
                page_text = soup.get_text(" ", strip=True)
                word_count_check = len(page_text.split())
                block_signals = [
                    "security checkpoint", "vercel security", "cloudflare", "ddos protection",
                    "access denied", "captcha", "checking your browser", "ray id", "please wait",
                    "just a moment", "enable javascript and cookies", "bot protection",
                    # Cookie consent popup signals
                    "cookie consent", "accept cookies", "cookie policy", "manage preferences",
                    "cookie settings", "accept all", "reject all", "gdpr"
                ]
                is_blocked = (
                    word_count_check < 100 and
                    any(sig in page_text.lower() for sig in block_signals)
                )

                if is_blocked:
                    result["status"] = "blocked"
                    # Determine if it's a cookie popup or bot protection
                    is_cookie_popup = any(sig in page_text.lower() for sig in ["cookie consent", "accept cookies", "cookie policy", "manage preferences", "gdpr"])
                    if is_cookie_popup:
                        result["error"] = "Cookie consent popup detected — the site requires cookie acceptance before content is accessible. Try enabling cookies/consent on your browser, or the site may need JavaScript rendering to proceed."
                    else:
                        result["error"] = "Bot protection detected — the site returned a security checkpoint page. Data for this competitor is unavailable."
                    result["http_status"] = response.status
                    return result

                # Detect JavaScript-heavy sites (very low word count with no bot protection message)
                if await self._should_render_with_playwright(html, word_count_check):
                    print(f"[Scraper] Detected JavaScript-heavy site: {url}")
                    rendered_html = await self._render_with_playwright(url)

                    if rendered_html:
                        # Re-parse with rendered HTML
                        html = rendered_html
                        soup = BeautifulSoup(html, "lxml")
                        doc = Document(html)
                        # Recalculate page text and word count
                        page_text = soup.get_text(" ", strip=True)
                        word_count_check = len(page_text.split())
                        print(f"[Scraper] Re-parsed with Playwright. New word count: {word_count_check}")
                    else:
                        # Playwright rendering failed - continue with limited data
                        result["status"] = "requires-javascript"
                        result["warning"] = "This site requires JavaScript rendering. Playwright rendering was attempted but failed (timeout or error). Limited data available."
                        result["http_status"] = response.status

                # Analyze all aspects
                result["seo_factors"] = self._analyze_seo(soup, url)

                # Remove images_needing_alt from SEO factors (no longer used)
                result["seo_factors"].pop("images_needing_alt", [])

                result["content_analysis"] = self._analyze_content(soup, doc)
                result["technical_factors"] = await self._analyze_technical(session, url, soup, response)
                result["llm_discoverability"] = self._analyze_llm_factors(soup, html)
                result["geo_factors"] = self._analyze_geo_factors(soup)
                result["page_messaging"] = await self._analyze_page_messaging(soup)
                result["scannability"] = self._analyze_scannability(soup)

                # Compile issues and strengths
                result["issues"], result["strengths"] = self._compile_findings(result)

        except asyncio.TimeoutError:
            result["status"] = "timeout"
            result["error"] = "Request timed out"
        except aiohttp.ClientError as e:
            result["status"] = "error"
            result["error"] = f"Connection error: {str(e)}"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        return result

    def _extract_domain(self, url: str) -> str:
        """Extract the domain from a URL."""
        extracted = tldextract.extract(url)
        return f"{extracted.domain}.{extracted.suffix}"

    def _analyze_seo(self, soup: BeautifulSoup, url: str) -> dict:
        """Analyze on-page SEO factors."""
        seo = {
            "title": None,
            "title_length": 0,
            "meta_description": None,
            "meta_description_length": 0,
            "h1_tags": [],
            "h2_tags": [],
            "h3_tags": [],
            "canonical_url": None,
            "og_tags": {},
            "twitter_cards": {},
            "internal_links": 0,
            "external_links": 0,
            "images_without_alt": 0,
            "images_total": 0,
            "keywords_in_url": [],
            "word_count": 0
        }

        # Title
        title_tag = soup.find("title")
        if title_tag:
            seo["title"] = title_tag.get_text(strip=True)
            seo["title_length"] = len(seo["title"])

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            seo["meta_description"] = meta_desc["content"]
            seo["meta_description_length"] = len(seo["meta_description"])

        # Headings — use separator=" " to prevent adjacent inline elements merging words
        for h1 in soup.find_all("h1"):
            seo["h1_tags"].append(h1.get_text(separator=" ", strip=True))
        for h2 in soup.find_all("h2"):
            seo["h2_tags"].append(h2.get_text(separator=" ", strip=True))
        for h3 in soup.find_all("h3"):
            seo["h3_tags"].append(h3.get_text(separator=" ", strip=True)[:100])

        # Canonical
        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical:
            seo["canonical_url"] = canonical.get("href")

        # Open Graph tags
        for og in soup.find_all("meta", attrs={"property": re.compile(r"^og:")}):
            prop = og.get("property", "").replace("og:", "")
            seo["og_tags"][prop] = og.get("content", "")[:200]

        # Twitter cards
        for tw in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")}):
            name = tw.get("name", "").replace("twitter:", "")
            seo["twitter_cards"][name] = tw.get("content", "")[:200]

        # Links analysis
        parsed_url = urlparse(url)
        base_domain = self._extract_domain(url)
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.startswith(("http://", "https://")):
                link_domain = self._extract_domain(href)
                if link_domain == base_domain:
                    seo["internal_links"] += 1
                else:
                    seo["external_links"] += 1
            elif href.startswith("/"):
                seo["internal_links"] += 1

        # Images
        images_needing_alt = []
        for img in soup.find_all("img"):
            seo["images_total"] += 1
            if not img.get("alt"):
                seo["images_without_alt"] += 1
                # Collect image data for alt text suggestions
                images_needing_alt.append({
                    "src": img.get("src", ""),
                    "title": img.get("title", ""),
                    "filename": img.get("src", "").split("/")[-1] if img.get("src") else ""
                })

        seo["images_needing_alt"] = images_needing_alt

        # Word count
        text = soup.get_text(separator=" ", strip=True)
        seo["word_count"] = len(text.split())

        return seo

    async def _generate_alt_suggestions(self, soup: BeautifulSoup, images_needing_alt: list, brand_context: list = None) -> dict:
        """Generate alt text suggestions using LLM for hash/encoded filenames. Parse filenames for others."""
        suggestions = {}
        hash_images = []  # Collect hash-named images for LLM processing

        if not images_needing_alt:
            return suggestions

        # Common file extensions and formats to skip
        skip_extensions = {'svg', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'avif', 'icon', 'ico'}
        skip_names = {'image', 'photo', 'picture', 'img', 'pic'}

        # Get page content for context (h1, h2, main content)
        page_h1 = [h1.get_text(strip=True) for h1 in soup.find_all('h1')]
        page_h2 = [h2.get_text(strip=True) for h2 in soup.find_all('h2')][:3]
        page_title = soup.find('title')
        title_text = page_title.get_text(strip=True) if page_title else ""

        # Get brand keywords if documents available
        brand_keywords = ""
        if brand_context:
            for doc in brand_context:
                if isinstance(doc, dict) and "text" in doc:
                    brand_keywords += " " + doc["text"][:200]

        for img_info in images_needing_alt:
            src = img_info.get("src", "")
            filename = img_info.get("filename", "")

            is_hash_filename = False
            is_encoded = False

            if filename:
                # Check for base64/encoded content
                if filename.startswith(('data:', 'svg+xml', 'base64')) or ',' in filename:
                    is_encoded = True
                    hash_images.append({
                        "src": src,
                        "filename": filename,
                        "type": "encoded"
                    })
                    continue

                name_without_ext = re.sub(r'\.\w+$', '', filename)
                # Check if it looks like a hash (20+ hex chars, or multiple hash-like segments)
                if re.match(r'^[a-f0-9]{20,}(_[a-f0-9]{20,})?', name_without_ext.lower()):
                    is_hash_filename = True
                    hash_images.append({
                        "src": src,
                        "filename": filename,
                        "type": "hash"
                    })
                    continue

            # Generate suggestions for meaningful filenames (parse from filename)
            suggestion = ""
            if filename and not is_hash_filename and not is_encoded:
                # Remove extension
                name_without_ext = re.sub(r'\.\w+$', '', filename)
                # Split on separators
                name_parts = re.sub(r'[_\-\./]', ' ', name_without_ext).split()
                # Filter out: numbers-only, common generic names, extensions
                name_parts = [p.lower() for p in name_parts
                             if p and not re.match(r'^\d+$', p)
                             and p.lower() not in skip_extensions
                             and p.lower() not in skip_names]

                if name_parts:
                    # Use first 2-3 meaningful words from filename
                    suggestion = " ".join(name_parts[:3])
                    suggestion = suggestion.capitalize()
                    suggestions[src] = suggestion

        # Use LLM to generate alt text for hash/encoded filenames
        if hash_images:
            llm_suggestions = await self._generate_alt_text_with_llm(
                hash_images,
                page_h1,
                page_h2,
                title_text,
                brand_keywords
            )
            suggestions.update(llm_suggestions)

        return suggestions

    async def _generate_alt_text_with_llm(self, hash_images: list, page_h1: list, page_h2: list, title: str, brand_keywords: str) -> dict:
        """Use LLM to generate meaningful alt text for hash/encoded filenames."""
        suggestions = {}
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")

        for img in hash_images:
            src = img.get("src", "")
            filename = img.get("filename", "")

            try:
                # Build context for the LLM
                page_context = f"Page title: {title}\n"
                if page_h1:
                    page_context += f"Main heading: {page_h1[0]}\n"
                if page_h2:
                    page_context += f"Section headings: {', '.join(page_h2)}\n"

                prompt = f"""Based on the following page context, generate a brief, descriptive alt text (1-3 sentences) for an image with filename: {filename}

Page Context:
{page_context}

Image filename: {filename}
Image location: {src}

Write ONLY the alt text description, nothing else. No quotes, no explanation."""

                print(f"[LLM] Calling {model} for alt text generation of hash-named image")
                response = await litellm.acompletion(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert at writing descriptive, SEO-friendly alt text for images based on limited context. Generate concise, clear descriptions that would help accessibility and search engine understanding."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                    max_tokens=100
                )

                alt_text = response.choices[0].message.content.strip()
                if alt_text and len(alt_text) > 5:  # Ensure it's a reasonable response
                    suggestions[src] = alt_text
                    print(f"[LLM] ✅ Generated alt text for {filename[:30]}...")

            except Exception as e:
                print(f"[ERROR] LLM alt text generation failed for {filename}: {str(e)}")
                # Fallback to placeholder if LLM fails
                suggestions[src] = "Image with hash filename - please add descriptive alt text"

        return suggestions

    async def _should_render_with_playwright(self, html: str, word_count: int) -> bool:
        """
        Determine if Playwright rendering is needed for a page.
        Checks for JavaScript-heavy indicators and framework signals.
        """
        # Check 1: Word count < 150 (existing JS detection)
        if word_count < 150:
            return True

        # Check 2: Detect framework signals in HTML
        framework_signals = [
            '<script src="/__next/',  # Next.js
            '<script src="/_astro/',  # Astro
            'data-react-root',        # React
            'ng-app',                 # Angular
            'v-app',                  # Vue
            '<noscript>Enable JavaScript',  # Explicit JS requirement
        ]

        for signal in framework_signals:
            if signal in html:
                return True

        return False

    async def _render_with_playwright(self, url: str) -> str:
        """
        Render a JavaScript-heavy page using Playwright and return rendered HTML.
        Falls back to None on timeout or error (graceful fallback).
        """
        try:
            browser_manager = PlaywrightBrowserManager()
            html, metadata = await browser_manager.render_page(url, timeout=10)

            if html:
                print(f"[Playwright] ✅ Rendered {url}")
                return html
            else:
                print(f"[Playwright] ⚠️ Timeout/error rendering {url}, falling back to static")
                return None

        except Exception as e:
            print(f"[Playwright] ❌ Error rendering {url}: {str(e)}")
            return None

    async def _infer_keywords_with_llm(self, title: str, primary_message: str, h2_tags: list, meta_description: str, key_claims: list) -> list:
        """
        Use LLM to intelligently identify keywords this page is targeting based on content signals.
        Works for any industry — doesn't rely on hard-coded industry keyword lists.
        """
        try:
            # Build context from page signals
            context = f"""
Title: {title}
H1/Primary Message: {primary_message}
H2 Headings: {', '.join(h2_tags[:3]) if h2_tags else 'N/A'}
Meta Description: {meta_description}
Key Claims: {', '.join(key_claims) if key_claims else 'N/A'}
"""

            model = os.getenv("LLM_MODEL", "gpt-4o-mini")
            print(f"[LLM] Calling {model} for keyword identification")

            response = await litellm.acompletion(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an SEO expert analyzing what keywords a page targets. Based on the page's content signals (title, H1, headings, meta, claims), identify the main keywords/topics this page is optimizing for. Return ONLY a comma-separated list of 5-8 keywords or short phrases (no more than 3 words each). No explanations, no quotes."
                    },
                    {
                        "role": "user",
                        "content": f"What keywords/topics is this page targeting? Return only comma-separated keywords:\n{context}"
                    }
                ],
                temperature=0.0,  # Deterministic output
                max_tokens=100
            )

            keywords_str = response.choices[0].message.content.strip()
            print(f"[LLM] ✅ Keywords identified: {keywords_str}")

            # Parse comma-separated keywords
            keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
            return keywords[:10]  # Return up to 10 keywords

        except Exception as e:
            print(f"[LLM] ❌ Keyword identification failed: {str(e)}")
            return []

    def _analyze_content(self, soup: BeautifulSoup, doc: Document) -> dict:
        """Analyze content quality and structure."""
        content = {
            "main_content": "",
            "content_length": 0,
            "readability_score": 0,
            "has_structured_data": False,
            "structured_data_types": [],
            "content_sections": [],
            "key_phrases": [],
            "cta_elements": []
        }

        # Extract main content
        try:
            content["main_content"] = doc.summary()[:2000]
            clean_text = BeautifulSoup(content["main_content"], "lxml").get_text(strip=True)
            content["content_length"] = len(clean_text)
        except Exception:
            pass

        # Structured data (JSON-LD, microdata)
        json_ld = soup.find_all("script", attrs={"type": "application/ld+json"})
        if json_ld:
            content["has_structured_data"] = True
            content["structured_data_types"].append("JSON-LD")

        # Check for schema.org microdata
        if soup.find(attrs={"itemtype": True}):
            content["has_structured_data"] = True
            content["structured_data_types"].append("Microdata")

        # CTAs
        cta_patterns = ["sign up", "get started", "try", "demo", "contact", "learn more", "download", "subscribe"]
        for link in soup.find_all(["a", "button"]):
            text = link.get_text(strip=True).lower()
            for pattern in cta_patterns:
                if pattern in text:
                    content["cta_elements"].append({
                        "text": link.get_text(strip=True)[:50],
                        "type": pattern
                    })
                    break

        return content

    async def _analyze_technical(self, session: aiohttp.ClientSession, url: str, soup: BeautifulSoup, response) -> dict:
        """Analyze technical SEO factors."""
        # Use final URL (after redirects) for HTTPS check
        final_url = str(response.url)
        technical = {
            "https": final_url.startswith("https"),
            "response_time_ms": 0,
            "has_robots_txt": False,
            "has_sitemap": False,
            "mobile_friendly_hints": [],
            "page_speed_hints": [],
            "security_headers": {}
        }

        # Check security headers
        important_headers = ["strict-transport-security", "content-security-policy", "x-frame-options", "x-content-type-options"]
        for header in important_headers:
            if header in response.headers:
                technical["security_headers"][header] = True

        # Mobile hints
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if viewport:
            technical["mobile_friendly_hints"].append("Has viewport meta tag")

        # Check robots.txt
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            async with session.get(robots_url) as robots_resp:
                if robots_resp.status == 200:
                    technical["has_robots_txt"] = True
        except Exception:
            pass

        # Check sitemap
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
        try:
            async with session.get(sitemap_url) as sitemap_resp:
                if sitemap_resp.status == 200:
                    technical["has_sitemap"] = True
        except Exception:
            pass

        return technical

    def _analyze_llm_factors(self, soup: BeautifulSoup, html: str) -> dict:
        """
        Analyze factors that affect LLM discoverability and AI search results.
        """
        llm = {
            "clear_value_proposition": False,
            "structured_content": False,
            "entity_mentions": [],
            "faq_schema": False,
            "how_to_schema": False,
            "clear_product_descriptions": False,
            "authoritative_content_signals": [],
            "citations_and_sources": 0,
            "content_freshness_signals": [],
            "unique_insights": []
        }

        # Check for FAQ structured data
        faq_indicators = ["faq", "frequently asked", "questions"]
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            content = script.get_text().lower()
            if "faqpage" in content:
                llm["faq_schema"] = True
            if "howto" in content:
                llm["how_to_schema"] = True

        # Check for clear sections
        headers = soup.find_all(["h1", "h2", "h3"])
        if len(headers) >= 3:
            llm["structured_content"] = True

        # Look for value proposition patterns
        hero_patterns = ["hero", "banner", "jumbotron", "headline"]
        for pattern in hero_patterns:
            if soup.find(class_=re.compile(pattern, re.I)):
                llm["clear_value_proposition"] = True
                break

        # Check for authoritative signals
        if soup.find(text=re.compile(r"(research|study|data|according to|source)", re.I)):
            llm["authoritative_content_signals"].append("References research/data")

        # Citations (links to external authoritative sources)
        external_links = soup.find_all("a", href=re.compile(r"^https?://"))
        llm["citations_and_sources"] = len(external_links)

        # Freshness signals
        date_patterns = soup.find_all(attrs={"datetime": True})
        if date_patterns:
            llm["content_freshness_signals"].append("Has datetime attributes")

        time_tags = soup.find_all("time")
        if time_tags:
            llm["content_freshness_signals"].append("Uses time elements")

        return llm

    def _analyze_geo_factors(self, soup: BeautifulSoup) -> dict:
        """Analyze Generative Engine Optimization (GEO) factors."""
        geo = {
            "citation_ready": False,
            "quotable_statements": [],
            "statistics_present": False,
            "expert_attribution": False,
            "source_links": [],
            "definition_blocks": [],
            "comparison_tables": False,
            "lists_and_bullets": 0
        }

        # Check for statistics
        text = soup.get_text()
        if re.search(r"\d+%|\d+ percent|\d+\s*(million|billion|thousand)", text, re.I):
            geo["statistics_present"] = True

        # Check for lists
        lists = soup.find_all(["ul", "ol"])
        geo["lists_and_bullets"] = len(lists)

        # Check for tables (comparison/feature tables)
        tables = soup.find_all("table")
        if tables:
            geo["comparison_tables"] = True

        # Check for blockquotes (expert citations)
        blockquotes = soup.find_all("blockquote")
        if blockquotes:
            geo["expert_attribution"] = True
            for bq in blockquotes[:3]:
                geo["quotable_statements"].append(bq.get_text(strip=True)[:150])

        # Definition-like content
        dl_tags = soup.find_all("dl")
        if dl_tags:
            geo["definition_blocks"] = [dl.get_text(strip=True)[:100] for dl in dl_tags[:3]]

        # Citation readiness
        if geo["statistics_present"] and (geo["expert_attribution"] or geo["lists_and_bullets"] > 2):
            geo["citation_ready"] = True

        return geo

    async def _infer_keywords_with_llm(
        self,
        title: str,
        primary_message: str,
        h2_tags: list,
        meta_description: str,
        key_claims: list
    ) -> list:
        """
        Use LLM to intelligently extract keywords from page content.
        Unlike hard-coded approaches, this works across any industry.
        """
        # Prepare content signals for LLM analysis
        content = {
            "page_title": title,
            "primary_message": primary_message,
            "subheadings": h2_tags[:5] if h2_tags else [],
            "meta_description": meta_description,
            "key_claims": key_claims[:5] if key_claims else []
        }

        prompt = f"""Analyze this webpage's content and identify the 5-10 most important keywords or key phrases it targets.

Content signals:
- Page Title: {content['page_title']}
- Primary Message (H1): {content['primary_message']}
- Subheadings (H2): {', '.join(content['subheadings'])}
- Meta Description: {content['meta_description']}
- Key Claims: {', '.join(content['key_claims'])}

Extract meaningful keywords that represent what this page is optimizing for. These should be:
- Specific to the content (not generic)
- Helpful for understanding the page's focus
- Natural language phrases (not abbreviations unless essential)

Return ONLY a comma-separated list of keywords, nothing else. Example: "keyword one, keyword two, keyword three"
"""

        try:
            response = await litellm.acompletion(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,  # Deterministic
                max_tokens=100
            )
            keywords_text = response.choices[0].message.content.strip()
            # Parse comma-separated keywords
            keywords = [kw.strip() for kw in keywords_text.split(",") if kw.strip()]
            return keywords[:10]  # Cap at 10
        except Exception as e:
            print(f"[LLM Keywords] Error extracting keywords: {str(e)}")
            return []

    async def _analyze_page_messaging(self, soup: BeautifulSoup) -> dict:
        """
        Infer the page's core message, intended audience, and value proposition
        from the visible text — hero copy, headings, CTAs, and body content.
        """
        messaging = {
            "primary_message": "",
            "apparent_audience": "",
            "value_proposition": "",
            "key_claims": [],
            "cta_language": [],
            "tone": ""
        }

        # Grab hero / above-the-fold text: H1, first H2, hero-class elements
        # Use separator=" " everywhere to prevent inline elements merging into "wordword"
        h1_tags = [t.get_text(separator=" ", strip=True) for t in soup.find_all("h1")]
        h2_tags = [t.get_text(separator=" ", strip=True) for t in soup.find_all("h2")][:4]

        # Hero-like containers
        hero_text = []
        for cls in ["hero", "banner", "jumbotron", "headline", "intro", "above-fold"]:
            el = soup.find(class_=re.compile(cls, re.I))
            if el:
                hero_text.append(el.get_text(separator=" ", strip=True)[:300])

        # Get page title as fallback
        page_title = soup.find("title")
        title_text = page_title.get_text(strip=True) if page_title else ""

        # Primary message = first non-empty H1 or hero text or page title
        if h1_tags:
            # Use first non-empty H1 tag
            non_empty_h1 = next((h1 for h1 in h1_tags if h1.strip()), None)
            if non_empty_h1:
                messaging["primary_message"] = non_empty_h1
            elif hero_text:
                messaging["primary_message"] = hero_text[0][:150]
            elif title_text:
                messaging["primary_message"] = title_text
        elif hero_text:
            messaging["primary_message"] = hero_text[0][:150]
        elif title_text:
            messaging["primary_message"] = title_text

        # Value prop — look for subheadline patterns near the hero
        # Filter out Lorem Ipsum and placeholder text
        lorem_ipsum_terms = {'lorem', 'ipsum', 'dolor', 'sit', 'amet', 'consectetur', 'adipiscing', 'elit',
                             'sed', 'quisque', 'pellentesque', 'ultrices', 'lacus', 'ornare', 'ullamcorper'}
        all_paras = []
        for p in soup.find_all("p"):
            text = p.get_text(separator=" ", strip=True)
            if len(text) > 40:
                # Skip if text is mostly Lorem Ipsum placeholder terms
                words = text.lower().split()
                lorem_ratio = sum(1 for w in words if w.rstrip('.,;:!?') in lorem_ipsum_terms) / len(words) if words else 0
                if lorem_ratio < 0.3:  # Skip paragraphs that are >30% Lorem Ipsum
                    all_paras.append(text)

        if all_paras:
            text = all_paras[0]
            # Truncate at sentence boundary (period, exclamation, question mark) within ~400 chars
            # This prevents cutting off mid-word while preserving complete thoughts
            max_len = 400
            if len(text) > max_len:
                # Try to find the last sentence-ending punctuation within the limit
                truncated = text[:max_len]
                last_period = max(
                    truncated.rfind('. '),
                    truncated.rfind('! '),
                    truncated.rfind('? ')
                )
                if last_period > 100:  # Ensure we have at least 100 chars
                    messaging["value_proposition"] = truncated[:last_period + 1]
                else:
                    # Fallback: just truncate at max_len
                    messaging["value_proposition"] = text[:max_len].rstrip() + '…'
            else:
                messaging["value_proposition"] = text

        # Key claims from H2s
        messaging["key_claims"] = h2_tags[:5]

        # CTA language
        for el in soup.find_all(["a", "button"]):
            text = el.get_text(separator=" ", strip=True)
            if 3 < len(text) < 60:
                messaging["cta_language"].append(text)
        messaging["cta_language"] = list(dict.fromkeys(messaging["cta_language"]))[:8]

        # Audience inference: Leave empty for LLM-based inference in analyzer.py
        # Regex heuristics produce unreliable results (e.g., "speed; practitioner")
        # The LLM in analyzer._infer_missing_audience() provides quality audience inference
        messaging["apparent_audience"] = ""

        # Get full page text for tone analysis and other heuristics
        full_text = soup.get_text(separator=" ", strip=True)

        # Tone heuristic
        word_count = len(full_text.split())
        exclamations = full_text.count("!")
        technical_terms = len(re.findall(
            r"\b(API|SDK|integration|compliance|enterprise|encryption|schema|protocol|authentication|authorization)\b",
            full_text, re.I
        ))
        if technical_terms > 5:
            messaging["tone"] = "Technical / B2B"
        elif exclamations > 3:
            messaging["tone"] = "Energetic / Consumer"
        else:
            messaging["tone"] = "Professional / Corporate"

        # ── Keyword targeting signals ─────────────────────────────────────────
        # Use LLM to intelligently extract keywords (industry-agnostic approach)
        # This replaces hard-coded keyword lists and works across any industry
        title_tag = soup.find("title")
        meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        title_raw = title_tag.get_text(separator=" ", strip=True) if title_tag else ""
        meta_raw = meta_desc_tag.get("content", "") if meta_desc_tag else ""

        # Call LLM to extract keywords intelligently
        keywords = await self._infer_keywords_with_llm(
            title=title_raw,
            primary_message=messaging.get("primary_message", ""),
            h2_tags=h2_tags,
            meta_description=meta_raw,
            key_claims=messaging.get("key_claims", [])
        )
        messaging["keyword_targets"] = keywords

        return messaging

    def _analyze_scannability(self, soup: BeautifulSoup) -> dict:
        """
        Analyze page scannability, messaging clarity, and content structure.
        """
        scannability = {
            "heading_count": 0,
            "heading_hierarchy_quality": "Good",
            "list_count": 0,
            "paragraph_count": 0,
            "avg_paragraph_length": 0,
            "has_clear_primary_message": False,
            "has_clear_value_prop": False,
            "cta_count": 0,
            "visual_hierarchy_score": 0,
            "content_organization": "Well-organized"
        }

        # Count heading elements
        h1_count = len(soup.find_all("h1"))
        h2_count = len(soup.find_all("h2"))
        h3_count = len(soup.find_all("h3"))
        scannability["heading_count"] = h1_count + h2_count + h3_count

        # Evaluate heading hierarchy quality
        if h1_count == 1 and h2_count > 0:
            scannability["heading_hierarchy_quality"] = "Good"
        elif h1_count == 0:
            scannability["heading_hierarchy_quality"] = "Poor - No H1"
        elif h1_count > 1:
            scannability["heading_hierarchy_quality"] = "Fair - Multiple H1s"
        else:
            scannability["heading_hierarchy_quality"] = "Fair"

        # Count lists (bullet points, numbered)
        lists = soup.find_all(["ul", "ol"])
        scannability["list_count"] = len(lists)

        # Count list items for total scannability
        list_items = soup.find_all("li")
        scannability["list_items"] = len(list_items)

        # Analyze paragraphs
        paragraphs = soup.find_all("p")
        scannability["paragraph_count"] = len(paragraphs)

        if paragraphs:
            total_length = sum(len(p.get_text(strip=True).split()) for p in paragraphs)
            scannability["avg_paragraph_length"] = round(total_length / len(paragraphs), 1)

        # Count CTAs
        cta_keywords = ["sign up", "get started", "try", "demo", "contact", "learn more", "download", "subscribe", "request", "book"]
        for link in soup.find_all(["a", "button"]):
            text = link.get_text(strip=True).lower()
            if any(kw in text for kw in cta_keywords):
                scannability["cta_count"] += 1

        # Check for clear primary message (H1 exists and has content)
        h1_elements = soup.find_all("h1")
        if h1_elements and h1_elements[0].get_text(strip=True):
            scannability["has_clear_primary_message"] = True

        # Check for clear value prop (has subheading or visible description after H1)
        h2_elements = soup.find_all("h2")
        if h2_elements and len(h2_elements[0].get_text(strip=True)) > 10:
            scannability["has_clear_value_prop"] = True

        # Visual hierarchy score (0-100)
        # Based on: heading count, list usage, CTA visibility
        score = min(100, (scannability["heading_count"] * 8) + (scannability["list_count"] * 15) + (scannability["cta_count"] * 10))
        scannability["visual_hierarchy_score"] = score

        # Content organization assessment
        if scannability["heading_count"] >= 3 and scannability["list_count"] >= 1:
            scannability["content_organization"] = "Well-organized"
        elif scannability["heading_count"] >= 2:
            scannability["content_organization"] = "Moderately organized"
        else:
            scannability["content_organization"] = "Minimal structure"

        return scannability

    def _compile_findings(self, result: dict) -> tuple[list, list]:
        """Compile issues and strengths from analysis."""
        issues = []
        strengths = []

        seo = result.get("seo_factors", {})
        tech = result.get("technical_factors", {})
        content = result.get("content_analysis", {})
        llm = result.get("llm_discoverability", {})
        geo = result.get("geo_factors", {})

        # SEO Issues
        if not seo.get("title"):
            issues.append({"category": "SEO", "severity": "high", "issue": "Missing page title"})
        elif seo.get("title_length", 0) > 60:
            issues.append({"category": "SEO", "severity": "medium", "issue": "Title too long (>60 chars)"})
        elif seo.get("title_length", 0) < 30:
            issues.append({"category": "SEO", "severity": "low", "issue": "Title may be too short (<30 chars)"})

        if not seo.get("meta_description"):
            issues.append({"category": "SEO", "severity": "high", "issue": "Missing meta description"})
        elif seo.get("meta_description_length", 0) > 160:
            issues.append({"category": "SEO", "severity": "medium", "issue": "Meta description too long (>160 chars)"})

        if len(seo.get("h1_tags", [])) == 0:
            issues.append({"category": "SEO", "severity": "high", "issue": "No H1 tag found"})
        elif len(seo.get("h1_tags", [])) > 1:
            issues.append({"category": "SEO", "severity": "medium", "issue": "Multiple H1 tags found"})

        if seo.get("images_without_alt", 0) > 0:
            issues.append({
                "category": "SEO",
                "severity": "medium",
                "issue": f"{seo['images_without_alt']} images missing alt text"
            })

        if not seo.get("og_tags"):
            issues.append({"category": "SEO", "severity": "medium", "issue": "Missing Open Graph tags"})

        # Technical Issues
        if not tech.get("https"):
            issues.append({"category": "Technical", "severity": "high", "issue": "Not using HTTPS"})

        if not tech.get("has_robots_txt"):
            issues.append({"category": "Technical", "severity": "medium", "issue": "No robots.txt found"})

        if not tech.get("has_sitemap"):
            issues.append({"category": "Technical", "severity": "medium", "issue": "No sitemap.xml found"})

        if not tech.get("mobile_friendly_hints"):
            issues.append({"category": "Technical", "severity": "high", "issue": "No viewport meta tag (mobile issues)"})

        # LLM Discoverability Issues
        if not llm.get("structured_content"):
            issues.append({"category": "LLM", "severity": "medium", "issue": "Content lacks clear structure (few headers)"})

        if not llm.get("faq_schema"):
            issues.append({"category": "LLM", "severity": "low", "issue": "No FAQ schema markup"})

        # GEO Issues
        if not geo.get("statistics_present"):
            issues.append({"category": "GEO", "severity": "medium", "issue": "No statistics or data points found"})

        if geo.get("lists_and_bullets", 0) < 2:
            issues.append({"category": "GEO", "severity": "low", "issue": "Limited use of lists for scannable content"})

        if not geo.get("citation_ready"):
            issues.append({"category": "GEO", "severity": "medium", "issue": "Content not optimized for AI citations"})

        # Strengths
        if seo.get("title") and 30 <= seo.get("title_length", 0) <= 60:
            strengths.append({"category": "SEO", "strength": "Well-optimized title length"})

        if seo.get("meta_description") and 120 <= seo.get("meta_description_length", 0) <= 160:
            strengths.append({"category": "SEO", "strength": "Good meta description length"})

        if content.get("has_structured_data"):
            strengths.append({"category": "SEO", "strength": f"Has structured data: {', '.join(content.get('structured_data_types', []))}"})

        if tech.get("https"):
            strengths.append({"category": "Technical", "strength": "Using HTTPS"})

        if tech.get("has_sitemap"):
            strengths.append({"category": "Technical", "strength": "Has sitemap.xml"})

        if llm.get("faq_schema"):
            strengths.append({"category": "LLM", "strength": "Has FAQ schema for AI search"})

        if geo.get("statistics_present"):
            strengths.append({"category": "GEO", "strength": "Contains statistics/data points"})

        if geo.get("comparison_tables"):
            strengths.append({"category": "GEO", "strength": "Has comparison tables"})

        return issues, strengths
