"""
Automatic branding detection from websites.
Extracts logo, colors, and fonts from blog URLs and domains.
"""

import os
import re
import tempfile
from typing import Optional, Dict, List, Tuple
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
from collections import Counter

import requests
from bs4 import BeautifulSoup
from PIL import Image
import colorsys

# ── Data Structure ────────────────────────────────────────────────────────

@dataclass
class DetectedBranding:
    """Detected branding from website."""
    logo_path: Optional[str] = None  # Temp path to downloaded logo
    primary_color: Optional[str] = None  # Hex color
    accent_color: Optional[str] = None  # Hex color
    secondary_color: Optional[str] = None  # Hex color
    fonts: List[str] = None  # Font families detected

    def __post_init__(self):
        if self.fonts is None:
            self.fonts = []

    def to_dict(self) -> dict:
        """Convert to dict for JSON response."""
        return {
            "logo_path": self.logo_path,
            "primary_color": self.primary_color,
            "accent_color": self.accent_color,
            "secondary_color": self.secondary_color,
            "fonts": self.fonts,
        }


# ── Logo Extraction ───────────────────────────────────────────────────────

async def extract_logo(blog_url: str, domain_url: Optional[str] = None) -> Optional[str]:
    """
    Extract logo from blog page or domain.
    Returns path to temp file with downloaded logo, or None if not found.
    """
    print(f"\n📸 Extracting logo from: {blog_url}")

    # Try blog URL first
    logo_path = await _extract_logo_from_url(blog_url)
    if logo_path:
        print(f"✓ Logo found on blog page")
        return logo_path

    # Try domain root
    if domain_url:
        logo_path = await _extract_logo_from_url(domain_url)
        if logo_path:
            print(f"✓ Logo found on domain")
            return logo_path

    print(f"⚠ No logo found")
    return None


