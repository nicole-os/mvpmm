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
import logging
import re
import os
import ssl
import certifi
from urllib.parse import urlparse, urljoin
from typing import Optional
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
from readability import Document
import tldextract
import litellm
from browser_manager import PlaywrightBrowserManager
from html.parser import HTMLParser

# curl_cffi: optional dependency for Cloudflare/WAF bypass via Chrome TLS impersonation.
# Falls back gracefully if not installed — aiohttp is still used for non-protected sites.
try:
    import curl_cffi.requests as cffi_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False


class TextExtractor(HTMLParser):
    """Extract plain text from HTML using standard library (Python 3.13 compatible)."""
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            setattr(self, f'in_{tag}', True)

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            setattr(self, f'in_{tag}', False)

    def handle_data(self, data):
        if not self.in_script and not self.in_style:
            self.text_parts.append(data)

    def get_text(self):
        text = ' '.join(self.text_parts)
        return re.sub(r'\s+', ' ', text).strip()


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

    async def _fetch_with_curl_cffi(self, url: str) -> tuple:
        """
        Fetch a URL using curl_cffi with Chrome TLS fingerprint impersonation.
        Bypasses Cloudflare and most WAF bot-protection walls that block aiohttp.
        Returns (html, status_code) or (None, 0) on failure.
        """
        if not CURL_CFFI_AVAILABLE:
            return None, 0
        try:
            loop = asyncio.get_event_loop()
            def _sync_fetch():
                r = cffi_requests.get(
                    url,
                    impersonate="chrome124",
                    timeout=20,
                    allow_redirects=True,
                )
                return r.text, r.status_code
            html, status = await loop.run_in_executor(None, _sync_fetch)
            logger.debug(f"curl_cffi: {url} → status={status}, size={len(html)} chars")
            return html, status
        except Exception as e:
            logger.warning(f"curl_cffi failed for {url}: {e}")
            return None, 0

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
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context, limit=10, limit_per_host=5)
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

                        # Check for HTTP error status codes
                        if response.status >= 400:
                            if response.status == 403:
                                # Likely Cloudflare or WAF — try Chrome TLS impersonation before giving up
                                logger.info(f"403 received, trying curl_cffi bypass: {url}")
                                html, cffi_status = await self._fetch_with_curl_cffi(url)
                                if html and cffi_status < 400:
                                    result["http_status"] = cffi_status
                                    logger.info(f"curl_cffi bypass succeeded: {url}")
                                else:
                                    result["status"] = "error"
                                    result["error"] = "Access Denied (403) — This site blocks automated access (Cloudflare or WAF protection detected)."
                                    return result
                            else:
                                result["status"] = "error"
                                if response.status == 404:
                                    result["error"] = "Page Not Found (404) — The URL does not exist or has been removed."
                                elif response.status >= 500:
                                    result["error"] = f"Server Error ({response.status}) — The server is currently unavailable or experiencing issues."
                                else:
                                    result["error"] = f"HTTP Error {response.status} — The server returned an error response."
                                return result
                        else:
                            html = await response.text()
                except ValueError as e:
                    # Handle other ValueError types
                    raise

                logger.debug(f"HTML fetched: {len(html)} bytes")
                soup = BeautifulSoup(html, "html.parser")
                doc = Document(html)

                # Detect bot-protection / CAPTCHA walls and JavaScript-heavy sites
                page_text = soup.get_text(" ", strip=True)
                word_count_check = len(page_text.split())
                logger.debug(f"After parsing: word_count={word_count_check}, elements={len(soup.find_all())}")
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
                    is_cookie_popup = any(sig in page_text.lower() for sig in ["cookie consent", "accept cookies", "cookie policy", "manage preferences", "gdpr"])
                    if is_cookie_popup:
                        # Cookie walls need JS interaction — try Playwright to click Accept
                        logger.info(f"Cookie consent wall detected, attempting Playwright bypass: {url}")
                        consent_html, _ = await PlaywrightBrowserManager.render_page_with_consent_bypass(url)
                        if consent_html:
                            consent_text = BeautifulSoup(consent_html, "html.parser").get_text(" ", strip=True)
                            consent_words = len(consent_text.split())
                            if consent_words > 100:
                                logger.info(f"Cookie consent bypass succeeded: {url} ({consent_words} words)")
                                html = consent_html
                                soup = BeautifulSoup(html, "html.parser")
                                doc = Document(html)
                                page_text = consent_text
                                word_count_check = consent_words
                                # Fall through to full analysis below
                            else:
                                result["status"] = "blocked"
                                result["error"] = "Cookie consent popup detected — unable to dismiss automatically."
                                result["http_status"] = response.status
                                return result
                        else:
                            result["status"] = "blocked"
                            result["error"] = "Cookie consent popup detected — unable to dismiss automatically."
                            result["http_status"] = response.status
                            return result
                    # Bot protection (Cloudflare etc.) — try curl_cffi Chrome impersonation
                    logger.info(f"Bot protection detected, trying curl_cffi bypass: {url}")
                    cffi_html, cffi_status = await self._fetch_with_curl_cffi(url)
                    if cffi_html and cffi_status < 400:
                        cffi_text = BeautifulSoup(cffi_html, "html.parser").get_text(" ", strip=True)
                        cffi_words = len(cffi_text.split())
                        cffi_blocked = cffi_words < 100 and any(sig in cffi_text.lower() for sig in block_signals)
                        if not cffi_blocked:
                            logger.info(f"curl_cffi bypass succeeded: {url}")
                            html = cffi_html
                            soup = BeautifulSoup(html, "html.parser")
                            doc = Document(html)
                            page_text = cffi_text
                            word_count_check = cffi_words
                        else:
                            result["status"] = "blocked"
                            result["error"] = "Bot protection detected — the site returned a security checkpoint page. Data for this competitor is unavailable."
                            result["http_status"] = response.status
                            return result
                    else:
                        result["status"] = "blocked"
                        result["error"] = "Bot protection detected — the site returned a security checkpoint page. Data for this competitor is unavailable."
                        result["http_status"] = response.status
                        return result

                # Detect JavaScript-heavy sites (very low word count with no bot protection message)
                if await self._should_render_with_playwright(html, word_count_check):
                    logger.debug(f"JS-heavy site, using Playwright: {url}")
                    rendered_html = await self._render_with_playwright(url)

                    if rendered_html:
                        # Re-parse with rendered HTML
                        html = rendered_html
                        soup = BeautifulSoup(html, "html.parser")
                        doc = Document(html)
                        # Recalculate page text and word count
                        page_text = soup.get_text(" ", strip=True)
                        word_count_check = len(page_text.split())
                        logger.debug(f"Playwright re-parse complete. word_count={word_count_check}")
                    else:
                        # Playwright rendering failed - continue with limited data
                        result["status"] = "requires-javascript"
                        result["warning"] = "This site requires JavaScript rendering. Playwright rendering was attempted but failed (timeout or error). Limited data available."
                        result["http_status"] = response.status

                # Analyze all aspects
                result["_debug"] = {
                    "html_size": len(html),
                    "soup_elements": len(soup.find_all()),
                    "page_text_length": len(soup.get_text(" ", strip=True))
                }

                result["seo_factors"] = self._analyze_seo(soup, url, doc)

                # Remove images_needing_alt from SEO factors (no longer used)
                result["seo_factors"].pop("images_needing_alt", [])

                result["content_analysis"] = await self._analyze_content(soup, doc, html, url)
                result["technical_factors"] = await self._analyze_technical(session, url, soup, response)
                result["llm_discoverability"] = await self._analyze_llm_factors(soup, html)
                result["geo_factors"] = await self._analyze_geo_factors(soup, html)
                result["page_messaging"] = await self._analyze_page_messaging(soup, result["content_analysis"].get("cta_elements", []))
                result["scannability"] = self._analyze_scannability(soup)

                # Compile issues and strengths
                result["issues"], result["strengths"] = self._compile_findings(result)

        except asyncio.TimeoutError:
            result["status"] = "timeout"
            result["error"] = "Request timed out"
        except aiohttp.ClientError as e:
            # Check if it's an oversized header error - try Playwright fallback
            if "header value is too long" in str(e).lower() or "8190 bytes" in str(e):
                try:
                    logger.warning(f"HTTP header too large for {url}, using Playwright fallback")
                    rendered_html, metadata = await PlaywrightBrowserManager.render_page(url)
                    if not rendered_html:
                        result["status"] = "error"
                        result["error"] = f"Failed to fetch page: Server response headers are oversized, and Playwright rendering also failed."
                        return result

                    # Re-run analysis with Playwright-rendered HTML
                    soup = BeautifulSoup(rendered_html, "lxml")
                    doc = Document(rendered_html)
                    result["seo_factors"] = self._analyze_seo(soup, url, doc)
                    result["seo_factors"].pop("images_needing_alt", [])
                    result["content_analysis"] = await self._analyze_content(soup, doc, rendered_html, url)
                    result["technical_factors"] = await self._analyze_technical(None, url, soup, None)
                    result["llm_discoverability"] = await self._analyze_llm_factors(soup, rendered_html)
                    result["geo_factors"] = await self._analyze_geo_factors(soup, rendered_html)
                    result["page_messaging"] = await self._analyze_page_messaging(soup, result["content_analysis"].get("cta_elements", []))
                    result["scannability"] = self._analyze_scannability(soup)
                    result["issues"], result["strengths"] = self._compile_findings(result)
                    result["header_warning"] = "Site has oversized HTTP headers (likely large cookies). Used Playwright rendering as fallback. Note: Robots.txt and Sitemap detection were skipped for this site (requires direct HTTP access). They may exist but weren't checked."
                    result["status"] = "success"
                    return result
                except (ValueError, aiohttp.ClientError, asyncio.TimeoutError) as fetch_error:
                    # Only catch rendering/fetching errors, let analysis errors propagate
                    logger.error(f"Playwright rendering failed: {str(fetch_error)}")
                    result["status"] = "error"
                    result["error"] = f"Failed to fetch page: Server response headers are oversized, and Playwright rendering also failed."
                    return result

            result["status"] = "error"
            result["error"] = f"Connection error: {str(e)}"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        return result

    def _strip_consent_and_nav(self, html: str) -> str:
        """
        Remove common consent/nav/footer elements for LLM CTA detection.
        Uses targeted ID/class pattern matching to avoid removing content-bearing elements.
        Does NOT blindly remove all header/nav/footer tags (too aggressive, breaks content).
        """
        soup = BeautifulSoup(html, "html.parser")

        # Remove by ID/class patterns ONLY (more surgical than tag-based removal)
        removal_patterns = [
            # Consent/GDPR banners
            {"id": re.compile(r"^(cookie|consent|gdpr|privacy|notice)", re.I)},
            {"class": re.compile(r"(cookie-banner|cookie-consent|consent-banner|gdpr-banner|privacy-banner)", re.I)},
            # Navigation patterns
            {"id": re.compile(r"^(navbar|navigation|header-nav|main-nav|top-nav|megamenu)", re.I)},
            {"class": re.compile(r"(navbar|nav-bar|main-nav|top-nav|header-navigation|nav-menu|megamenu)", re.I)},
            # Modals and overlays
            {"class": re.compile(r"(modal|dialog|popup|overlay)", re.I)},
            # Language selectors and accessibility controls
            {"class": re.compile(r"(language-selector|lang-select|lang-dropdown|accessibility|a11y|skip-to|skip-link)", re.I)},
            # Footer content
            {"id": re.compile(r"^(footer|site-footer|page-footer|main-footer)", re.I)},
            {"class": re.compile(r"(site-footer|footer-nav|footer-links|footer-menu)", re.I)},
        ]

        for pattern in removal_patterns:
            for el in soup.find_all(True, attrs=pattern):
                el.decompose()

        return str(soup)

    def _extract_domain(self, url: str) -> str:
        """Extract the domain from a URL."""
        extracted = tldextract.extract(url)
        return f"{extracted.domain}.{extracted.suffix}"

    def _analyze_seo(self, soup: BeautifulSoup, url: str, doc: Document = None) -> dict:
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

        # Word count - use full soup text so nav/hero/feature sections are all counted.
        # readability doc.summary() is too aggressive for homepages and strips most content.
        try:
            seo["word_count"] = len(soup.get_text(separator=" ", strip=True).split())
        except Exception:
            seo["word_count"] = 0

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

                logger.debug(f"LLM: generating alt text with {model}")
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
                    logger.debug(f"LLM: generated alt text for {filename[:30]}")

            except Exception as e:
                logger.warning(f"LLM alt text generation failed for {filename}: {str(e)}")
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
            html, metadata = await browser_manager.render_page(url, timeout=20)

            if html:
                logger.debug(f"Playwright rendered: {url}")
                return html
            else:
                logger.warning(f"Playwright timeout/error for {url}, falling back to static HTML")
                return None

        except Exception as e:
            logger.error(f"Playwright error for {url}: {str(e)}")
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
            logger.debug(f"LLM: identifying keywords with {model}")

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
            logger.debug(f"LLM keywords: {keywords_str}")

            # Parse comma-separated keywords
            keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
            return keywords[:10]  # Return up to 10 keywords

        except Exception as e:
            logger.warning(f"LLM keyword identification failed: {str(e)}")
            return []

    async def _analyze_content(self, soup: BeautifulSoup, doc: Document, html: str, url: str) -> dict:
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

        # Extract main content using readability
        try:
            readability_summary = doc.summary()
            clean_text = BeautifulSoup(readability_summary, "html.parser").get_text(strip=True)
            content["main_content"] = readability_summary[:2000]
            content["content_length"] = len(clean_text.split())
        except Exception as e:
            # Fallback to full page text if readability fails
            try:
                full_page_text = soup.get_text(separator=" ", strip=True)
                content["main_content"] = full_page_text[:2000]
                content["content_length"] = len(full_page_text.split())
            except:
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

        # CTAs — Use LLM-based detection (Claude: URL-based, others: text-based)
        page_title = soup.find("title")
        page_title_text = page_title.get_text(strip=True) if page_title else ""

        cta_results = await self._infer_cta_elements_with_llm(url, html, page_title_text)
        content["cta_elements"] = cta_results

        return content

    async def _analyze_technical(self, session: aiohttp.ClientSession, url: str, soup: BeautifulSoup, response) -> dict:
        """Analyze technical SEO factors."""
        # Use final URL (after redirects) for HTTPS check (fallback to input URL if response is None)
        final_url = str(response.url) if response else url
        technical = {
            "https": final_url.startswith("https"),
            "response_time_ms": 0,
            "has_robots_txt": False,
            "has_sitemap": False,
            "mobile_friendly_hints": [],
            "page_speed_hints": []
        }

        # Mobile hints
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if viewport:
            technical["mobile_friendly_hints"].append("Has viewport meta tag")

        # Parse URL for robots.txt and sitemap detection
        parsed = urlparse(url)

        # Check robots.txt (only if session available)
        robots_content = ""
        if session:
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            try:
                async with session.get(robots_url) as robots_resp:
                    if robots_resp.status == 200:
                        technical["has_robots_txt"] = True
                        robots_content = await robots_resp.text()
            except Exception:
                pass

        # Enhanced sitemap detection
        # Strategy: 1) Check robots.txt for Sitemap entries, 2) Check common patterns, 3) Fall back to /sitemap.xml
        sitemap_urls_to_check = []

        # Parse robots.txt for Sitemap: entries
        if robots_content:
            sitemap_lines = [line.strip() for line in robots_content.split('\n') if line.lower().startswith('sitemap:')]
            for line in sitemap_lines:
                # Extract URL after "Sitemap:"
                sitemap_candidate = line.split(':', 1)[1].strip()
                if sitemap_candidate:
                    sitemap_urls_to_check.append(sitemap_candidate)

        # Add common sitemap naming patterns to check
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        common_patterns = [
            f"{base_url}/sitemap_index.xml",
            f"{base_url}/sitemap.xml",
            f"{base_url}/sitemap1.xml",
            f"{base_url}/sitemap-index.xml",
        ]
        sitemap_urls_to_check.extend(common_patterns)

        # Remove duplicates while preserving order
        sitemap_urls_to_check = list(dict.fromkeys(sitemap_urls_to_check))

        # Check each sitemap URL (only if session available)
        if session:
            for sitemap_url in sitemap_urls_to_check:
                try:
                    async with session.get(sitemap_url, timeout=aiohttp.ClientTimeout(total=5)) as sitemap_resp:
                        if sitemap_resp.status == 200:
                            technical["has_sitemap"] = True
                            break  # Found at least one sitemap, no need to check others
                except Exception:
                    continue

        return technical

    async def _analyze_llm_factors(self, soup: BeautifulSoup, html: str) -> dict:
        """
        Analyze factors that affect LLM discoverability and AI search results.
        Uses LLM-based intelligent analysis instead of hard-coded patterns.
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

        # Get full page text (needed for FAQ detection and fallback)
        full_page_text = soup.get_text(separator=" ", strip=True)

        # Get content for LLM analysis - use FULL page text for LLM methods
        # (LLM needs full context to accurately detect FAQ, How-To, etc.)
        extracted_text = None
        try:
            doc = Document(html)
            main_content = doc.summary()
            extracted_text = BeautifulSoup(main_content, "html.parser").get_text(separator=" ", strip=True)

            # If Readability extraction is too small (< 20% of full page), use full page text instead
            # This handles JS-heavy pages where Readability can't extract dynamic content
            if len(extracted_text.split()) < max(200, len(full_page_text.split()) * 0.2):
                page_text = full_page_text
            else:
                page_text = full_page_text  # Use full page for LLM analysis, not truncated
        except:
            # Fallback to full page text if readability fails
            page_text = full_page_text

        h1_tags = [t.get_text(separator=" ", strip=True) for t in soup.find_all("h1")]
        h2_tags = [t.get_text(separator=" ", strip=True) for t in soup.find_all("h2")][:10]

        # Use LLM to detect FAQ content - use FULL page text since FAQs often appear at bottom
        llm["faq_schema"] = await self._infer_faq_content_with_llm(full_page_text, h2_tags)

        # Use LLM to detect How-To content
        llm["how_to_schema"] = await self._infer_howto_content_with_llm(
            page_text,
            h1_tags[0] if h1_tags else "",
            h2_tags
        )

        # Check for clear sections (structural heuristic - still valid)
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

    async def _analyze_geo_factors(self, soup: BeautifulSoup, html: str) -> dict:
        """Analyze Generative Engine Optimization (GEO) factors using LLM intelligence."""
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

        # Get content for LLM analysis - extract main content first for better accuracy
        full_page_text = soup.get_text(separator=" ", strip=True)
        extracted_text = None

        try:
            doc = Document(html)
            main_content = doc.summary()
            extracted_text = BeautifulSoup(main_content, "html.parser").get_text(separator=" ", strip=True)

            # If Readability extraction is too small (< 20% of full page), use full page text instead
            # This handles JS-heavy pages where Readability can't extract dynamic content
            if len(extracted_text.split()) < max(200, len(full_page_text.split()) * 0.2):
                page_text = full_page_text
            else:
                page_text = extracted_text
        except:
            # Fallback to full page text if readability fails
            page_text = full_page_text
        h1_tags = [t.get_text(separator=" ", strip=True) for t in soup.find_all("h1")]
        h2_tags = [t.get_text(separator=" ", strip=True) for t in soup.find_all("h2")][:10]

        # Use LLM to detect statistics (more accurate than regex)
        geo["statistics_present"] = await self._infer_statistics_with_llm(page_text)

        # Check for lists (structural heuristic - still valid)
        lists = soup.find_all(["ul", "ol"])
        geo["lists_and_bullets"] = len(lists)

        # Use LLM to detect comparative content (more accurate than just checking for <table>)
        geo["comparison_tables"] = await self._infer_comparative_content_with_llm(
            page_text,
            h1_tags[0] if h1_tags else "",
            h2_tags
        )

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

        # Use LLM to assess citation readiness (more nuanced than basic heuristic)
        geo["citation_ready"] = await self._infer_citation_readiness_with_llm(
            page_text,
            geo["statistics_present"],
            h2_tags
        )

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
            logger.warning(f"LLM keywords error: {str(e)}")
            return []

    async def _infer_faq_content_with_llm(self, page_text: str, h2_tags: list) -> bool:
        """
        Use LLM to determine if page has Q&A content optimized for AI search.
        More accurate than checking for "faqpage" string in JSON-LD.

        This method receives FULL page text so it can catch FAQs anywhere on the page
        (they often appear at the bottom, not just in main content extraction).
        """
        prompt = f"""Does this webpage contain a FAQ section, Q&A content, or frequently asked questions?

