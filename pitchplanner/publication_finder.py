"""
Publication Finder Module
Fetches recent articles from B2B tech publications to reverse-engineer
journalist coverage patterns for beat matching and pitch personalization.

Default publication list covers broad B2B tech — startups, enterprise, AI,
cloud, developer tools, business leadership. Replace or extend via the
Publication Library in the UI, or edit PUBLICATIONS directly.
"""

import asyncio
import re
from typing import Optional
import aiohttp
from bs4 import BeautifulSoup


# Curated publication list with RSS feeds and metadata
# Tiered by audience and relevance to B2B tech startups broadly.
# Replace or extend this list via the Publication Library in the UI.
PUBLICATIONS = [
    # ── Tier 1 — Broad Tech & Startup Press ───────────────────────────
    {
        "name": "TechCrunch",
        "domain": "techcrunch.com",
        "tier": 1,
        "beat": "startups, funding, enterprise tech, AI",
        "audience": "Founders, investors, tech industry operators",
        "rss": "https://techcrunch.com/feed/",
        "description": "Definitive startup and venture capital publication — product launches, funding rounds, enterprise tech, AI"
    },
    {
        "name": "VentureBeat",
        "domain": "venturebeat.com",
        "tier": 1,
        "beat": "enterprise AI, cloud, data, digital transformation",
        "audience": "Enterprise technology decision makers, IT and business leaders",
        "rss": "https://venturebeat.com/feed/",
        "description": "Enterprise AI, cloud infrastructure, business software, digital transformation"
    },
    {
        "name": "Wired",
        "domain": "wired.com",
        "tier": 1,
        "beat": "technology, culture, science, policy",
        "audience": "Tech-savvy general audience, executives, policy makers",
        "rss": "https://www.wired.com/feed/rss",
        "description": "Long-form technology journalism covering innovation, culture, security, and business"
    },
    {
        "name": "MIT Technology Review",
        "domain": "technologyreview.com",
        "tier": 1,
        "beat": "AI, deep tech, research, emerging technology",
        "audience": "Researchers, executives, informed general audience",
        "rss": "https://www.technologyreview.com/feed/",
        "description": "Rigorous coverage of emerging technology — AI, biotech, energy, computing"
    },
    {
        "name": "The Verge",
        "domain": "theverge.com",
        "tier": 1,
        "beat": "consumer tech, product launches, big tech, policy",
        "audience": "Mainstream tech audience, consumers, early adopters",
        "rss": "https://www.theverge.com/rss/index.xml",
        "description": "Consumer and enterprise technology — product launches, big tech news, policy"
    },
    {
        "name": "Ars Technica",
        "domain": "arstechnica.com",
        "tier": 1,
        "beat": "deep tech, science, security, open source",
        "audience": "Technical audience, developers, engineers, power users",
        "rss": "https://feeds.arstechnica.com/arstechnica/index",
        "description": "In-depth technical coverage — computing, science, security, policy"
    },
    # ── Tier 1 — Business & Leadership Press ──────────────────────────
    {
        "name": "Fortune",
        "domain": "fortune.com",
        "tier": 1,
        "beat": "business leadership, technology, finance",
        "audience": "C-suite executives, investors, business decision makers",
        "rss": "https://fortune.com/feed/",
        "description": "Business technology, executive profiles, Fortune 500 strategy, AI and future of work"
    },
    {
        "name": "Fast Company",
        "domain": "fastcompany.com",
        "tier": 1,
        "beat": "innovation, startups, leadership, workplace",
        "audience": "Business leaders, entrepreneurs, creative professionals",
        "rss": "https://www.fastcompany.com/latest/rss",
        "description": "Innovation, startup stories, leadership, design, and the future of work"
    },
    # ── Tier 2 — Enterprise & B2B Tech ────────────────────────────────
    {
        "name": "ZDNet",
        "domain": "zdnet.com",
        "tier": 2,
        "beat": "enterprise IT, cloud, software, security",
        "audience": "IT professionals, enterprise buyers, business leaders",
        "rss": "https://www.zdnet.com/news/rss.xml",
        "description": "Enterprise technology news — cloud, software, security, AI tools for business"
    },
    {
        "name": "TechRepublic",
        "domain": "techrepublic.com",
        "tier": 2,
        "beat": "enterprise IT, productivity, cloud, AI tools",
        "audience": "IT managers, system admins, enterprise decision makers",
        "rss": "https://www.techrepublic.com/rssfeeds/articles/",
        "description": "Practical enterprise IT — cloud tools, AI, security, productivity, best practices"
    },
    {
        "name": "SiliconANGLE",
        "domain": "siliconangle.com",
        "tier": 2,
        "beat": "cloud, AI, data, enterprise startups",
        "audience": "Enterprise tech buyers, CIOs, IT leaders",
        "rss": "https://siliconangle.com/feed/",
        "description": "Cloud infrastructure, AI platforms, enterprise software — deep B2B coverage"
    },
    {
        "name": "InfoWorld",
        "domain": "infoworld.com",
        "tier": 2,
        "beat": "software development, cloud, open source, DevOps",
        "audience": "Developers, software architects, engineering leaders",
        "rss": "https://www.infoworld.com/index.rss",
        "description": "Software development, cloud architecture, open source, DevOps, and engineering leadership"
    },
    {
        "name": "CRN",
        "domain": "crn.com",
        "tier": 2,
        "beat": "channel, MSPs, resellers, IT solutions",
        "audience": "VARs, MSPs, channel partners, IT solution providers",
        "rss": "https://www.crn.com/rss/news.xml",
        "description": "Channel technology — MSPs, resellers, vendor programs, IT solution providers"
    },
    # ── Tier 2 — Startup & Business ───────────────────────────────────
    {
        "name": "Forbes Tech",
        "domain": "forbes.com",
        "tier": 2,
        "beat": "startups, business technology, leadership, AI",
        "audience": "Business executives, entrepreneurs, investors",
        "rss": "https://www.forbes.com/innovation/feed2",
        "description": "Technology entrepreneurship, startup profiles, executive thought leadership, AI in business"
    },
    {
        "name": "Inc.",
        "domain": "inc.com",
        "tier": 2,
        "beat": "entrepreneurship, startups, leadership, growth",
        "audience": "Entrepreneurs, small and mid-size business owners, startup founders",
        "rss": "https://www.inc.com/rss/",
        "description": "Entrepreneurship, startup growth, leadership, company building, productivity"
    },
    {
        "name": "Business Insider Tech",
        "domain": "businessinsider.com",
        "tier": 2,
        "beat": "tech industry, startups, big tech, AI",
        "audience": "General business audience, mainstream tech readers",
        "rss": "https://feeds.businessinsider.com/tech",
        "description": "Tech industry news, startup stories, big tech strategy, AI business impact"
    },
]