async def _extract_logo_from_url(url: str) -> Optional[str]:
    """Try to extract logo from a specific URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        }
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Priority order for logo detection (header logos are most reliable)
        logo_candidates = []

        # 1. ONLY look in header/nav (content images are not logos)
        # Check all header/nav elements for images
        header_elements = soup.find_all(["header", "nav"])
        for header in header_elements:
            # Look for images in this header/nav
            for img in header.find_all("img", recursive=True):
                src = img.get("src", "")
                alt = img.get("alt", "").lower()

                if src:
                    # Skip tiny icons (less than 30px) and social media icons
                    width_attr = img.get("width", "")
                    height_attr = img.get("height", "")
                    try:
                        w = int(width_attr) if width_attr else 0
                        h = int(height_attr) if height_attr else 0
                        max_dim = max(w, h)
                        if max_dim > 0 and max_dim < 30:
                            continue  # Too small, skip
                    except:
                        pass

                    # Skip if it's clearly an icon
                    classes = img.get("class", [])
                    if isinstance(classes, str):
                        classes = classes.split()
                    if any(x in ' '.join(classes).lower() for x in ["icon", "social", "svg-icon", "flag"]):
                        continue

                    # Skip if filename suggests it's not a logo
                    src_lower = src.lower()
                    skip_keywords = ["icon", "arrow", "menu", "hamburger", "toggle", "badge", "social", "flag"]
                    if any(x in src_lower for x in skip_keywords):
                        continue

                    # Prioritize explicit logo mentions
                    if "logo" in alt or "logo" in src_lower or "brand" in src_lower:
                        logo_candidates.insert(0, ("header-logo", src))  # Put at front
                    else:
                        logo_candidates.append(("header-img", src))

        # 2. Images with explicit "logo" in filename
        for img in soup.find_all("img"):
            src = img.get("src", "")
            alt = img.get("alt", "").lower()
            if "logo" in src.lower() or "logo" in alt.lower():
                # Skip if it's in article content (likely blog image)
                parent = img.find_parent("article") or img.find_parent("main")
                if not parent:
                    logo_candidates.append(("filename-logo", src))

        # 3. Check for apple-touch-icon (small, likely logo)
        touch_icon = soup.find("link", rel="apple-touch-icon")
        if touch_icon and touch_icon.get("href"):
            logo_candidates.append(("touch-icon", touch_icon["href"]))

        # 4. Check for favicon
        favicon = soup.find("link", rel="icon")
        if favicon and favicon.get("href"):
            logo_candidates.append(("favicon", favicon["href"]))

        # 5. Check for og:image (often blog featured image, lower priority)
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            logo_candidates.append(("og:image", og_image["content"]))

        # Try each candidate
        for candidate_type, logo_url in logo_candidates:
            print(f"  Trying {candidate_type}: {logo_url}")
            downloaded_path = await _download_image(logo_url, url)
            if downloaded_path:
                print(f"  ✓ Downloaded {candidate_type}")
                return downloaded_path

        return None

    except Exception as e:
        print(f"  Error extracting logo: {e}")
        return None


async def _download_image(image_url: str, page_url: str) -> Optional[str]:
    """Download image and save to temp file."""
    try:
        # Make URL absolute if relative
        if not image_url.startswith(("http://", "https://")):
            image_url = urljoin(page_url, image_url)

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        }
        response = requests.get(image_url, timeout=10, headers=headers)
        response.raise_for_status()

        # Determine extension
        content_type = response.headers.get("content-type", "image/png")
        ext = ".png"
        if "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"
        elif "svg" in content_type:
            ext = ".svg"
        elif "webp" in content_type:
            ext = ".webp"

        # Validate file size (logos are typically 5KB-500KB)
        # Skip too small (broken/placeholder) or too large (full images)
        file_size = len(response.content)
        if file_size < 2048:  # Less than 2KB - likely broken
            print(f"    Skipped: file too small ({file_size} bytes)")
            return None
        if file_size > 5 * 1024 * 1024:  # More than 5MB - likely content image
            print(f"    Skipped: file too large ({file_size / 1024 / 1024:.1f}MB)")
            return None

        # Save to temp file
        tmp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp_file.write(response.content)
        tmp_file.flush()
        tmp_file.close()

        return tmp_file.name

    except Exception as e:
        print(f"    Failed to download: {e}")
        return None


# ── Color Analysis ────────────────────────────────────────────────────────

async def extract_colors(blog_url: str) -> Dict[str, str]:
    """
    Extract dominant colors from website.
    Returns dict with primary, accent, secondary colors (hex).
    """
    print(f"\n🎨 Analyzing colors from: {blog_url}")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        }
        response = requests.get(blog_url, timeout=10, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        colors = []

        # Extract colors from CSS
        style_tags = soup.find_all("style")
        for style in style_tags:
            css_text = style.string or ""
            # Find hex colors in CSS
            hex_colors = re.findall(r"#[0-9a-fA-F]{6}", css_text)
            colors.extend(hex_colors)

        # Extract colors from inline styles
        for element in soup.find_all(style=True):
            style_attr = element.get("style", "")
            hex_colors = re.findall(r"#[0-9a-fA-F]{6}", style_attr)
            colors.extend(hex_colors)

        # Extract from link stylesheets
        links = soup.find_all("link", rel="stylesheet")
        for link in links:
            href = link.get("href")
            if href:
                try:
                    css_url = urljoin(blog_url, href)
                    css_response = requests.get(css_url, timeout=5, headers=headers)
                    hex_colors = re.findall(r"#[0-9a-fA-F]{6}", css_response.text)
                    colors.extend(hex_colors)
                except:
                    pass

        # Find most common colors
        if colors:
            color_counts = Counter(colors)
            most_common = color_counts.most_common(5)

            # Filter to avoid pure black/white
            filtered_colors = [
                color for color, count in most_common
                if color.lower() not in ["#000000", "#ffffff", "#f9f9f9", "#fafafa"]
            ]

            if len(filtered_colors) >= 3:
                result = {
                    "primary_color": filtered_colors[0],
                    "secondary_color": filtered_colors[1],
                    "accent_color": filtered_colors[2],
                }
                print(f"✓ Detected colors: {result}")
                return result
            elif len(filtered_colors) >= 1:
                result = {
                    "primary_color": filtered_colors[0],
                    "secondary_color": filtered_colors[0] if len(filtered_colors) < 2 else filtered_colors[1],
                    "accent_color": "#FF6B6B",  # Default accent
                }
                print(f"✓ Detected colors (with defaults): {result}")
                return result

        print(f"⚠ Could not detect colors, using defaults")
        return {
            "primary_color": "#131553",
            "secondary_color": "#08c4ff",
            "accent_color": "#c6159b",
        }

    except Exception as e:
        print(f"Error extracting colors: {e}")
        return {
            "primary_color": "#131553",
            "secondary_color": "#08c4ff",
            "accent_color": "#c6159b",
        }


# ── Font Detection ────────────────────────────────────────────────────────

async def extract_fonts(blog_url: str) -> List[str]:
    """
    Extract font families used on website.
    Returns list of font names (e.g., ["Poppins", "Open Sans"]).
    """
    print(f"\n🔤 Detecting fonts from: {blog_url}")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        }
        response = requests.get(blog_url, timeout=10, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        fonts = set()

        # Extract from CSS
        style_tags = soup.find_all("style")
        for style in style_tags:
            css_text = style.string or ""
            # Find font-family declarations
            font_matches = re.findall(r"font-family\s*:\s*['\"]?([^'\";\n]+)['\"]?[;,\n]", css_text, re.IGNORECASE)
            for match in font_matches:
                # Clean up and extract first font
                font_name = match.strip().split(",")[0].strip("'\" ")
                if font_name and len(font_name) > 2:
                    fonts.add(font_name)

        # Extract from inline styles
        for element in soup.find_all(style=True):
            style_attr = element.get("style", "")
            font_matches = re.findall(r"font-family\s*:\s*([^;]+)", style_attr, re.IGNORECASE)
            for match in font_matches:
                font_name = match.strip().strip("'\" ")
                if font_name and len(font_name) > 2:
                    fonts.add(font_name)

        # Extract from link stylesheets
        links = soup.find_all("link", rel="stylesheet")
        for link in links:
            href = link.get("href")
            if href:
                try:
                    css_url = urljoin(blog_url, href)
                    css_response = requests.get(css_url, timeout=5, headers=headers)
                    font_matches = re.findall(r"font-family\s*:\s*['\"]?([^'\";\n]+)['\"]?[;,\n]", css_response.text, re.IGNORECASE)
                    for match in font_matches:
                        font_name = match.strip().split(",")[0].strip("'\" ")
                        if font_name and len(font_name) > 2:
                            fonts.add(font_name)
                except:
                    pass

        # Filter to common/relevant fonts
        fonts_list = list(fonts)[:5]  # Top 5 fonts

        if fonts_list:
            print(f"✓ Detected fonts: {fonts_list}")
            return fonts_list
        else:
            defaults = ["Poppins", "Open Sans", "Helvetica"]
            print(f"⚠ Could not detect fonts, using defaults: {defaults}")
            return defaults

    except Exception as e:
        print(f"Error extracting fonts: {e}")
        return ["Poppins", "Open Sans", "Helvetica"]


# ── Main Detection Function ──────────────────────────────────────────────

async def detect_branding(blog_url: str) -> DetectedBranding:
    """
    Detect all branding elements from blog URL.
    Returns DetectedBranding object with logo, colors, fonts.
    """
    print(f"\n{'='*70}")
    print(f"AUTO-DETECTING BRANDING FROM: {blog_url}")
    print(f"{'='*70}")

    # Extract domain URL
    parsed = urlparse(blog_url)
    domain_url = f"{parsed.scheme}://{parsed.netloc}"

    # Extract logo
    logo_path = await extract_logo(blog_url, domain_url)

    # Extract colors
    colors = await extract_colors(blog_url)

    # Extract fonts
    fonts = await extract_fonts(blog_url)

    detected = DetectedBranding(
        logo_path=logo_path,
        primary_color=colors.get("primary_color"),
        accent_color=colors.get("accent_color"),
        secondary_color=colors.get("secondary_color"),
        fonts=fonts,
    )

    print(f"\n{'='*70}")
    print(f"DETECTION COMPLETE:")
    print(f"  Logo: {'✓' if logo_path else '✗'}")
    print(f"  Primary Color: {detected.primary_color}")
    print(f"  Accent Color: {detected.accent_color}")
    print(f"  Secondary Color: {detected.secondary_color}")
    print(f"  Fonts: {', '.join(fonts[:3])}")
    print(f"{'='*70}\n")

    return detected