Look for:
- Explicit "FAQ" or "Frequently Asked Questions" section
- Questions formatted as Q&A with answers
- Common customer/user questions and their answers
- "Ask us..." or "Common questions" sections
- Question-formatted headings (What is..., How do I..., etc.)

Page Headings (H2):
{chr(10).join(h2_tags[:10])}

Page Content:
{page_text}

Respond with ONLY "yes" or "no" — nothing else."""

        try:
            response = await litellm.acompletion(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=5
            )
            answer = response.choices[0].message.content.strip().lower()
            return "yes" in answer
        except Exception as e:
            logger.warning(f"LLM FAQ error: {str(e)}")
            return False

    async def _infer_howto_content_with_llm(self, page_text: str, h1: str, h2_tags: list) -> bool:
        """
        Use LLM to detect step-by-step guides optimized for user intent.
        More accurate than checking for "howto" string in JSON-LD.
        """
        prompt = f"""Is this webpage a "How-To" guide, tutorial, or step-by-step instructions?

Look for:
- Step-by-step numbered or sequential instructions
- Tutorial format (Step 1, Step 2, etc.)
- How-to guides or "How to..." content
- Instructions for users to follow
- Sequential procedures or processes

Primary Heading (H1):
{h1}

Section Headings (H2):
{chr(10).join(h2_tags[:10])}