class PublicationFinder:
    """Fetch recent articles from publications to reverse-engineer coverage patterns."""

    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PRPitchy/1.0; research bot)"
        }

    async def fetch_recent_articles(self, publication: dict, max_articles: int = 5) -> list[dict]:
        """Fetch recent articles from a publication's RSS feed."""
        articles = []
        rss_url = publication.get("rss", "").strip()
        if not rss_url:
            return articles  # No RSS configured — pub still included in summaries with empty articles
        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                async with session.get(rss_url) as response:
                    if response.status != 200:
                        return []
                    content = await response.text()

            # Parse RSS with BeautifulSoup
            soup = BeautifulSoup(content, "xml")
            items = soup.find_all("item")[:max_articles]
            if not items:
                # Try Atom format
                items = soup.find_all("entry")[:max_articles]

            for item in items:
                title = item.find("title")
                link = item.find("link")
                description = item.find("description") or item.find("summary")
                pub_date = item.find("pubDate") or item.find("published")

                title_text = title.get_text(strip=True) if title else ""
                # RSS link can be text or attribute
                link_text = ""
                if link:
                    link_text = link.get_text(strip=True) or link.get("href", "")

                desc_text = ""
                if description:
                    # Strip HTML from description
                    desc_soup = BeautifulSoup(description.get_text(strip=True), "html.parser")
                    desc_text = desc_soup.get_text(strip=True)[:300]

                # Extract author/byline — try multiple RSS formats
                author = None
                # Standard RSS <author>
                author_tag = item.find("author")
                if author_tag:
                    author = author_tag.get_text(strip=True)
                # Dublin Core <dc:creator> — most common in WordPress/Drupal feeds
                if not author:
                    dc_creator = item.find("dc:creator") or item.find("creator")
                    if dc_creator:
                        author = dc_creator.get_text(strip=True)
                # Media RSS <media:credit>
                if not author:
                    media_credit = item.find("media:credit") or item.find("credit")
                    if media_credit:
                        author = media_credit.get_text(strip=True)
                # Sanitize email+name format: "foo@bar.com (Jane Smith)" → "Jane Smith"
                if author and "(" in author and "@" in author:
                    match = re.search(r'\(([^)]+)\)', author)
                    author = match.group(1) if match else author.split("(")[-1].rstrip(")")
                # Strip bare email addresses (no name value)
                if author and "@" in author and "(" not in author:
                    author = None

                if title_text:
                    articles.append({
                        "title": title_text,
                        "url": link_text,
                        "summary": desc_text,
                        "date": pub_date.get_text(strip=True) if pub_date else "",
                        "author": author or "",
                        "publication": publication["name"],
                        "domain": publication["domain"],
                        "beat": publication["beat"],
                        "audience": publication["audience"],
                    })

        except Exception:
            pass

        return articles

    async def scan_publications(
        self,
        beat_filter: Optional[str] = None,
        tier_filter: Optional[int] = None,
        max_per_pub: int = 8,
        publications_override: list | None = None,
    ) -> list[dict]:
        """
        Scan multiple publications in parallel, return recent articles.
        Optionally filter by beat or tier.
        If publications_override is provided, use it instead of the default PUBLICATIONS list.
        """
        pubs_to_scan = publications_override if publications_override is not None else PUBLICATIONS
        if tier_filter:
            pubs_to_scan = [p for p in pubs_to_scan if p.get("tier", 2) <= tier_filter]
        if beat_filter:
            pubs_to_scan = [
                p for p in pubs_to_scan
                if beat_filter.lower() in p.get("beat", "").lower()
                or beat_filter.lower() in p.get("description", "").lower()
            ]

        tasks = [self.fetch_recent_articles(pub, max_articles=max_per_pub) for pub in pubs_to_scan]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        pub_summaries = []

        for pub, result in zip(pubs_to_scan, results):
            if isinstance(result, Exception) or not result:
                articles = []
            else:
                articles = result
                all_articles.extend(articles)

            pub_summaries.append({
                "name": pub.get("name", ""),
                "domain": pub.get("domain", ""),
                "tier": pub.get("tier", 2),
                "beat": pub.get("beat", ""),
                "audience": pub.get("audience", ""),
                "description": pub.get("description", ""),
                "recent_headlines": [a["title"] for a in articles],
                "known_authors": list(set(a["author"] for a in articles if a.get("author"))),
                "article_count": len(articles),
            })

        return pub_summaries, all_articles

    def get_publication_context(self) -> str:
        """Return a text summary of all publications for use in LLM prompts."""
        lines = []
        for pub in PUBLICATIONS:
            lines.append(
                f"- {pub['name']} (Tier {pub['tier']}, {pub['domain']}): "
                f"Beat: {pub['beat']}. Audience: {pub['audience']}. "
                f"{pub['description']}"
            )
        return "\n".join(lines)