Page Content:
{page_text}

Respond with ONLY "yes" or "no" — nothing else."""

        try:
            response = await litellm.acompletion(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=5
            )
            answer = response.choices[0].message.content.strip().lower()
            return "yes" in answer
        except Exception as e:
            logger.warning(f"LLM HowTo error: {str(e)}")
            return False

    async def _infer_statistics_with_llm(self, page_text: str) -> bool:
        """
        Use LLM to identify if page contains meaningful statistics and data-driven insights.
        More accurate than regex pattern matching.
        """
        prompt = f"""Does this webpage contain statistics, data points, research findings, or quantitative evidence?

Look for:
- Percentages, numerical data, or statistics (e.g., "75% of users", "increase of 129%")
- Data from studies, surveys, or research
- Charts, metrics, or quantitative findings
- Benchmarks or performance data
- Any numbers with context supporting claims

Page Content:
{page_text}

Respond with ONLY "yes" or "no" — nothing else."""

        try:
            response = await litellm.acompletion(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=5
            )
            answer = response.choices[0].message.content.strip().lower()
            return "yes" in answer
        except Exception as e:
            logger.warning(f"LLM statistics error: {str(e)}")
            return False

    async def _infer_comparative_content_with_llm(self, page_text: str, h1: str, h2_tags: list) -> bool:
        """
        Use LLM to detect if content is comparative/evaluative (not just layout tables).
        More accurate than checking if any <table> element exists.
        """
        prompt = f"""Does this webpage contain comparative or evaluative content (not just layout tables)?

Look for:
- Comparisons between products, services, or features
- Pros and cons lists
- Evaluations or reviews
- Comparison tables or side-by-side features
- "vs" or "comparison" content
- Which option is better for different use cases

Primary Heading (H1):
{h1}

Section Headings (H2):
{chr(10).join(h2_tags[:10])}

Page Content:
{page_text}

Respond with ONLY "yes" or "no" — nothing else."""

        try:
            response = await litellm.acompletion(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=5
            )
            answer = response.choices[0].message.content.strip().lower()
            return "yes" in answer
        except Exception as e:
            logger.warning(f"LLM comparative error: {str(e)}")
            return False

    async def _infer_citation_readiness_with_llm(self, page_text: str, has_stats: bool, h2_tags: list) -> bool:
        """
        Use LLM to assess if content is structured and authoritative enough for AI citation.
        More nuanced than basic heuristic (stats + lists > 2).
        """
        prompt = f"""Is this webpage well-structured and authoritative enough for an AI system to cite as a source?

Look for:
- Clear, logical organization with sections
- Well-sourced claims or cited studies/data
- Authoritative tone and credible information
- Comprehensive coverage (not superficial)
- Facts presented clearly and accurately
- Sources attributed properly
- Data, statistics, or research findings

Section Headings (H2):
{chr(10).join(h2_tags[:10])}

Contains Statistics/Data: {has_stats}

Page Content:
{page_text}

Respond with ONLY "yes" or "no" — nothing else."""

        try:
            response = await litellm.acompletion(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=5
            )
            answer = response.choices[0].message.content.strip().lower()
            return "yes" in answer
        except Exception as e:
            logger.warning(f"LLM citation error: {str(e)}")
            return False

    async def _infer_cta_elements_with_llm(self, url: str, page_html: str, page_title: str) -> list:
        """
        Use LLM to identify primary CTAs. Intelligently chooses approach:

        - Claude models (claude-*): Uses URL-based analysis (LLM visits the page)
          ✓ Sees actual visual hierarchy, button styling, prominence
          ✓ Distinguishes CTAs from navigation by visual design
          ✓ Detects JavaScript-rendered CTAs

        - Other models (GPT-4o, etc.): Uses HTML text-based analysis
          ✓ Works with rendered HTML content
          ✓ No web browsing required
          ✓ Fast and reliable

        IMPORTANT for GitHub documentation:
        - LLM_MODEL must be set (e.g., claude-3-5-sonnet or gpt-4o)
        - Claude models require Anthropic API key
        - GPT-4o requires OpenAI API key

        Returns: [
            {
                "text": "Get a Demo",
                "type": "demo",
                "location": "hero",
                "is_cta": True,
                "confidence": "high"
            },
            ...
        ]
        """
        if not url or not page_html:
            logger.debug("LLM CTA: missing URL or HTML, skipping")
            return []

        model = os.getenv("LLM_MODEL")
        if not model:
            logger.warning("LLM_MODEL not set — CTA detection disabled. Set LLM_MODEL in .env")
            return []

        # Determine approach based on model
        use_url_approach = "claude" in model.lower()

        if use_url_approach:
            # Claude: URL-based approach (LLM visits the page)
            prompt = f"""Visit this website and identify all visible call-to-action buttons and links that drive business conversions:

URL: {url}

FOCUS ON: Primary CTAs that convert visitors (prominent buttons/links that drive action)
- "Get a Demo", "Request a Demo", "Schedule a Demo", "Book a Demo"
- "Free Trial", "Start Free Trial", "Try for Free", "Start for Free"
- "Contact Us", "Contact Sales", "Talk to Sales", "Get in Touch", "Request Info"
- "Sign Up", "Create Account", "Get Started", "Register", "Join Now"
- "Buy Now", "Purchase", "Add to Cart", "Pricing", "Get Pricing"
- "Download", "Download PDF", "Get the Guide", "Download the Report", "Get the Whitepaper"
- "Learn More", "View Details", "See How It Works" (if prominently displayed as primary action)

IGNORE - These are NOT CTAs:
- Navigation: Home, About, Blog, Pricing, Products, Solutions, Services, Docs, Help, Support
- Language selectors: "English", "Español", "Deutsch", language options
- Accessibility: "Skip to content", "High Contrast", "Change font size"
- Authentication: "Log In", "Sign In", "Log Out", "My Account", "Dashboard"
- Footer: "Terms", "Privacy", "Cookies", "Copyright", "Sitemap"
- Social media: "Facebook", "Twitter", "LinkedIn", "Instagram", "YouTube"
- Navigation controls: "Menu", "Close Menu", "Search", "Filter", "Sort"

For each PRIMARY CTA, provide:
- text: exact button/link text
- location: header, hero, main content, sidebar, footer, etc.
- action: demo, contact, signup, download, trial, pricing, etc.

Return JSON array:
[
  {{"text": "Get a Demo", "location": "hero section", "action": "demo"}},
  {{"text": "Start Free Trial", "location": "hero", "action": "trial"}}
]

ONLY return JSON, no other text."""
        else:
            # Other models: Structured button extraction approach
            # Extract actual <button> and <a> elements with attributes instead of flat text
            soup = BeautifulSoup(page_html, "lxml")

            # Collect all buttons and links with their attributes
            buttons_and_links = []

            for element in soup.find_all(['button', 'a']):
                text = element.get_text(strip=True)
                if not text or len(text) < 2:
                    continue

                # Skip obvious navigation/utility elements
                nav_keywords = ['skip', 'home', 'about', 'blog', 'login', 'sign in', 'deutsch', 'español',
                               'português', 'français', 'english', 'select a language', 'high contrast',
                               'menu', 'close', 'search']
                if any(kw in text.lower() for kw in nav_keywords):
                    continue

                # Get element attributes
                element_id = element.get('id', '')
                element_class = ' '.join(element.get('class', []))
                href = element.get('href', '')
                aria_label = element.get('aria-label', '')
                data_attrs = {k: v for k, v in element.attrs.items() if k.startswith('data-')}

                buttons_and_links.append({
                    'text': text,
                    'tag': element.name,
                    'id': element_id,
                    'class': element_class,
                    'href': href,
                    'aria_label': aria_label,
                    'data_attrs': data_attrs
                })

            # Format buttons/links as structured data for LLM
            structured_buttons = "\n".join([
                f"- Text: '{b['text']}' | Type: {b['tag']} | Href: {b['href'][:50] if b['href'] else 'N/A'} | Class: {b['class'][:80] if b['class'] else 'N/A'}"
                for b in buttons_and_links
            ])

            prompt = f"""Analyze these webpage buttons and links to identify primary call-to-action elements that drive business conversions.

Page Title: {page_title}

Buttons and Links Found:
{structured_buttons}

IDENTIFY: Which of these are PRIMARY CTAs that convert (demo, signup, trial, contact, download, pricing, etc.)?

EXCLUDE: Navigation links (Home, About, Blog, Products, Pricing as main nav), authentication (Login, Sign In), language/accessibility, footer-only links, social media

For EACH primary CTA, provide:
- text: exact text on the button/link
- location: where it appears on page (header, hero section, main content, etc.)
- action: what it does (demo, contact, signup, download, trial, pricing, etc.)

Return ONLY this JSON format (no markdown, no explanation):
[
  {{"text": "Get a Demo", "location": "hero section", "action": "demo"}},
  {{"text": "Contact Sales", "location": "header", "action": "contact"}}
]"""

        try:
            approach = "URL-based (Claude)" if use_url_approach else "text-based"
            logger.debug(f"LLM CTA: using {approach} with {model}")

            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=1000,
                timeout=60
            )

            result_text = response.choices[0].message.content.strip()

            # Strip markdown code block wrapper if GPT-4o returns JSON wrapped in ```json
            if result_text.startswith("```"):
                # Extract content between backticks
                parts = result_text.split("```")
                if len(parts) >= 2:
                    result_text = parts[1]
                    # If it starts with "json", skip that line
                    if result_text.startswith("json"):
                        result_text = result_text[4:].lstrip()

            # Parse JSON response
            try:
                import json
                results = json.loads(result_text)

                if not isinstance(results, list):
                    logger.warning(f"LLM CTA: expected JSON array, got {type(results)}")
                    return []

                # Validate and format results
                validated = []
                for item in results:
                    text = item.get("text", "").strip()
                    if text and len(text) > 2:  # Valid text
                        validated.append({
                            "text": text,
                            "type": item.get("action", "other"),
                            "location": item.get("location", "unknown"),
                            "is_cta": True,
                            "confidence": "high"
                        })

                logger.debug(f"LLM CTA: found {len(validated)} CTAs")
                return validated

            except json.JSONDecodeError as e:
                logger.warning(f"LLM CTA: JSON parse error: {str(e)[:100]}")
                logger.debug(f"LLM CTA response preview: {result_text[:200]}")
                return []

        except Exception as e:
            logger.error(f"LLM CTA error: {str(e)}")
            return []

    async def _infer_value_proposition_with_llm(
        self,
        h1: str,
        h2_tags: list,
        meta_description: str,
        main_content_sample: str
    ) -> dict:
        """
        Use LLM to identify and extract the value proposition from page content.

        Unlike the heuristic approach (first paragraph), this uses semantic understanding
        to identify what unique value/benefit the company offers, avoiding persona
        descriptions, feature lists, and other non-value-prop content.

        Returns: {
            "value_proposition": str or "",
            "confidence": "high" | "medium" | "low"
        }
        """
        prompt = f"""Analyze this webpage and identify the core VALUE PROPOSITION.

The value proposition is the unique benefit or core promise the company makes - what problem they solve or value they deliver.

DO NOT extract:
- Persona descriptions ("I am a security buyer...")
- Feature lists ("We offer X, Y, Z")
- Taglines or slogans alone
- Calls to action
- Navigation content

DO extract:
- The main benefit/promise (what makes them different)
- The core problem they solve
- The outcome customers get
- 1-2 sentences max, 50-250 characters

Page Data:
Title: {meta_description[:100] if meta_description else "N/A"}
H1 (primary message): {h1}
H2s (key points): {', '.join(h2_tags[:3]) if h2_tags else "N/A"}
Content sample (first 1500 chars):
{main_content_sample[:1500]}

Extract the VALUE PROPOSITION. Return ONLY a JSON object with no explanation:
{{
  "value_proposition": "1-2 sentence description of core value/benefit",
  "confidence": "high|medium|low"
}}

If no clear value proposition exists, return empty string and low confidence."""

        try:
            response = await litellm.acompletion(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,  # Deterministic
                max_tokens=150
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON response
            try:
                import json
                result = json.loads(result_text)
                value_prop = result.get("value_proposition", "").strip()
                confidence = result.get("confidence", "low")

                # Only accept if confidence is medium or high, or if we got a meaningful result
                if value_prop and len(value_prop) > 15:
                    logger.debug(f"LLM value prop extracted (confidence: {confidence}): {value_prop[:80]}")
                    return {
                        "value_proposition": value_prop,
                        "confidence": confidence
                    }
                else:
                    logger.debug("LLM value prop: no meaningful value prop found")
                    return {"value_proposition": "", "confidence": "low"}

            except json.JSONDecodeError:
                logger.warning(f"LLM value prop: invalid JSON response: {result_text[:100]}")
                return {"value_proposition": "", "confidence": "low"}

        except Exception as e:
            logger.error(f"LLM value prop error: {str(e)}")
            return {"value_proposition": "", "confidence": "low"}

    async def _analyze_page_messaging(self, soup: BeautifulSoup, cta_elements: list = None) -> dict:
        """
        Infer the page's core message, intended audience, and value proposition
        from the visible text — hero copy, headings, CTAs, and body content.
        Uses provided CTA elements from structured extraction instead of extracting from page.
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

        # Value Proposition — Use LLM-based extraction instead of heuristics
        # This handles persona descriptions, footnotes, and other edge cases better
        meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        meta_description = meta_desc_tag.get("content", "") if meta_desc_tag else ""

        # Get a sample of main content for LLM context
        main_content_sample = soup.get_text(separator=" ", strip=True)[:2000]

        # Call LLM to extract value proposition
        value_prop_result = await self._infer_value_proposition_with_llm(
            h1=messaging.get("primary_message", ""),
            h2_tags=h2_tags,
            meta_description=meta_description,
            main_content_sample=main_content_sample
        )
        messaging["value_proposition"] = value_prop_result.get("value_proposition", "")

        # Key claims from H2s
        messaging["key_claims"] = h2_tags[:5]

        # CTA language — Use provided CTA elements from structured extraction (not old page extraction)
        if cta_elements:
            messaging["cta_language"] = [cta.get("text", "") for cta in cta_elements[:8]]
        else:
            # Fallback (shouldn't happen, but just in case)
            messaging["cta_language"] = []

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
