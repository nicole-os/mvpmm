"""
PDF Generator — Configurable Branding
2-page and 3-page executive brief templates with full custom branding support.

Page 1 — "At a Glance"
  Header (title wraps, logo top-right) - color configurable
  QUICK OVERVIEW label + exec summary (no truncation)
  KEY TAKEAWAYS label + 3 horizontal cards (numbered in secondary color)

Page 2 — "Deep Dive"
  Narrow header band (primary color)
  Content sections with headers
  Optional FAQ section
  Separator line + CTA block (primary color with accent stripe)
  Full-bleed footer band (primary color)

Brand Configuration:
  Support for 8 colors (primary, secondary, accent, accent2, accent3, text_dark, text_light, border)
  Support for 3 fonts (title, subtitle, body)
  Optional company logo, name, and website
"""

import io
import os
import re
import json
import math
import random
import textwrap
from typing import Optional
from dataclasses import dataclass, asdict, fields as dataclass_fields

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Banned Phrases Filter ──────────────────────────────────────────────────────

BANNED_PHRASES = [
    "rapidly evolving field",
    "rapidly evolving",
    "ever-evolving",
    "rapidly changing",
    "landscape",
    "vague",
]

def _remove_banned_phrases(text: str) -> str:
    """Remove banned phrases from text (case-insensitive)."""
    if not text:
        return text

    for phrase in BANNED_PHRASES:
        # Case-insensitive replacement
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        text = pattern.sub("", text)

    # Clean up extra whitespace created by removal
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ── Brand Configuration Dataclass ──────────────────────────────────────────────

@dataclass
class BrandConfig:
    """Configuration for PDF branding (colors, fonts, company info)."""
    # Colors (hex strings)
    primary: str          # Headers, main backgrounds
    secondary: str        # Card numbers, accents
    accent: str           # CTA stripe, highlights
    accent2: str = "#8a9f4a"  # Secondary accent, CTA text
    accent3: str = "#5b8fa8"  # Third accent (teal/blue, for variety)
    text_dark: str = "#333333"        # Body text color
    text_light: str = "#F9F8F6"       # Light backgrounds
    border: str = "#A49A87"           # Subtle borders

    # Company Info
    company_name: str = ""
    company_website: str = ""
    company_logo_path: Optional[str] = None
    logo_file: Optional[str] = None  # New: logo path from branding JSON

    # Fonts (reportlab font names)
    font_title: str = "Poppins-Bold"
    font_subtitle: str = "OpenSans"
    font_body: str = "OpenSans"

    # Design preferences
    corner_style: str = "rounded"  # "rounded" or "sharp" for color bars
    logo_bg_color: Optional[str] = None  # Optional explicit logo background
    header_style: str = "geometric"  # "solid" | "geometric" | "surprise"

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if v is not None}


def get_default_brand_config() -> BrandConfig:
    """Return neutral default branding configuration."""
    return BrandConfig(
        primary="#4A3453",           # Deep purple
        secondary="#7B8BA3",         # Slate blue
        accent="#B38B91",            # Mauve
        accent2="#8a9f4a",           # Olive
        accent3="#5b8fa8",           # Steel blue
        text_dark="#333333",         # Dark grey
        text_light="#F9F8F6",        # Off-white
        border="#A49A87",            # Warm grey
        company_name="",
        company_website="",
        font_title="Poppins-Bold",
        font_subtitle="OpenSans",
        font_body="OpenSans"
    )


def validate_brand_config(config: dict) -> tuple[bool, str]:
    """
    Validate brand config dict.
    Returns (is_valid, error_message).
    Handles both nested and flat formats.
    """
    if not isinstance(config, dict):
        return False, "Brand config must be a dictionary"

    # Flatten if needed for validation
    flattened = _flatten_brand_config(config)

    required_colors = ["primary", "secondary", "accent", "text_dark", "text_light", "border"]
    hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")

    for color_key in required_colors:
        if color_key in flattened:
            color_val = flattened[color_key]
            if not hex_pattern.match(str(color_val)):
                return False, f"Color '{color_key}' must be hex format #RRGGBB, got '{color_val}'"

    # Validate fonts if provided
    valid_fonts = {
        "Poppins-Bold", "Poppins", "OpenSans-Bold", "OpenSans",
        "Helvetica-Bold", "Helvetica", "Courier-Bold", "Courier",
        "Times-Roman-Bold", "Times-Roman"
    }
    for font_key in ["font_title", "font_subtitle", "font_body"]:
        if font_key in flattened and flattened[font_key] not in valid_fonts:
            return False, f"Font '{font_key}' not supported. Use: {', '.join(valid_fonts)}"

    return True, ""


def create_brand_config(config_dict: Optional[dict] = None) -> BrandConfig:
    """
    Create BrandConfig from dict, merging with defaults.
    Validates hex colors and fonts.
    Supports both nested format {"colors": {...}, "fonts": {...}}
    and flat format {"primary": "...", "font_title": "..."}
    """
    defaults = get_default_brand_config()

    if config_dict is None:
        return defaults

    # Flatten nested format if present
    flattened = _flatten_brand_config(config_dict)

    # Validate
    is_valid, error_msg = validate_brand_config(flattened)
    if not is_valid:
        raise ValueError(f"Invalid brand config: {error_msg}")

    # Merge with defaults
    merged = asdict(defaults)
    merged.update({k: v for k, v in flattened.items() if v is not None})

    # Filter to only BrandConfig fields (ignore extra fields like elevator_pitch_body, etc.)
    valid_fields = {f.name for f in dataclass_fields(BrandConfig)}
    filtered = {k: v for k, v in merged.items() if k in valid_fields}

    return BrandConfig(**filtered)


def _flatten_brand_config(config_dict: dict) -> dict:
    """
    Flatten nested brand config structure.
    Converts {"colors": {...}, "fonts": {...}} to flat keys.
    """
    flattened = {}

    # Copy non-nested values
    for k, v in config_dict.items():
        if k not in ("colors", "fonts"):
            flattened[k] = v

    # Flatten colors
    if "colors" in config_dict and isinstance(config_dict["colors"], dict):
        for color_key, color_val in config_dict["colors"].items():
            flattened[color_key] = color_val

    # Flatten fonts
    if "fonts" in config_dict and isinstance(config_dict["fonts"], dict):
        for font_key, font_val in config_dict["fonts"].items():
            flattened[font_key] = font_val

    return flattened


# ── Color conversion helper ────────────────────────────────────────────────────

def _hex_to_color(hex_str: str) -> HexColor:
    """Convert hex string to HexColor."""
    try:
        return HexColor(hex_str)
    except Exception:
        return HexColor("#000000")  # fallback to black

# ── Paths ──────────────────────────────────────────────────────────────────────
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FONTS_DIR  = os.path.join(ASSETS_DIR, "fonts")
SHARED_FONTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "shared", "assets", "fonts"
)

def _find_font_file(filename: str) -> Optional[str]:
    for d in [FONTS_DIR, SHARED_FONTS_DIR]:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    return None

_fonts_registered = False

def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    for name, filename in [
        ("Poppins-Bold",  "Poppins-Bold.ttf"),
        ("Poppins",       "Poppins-Regular.ttf"),
        ("OpenSans",      "OpenSans-Regular.ttf"),
        ("OpenSans-Bold", "OpenSans-Bold.ttf"),
    ]:
        path = _find_font_file(filename)
        if path:
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                pass
    _fonts_registered = True

def _font(name: str) -> str:
    _register_fonts()
    fallbacks = {
        "Poppins-Bold":  "Helvetica-Bold",
        "Poppins":       "Helvetica",
        "OpenSans":      "Helvetica",
        "OpenSans-Bold": "Helvetica-Bold",
    }
    try:
        pdfmetrics.getFont(name)
        return name
    except Exception:
        return fallbacks.get(name, "Helvetica")

# ── Page constants ─────────────────────────────────────────────────────────────
W, H          = letter           # 612 x 792 pt
MARGIN        = 0.7 * inch
CONTENT_W     = W - 2 * MARGIN
HEADER_H      = 2.0 * inch
FOOTER_H      = 0.5 * inch       # full-bleed navy footer band height
BODY_FONT_SZ  = 11.0  # net +1pt from original 10.0
BODY_LEADING  = 16.5  # 11 * 1.5
CTA_BLOCK_H   = 2.4 * inch       # tall enough for 8 lines of boilerplate

# ── Text utilities ─────────────────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    """Normalize text by removing extra whitespace and hardcoded line breaks, preserving hyphens."""
    if not text:
        return text
    # First, normalize all hyphen variants to regular hyphen (-)
    # This handles en-dash, em-dash, non-breaking hyphen, etc.
    text = text.replace('–', '-')  # en-dash
    text = text.replace('—', '-')  # em-dash
    text = text.replace('‐', '-')  # hyphen
    text = text.replace('−', '-')  # minus sign
    text = text.replace('\u00ad', '-')  # soft hyphen
    # Unicode subscript digits → plain digits (built-in fonts like Times-Roman
    # only cover Latin-1, so U+2080-U+2089 render as ■ without this mapping)
    _sub = str.maketrans('₀₁₂₃₄₅₆₇₈₉', '0123456789')
    text = text.translate(_sub)
    # Unicode superscript digits not in Latin-1 → plain digits
    # (U+00B2 ² and U+00B3 ³ ARE in Latin-1 and render fine; remap the rest)
    _sup_extra = str.maketrans('⁰¹⁴⁵⁶⁷⁸⁹', '01456789')
    text = text.translate(_sup_extra)
    # Replace multiple spaces and newlines with single space (but preserve hyphens)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def _wrap(text: str, max_chars: int) -> list:
    """Legacy character-count based wrapper. Use _wrap_by_width() for font-aware wrapping."""
    if not text:
        return []
    # Normalize text to remove hardcoded line breaks
    text = _normalize_text(text)
    lines = []
    if text:
        lines.extend(textwrap.wrap(text, max_chars, break_long_words=False, break_on_hyphens=False))
    return lines

def _wrap_by_width(text: str, max_width: float, font_name: str, font_size: float) -> list:
    """Wrap text by actual measured line width using font metrics. Font-aware and accurate."""
    if not text or max_width <= 0:
        return []
    text = _normalize_text(text)
    lines = []
    words = text.split()
    current_line = []

    for word in words:
        test_line = ' '.join(current_line + [word])
        line_width = pdfmetrics.stringWidth(test_line, font_name, font_size)
        if line_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))
    return lines

def _line_count(text: str, width: float, size: float) -> int:
    if not text:
        return 0
    max_chars = max(10, int(width / (size * 0.50)))  # Increased from 0.52 for fuller text
    return len(_wrap(text, max_chars))

def _draw_text_block(c, x, y, width, text, font, size, leading, color,
                     max_lines=None):
    lines = _wrap_by_width(text, width, font, size)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
    c.setFont(font, size)
    c.setFillColor(color)
    t = c.beginText(x, y)
    t.setLeading(leading)
    for ln in lines:
        t.textLine(ln)
    c.drawText(t)
    return y - leading * len(lines)

# ── Section label (small all-caps, uses border color) ───────────────────────

def _draw_section_label(c, x, y, text, brand: BrandConfig):
    """All-caps eyebrow label using secondary color (guarded for legibility)."""
    c.setFont(_font("OpenSans-Bold"), 11)
    c.setFillColor(_hex_to_color(_safe_text_color(brand.secondary)))
    c.drawString(x, y, text.upper())
    return y - 15

# ── Section header (plain bold, uses primary color) ─────────────────────────

def _section_header(c, x, y, text, brand: BrandConfig):
    """Plain section header using primary color (guarded for legibility)."""
    c.setFont(_font("Poppins-Bold"), 12.5)
    c.setFillColor(_hex_to_color(_safe_text_color(brand.primary)))
    c.drawString(x, y, text)
    return y - 20

# ── Takeaway cards ─────────────────────────────────────────────────────────────

def _draw_takeaway_cards(c, takeaways: list, y: float, brand: BrandConfig, available_h: float = 0) -> float:
    """
    Draw 3 horizontal takeaway cards with 01/02/03 number labels.
    Number color uses secondary color, background uses text_light color.
    available_h: cards stretch to fill this height when provided.
    """
    gap       = 0.12 * inch
    card_w    = (CONTENT_W - 2 * gap) / 3
    card_pad  = 0.18 * inch
    inner_w   = card_w - 2 * card_pad
    text_sz   = 10.5
    text_lead = 15.5
    num_sz    = 22
    num_h     = num_sz * 1.3
    rule_gap  = 14
    top_pad   = 0.14 * inch
    bot_pad   = 0.10 * inch

    max_lines = max(
        (len(_wrap_by_width(t, inner_w, _font(brand.font_body), text_sz)) if t.strip() else 1)
        for t in takeaways
    )
    natural_h = top_pad + num_h + rule_gap + text_lead * max_lines + bot_pad
    natural_h = max(natural_h, 1.5 * inch)

    if available_h and available_h > 1.5 * inch:
        card_h = min(available_h, natural_h + 0.5 * inch)
    else:
        card_h = natural_h

    card_y = y - card_h

    labels = ["01", "02", "03"]
    for i, (label, takeaway) in enumerate(zip(labels, takeaways)):
        cx = MARGIN + i * (card_w + gap)

        # Card background — fixed light gray so it's always visible (text_light is often #ffffff)
        c.setFillColor(HexColor("#EEF2F8"))
        c.rect(cx, card_y, card_w, card_h, stroke=0, fill=1)

        # Number label in accent color (more prominent)
        c.setFont(_font("Poppins-Bold"), num_sz)
        c.setFillColor(_hex_to_color(brand.accent))
        num_y = card_y + card_h - top_pad - num_sz * 0.75
        c.drawString(cx + card_pad, num_y, label)

        # Thin rule below number in accent color
        rule_y = num_y - num_sz * 0.35
        c.setStrokeColor(_hex_to_color(brand.accent))
        c.setLineWidth(2.0)
        c.line(cx + card_pad, rule_y, cx + card_w - card_pad, rule_y)

        # Takeaway text — always dark since card background is always light (#EEF2F8)
        text_y = rule_y - rule_gap
        _draw_text_block(c, cx + card_pad, text_y, inner_w,
                         takeaway or "",
                         _font(brand.font_body), text_sz, text_lead, _hex_to_color(brand.text_dark))

    return card_y - 0.1 * inch

# ── FAQ section ────────────────────────────────────────────────────────────────

def _estimate_faq_section_height(faqs: list, limit: int = 5) -> float:
    """Estimate total rendered height of _draw_faq_section output (in points)."""
    q_sz = 11.0; q_lead = 15.5
    a_sz = 10.5; a_lead = 15.0
    indent = 0.15 * inch; pair_gap = 10
    label_h = 15  # _draw_section_label returns y - 15
    h = label_h + 6  # label + gap below label
    for faq in faqs[:limit]:
        q_lines = len(_wrap_by_width(faq.get("question", ""), CONTENT_W - 14, _font("Poppins-Bold"), q_sz))
        a_lines = len(_wrap_by_width(faq.get("answer", ""),   CONTENT_W - indent, _font("OpenSans"), a_sz))
        h += q_lines * q_lead + a_lines * a_lead + pair_gap
    h += 0.1 * inch  # final return offset
    return h


def _draw_faq_section(c, faqs: list, y: float, bottom_limit: float, brand: BrandConfig) -> float:
    """
    Draw FAQ section: small label + Q/A pairs.
    Q prefix uses secondary color, answers use border color.
    Only renders pairs that fit above bottom_limit.
    Returns new y after the section.
    """
    if not faqs:
        return y

    q_sz    = 11.0
    q_lead  = 15.5
    a_sz    = 10.5
    a_lead  = 15.0
    indent  = 0.15 * inch
    pair_gap = 10

    if y - bottom_limit < 80:
        return y

    y = _draw_section_label(c, MARGIN, y, "Frequently Asked Questions", brand)
    y -= 0.22 * inch  # extra breathing room between label and first Q

    for faq in faqs[:5]:
        question = faq.get("question", "").strip()
        answer   = faq.get("answer", "").strip()
        if not question:
            continue

        if y < bottom_limit + 0.35 * inch:
            break

        # Question — bold primary with accent Q prefix
        q_lines = _wrap_by_width(question, CONTENT_W - 14, _font("Poppins-Bold"), q_sz)

        c.setFont(_font("Poppins-Bold"), q_sz)
        c.setFillColor(_hex_to_color(brand.accent))  # accent color for Q marker
        c.drawString(MARGIN, y, "Q")
        c.setFillColor(_hex_to_color(_safe_text_color(brand.primary)))  # safe readable color for question text
        ty = y
        for ln in q_lines:
            c.drawString(MARGIN + 14, ty, ln)
            ty -= q_lead
        y = ty - 2

        # Answer — border color, indented
        if answer:
            y = _draw_text_block(c, MARGIN + indent, y, CONTENT_W - indent,
                                 answer, _font(brand.font_body), a_sz, a_lead, _hex_to_color(brand.text_dark))

        y -= pair_gap

    return y - 0.1 * inch

# ── Logo ───────────────────────────────────────────────────────────────────────

def _draw_logo(c, logo_path, brand: BrandConfig):
    """Draw transparent logo/company name top-right, linked to company website."""
    if not logo_path or not os.path.exists(logo_path):
        c.setFont(_font("Poppins-Bold"), 14)
        c.setFillColor(_hex_to_color(brand.text_light))
        link_x = W - MARGIN - 52
        c.drawString(link_x, H - 0.5 * inch, brand.company_name[:20].upper())
        c.linkURL(brand.company_website,
                  (link_x, H - 0.6 * inch, W - MARGIN, H - 0.35 * inch), relative=0)
        return

    # Dynamic sizing: fit within header bounds maintaining aspect ratio.
    # max_logo_w: 1.2" keeps wide-format logos readable while leaving room for title.
    max_logo_w = 1.2 * inch        # 20% narrower than previous 1.5"; ratio + vertical centre preserved
    max_logo_h = HEADER_H * 0.65  # 65% of 2" header height keeps logo inside the band

    try:
        from reportlab.lib.utils import ImageReader as _IR
        img = _IR(logo_path)
        iw, ih = img.getSize()
        scale = min(max_logo_w / iw, max_logo_h / ih) if iw > 0 and ih > 0 else 1.0
        logo_w = iw * scale
        logo_h = ih * scale
    except:
        logo_h = max_logo_h
        logo_w = min(logo_h * (908 / 192), max_logo_w)

    # Center the logo vertically within the header band
    header_y = H - HEADER_H
    logo_x   = W - MARGIN - logo_w
    logo_y   = header_y + (HEADER_H - logo_h) / 2


    try:
        c.drawImage(logo_path, logo_x, logo_y,
                    width=logo_w, height=logo_h, mask="auto")
        # Ensure URL has protocol for proper linking
        url = brand.company_website
        if url and not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        # Expand clickable area slightly for easier clicking
        link_padding = 0.1 * inch
        if url:
            c.linkURL(url,
                      (logo_x - link_padding, logo_y - link_padding,
                       logo_x + logo_w + link_padding, logo_y + logo_h + link_padding),
                      relative=0)
    except Exception:
        c.setFont(_font("Poppins-Bold"), 14)
        c.setFillColor(_hex_to_color(brand.text_light))
        link_x = W - MARGIN - 52
        c.drawString(link_x, H - 0.5 * inch, brand.company_name[:20].upper())
        c.linkURL(brand.company_website,
                  (link_x, H - 0.6 * inch, W - MARGIN, H - 0.35 * inch), relative=0)

# ── Header texture ─────────────────────────────────────────────────────────────

# Surprise patterns are chosen deterministically from the brand primary color hash
_SURPRISE_PATTERNS = ["halftone", "circuit", "arcs", "scanlines", "crosshatch"]

def _draw_header_texture(c, header_y: float, brand: BrandConfig, seed_str: str = ""):
    """
    Draw decorative texture overlay in the 2-page header band.

    brand.header_style controls which style is used:
      "solid"     — no texture; plain color only
      "geometric" — subtle overlapping circles + diagonal lines (default)
      "surprise"  — one of five digital/faded overlay patterns, chosen by
                    hashing (seed_str + brand.primary) for determinism per title
    """
    style = (brand.header_style or "geometric").lower()
    if style == "solid":
        return

    # Pick pattern
    if style == "surprise":
        idx = abs(hash(seed_str + brand.primary)) % len(_SURPRISE_PATTERNS)
        pattern = _SURPRISE_PATTERNS[idx]
    else:
        pattern = "geometric"

    c.saveState()
    # Clip all drawing to the header band
    p = c.beginPath()
    p.rect(0, header_y, W, HEADER_H)
    c.clipPath(p, stroke=0)

    sec = _hex_to_color(brand.secondary)
    acc = _hex_to_color(brand.accent)
    pri = _hex_to_color(brand.primary)
    lit = _hex_to_color(brand.text_light)

    # On a light header background the primary/secondary colours are dark enough to show.
    # On a dark header background text_light gives subtle bright highlights.
    bg_is_light = _brightness_of_color(
        brand.logo_bg_color if brand.logo_bg_color else brand.primary
    ) > 190
    # Choose overlay colour set: dark bg → use lit+sec (bright overlay); light bg → use pri+acc (dark overlay)
    ov1 = pri if bg_is_light else lit
    ov2 = acc if bg_is_light else sec
    # Base alpha multiplier: higher on light bg so patterns are clearly visible
    alpha_mul = 2.2 if bg_is_light else 1.0

    # ── Geometric (current default) ───────────────────────────────────────────
    if pattern == "geometric":
        a1 = min(0.18, 0.07 * alpha_mul)
        a2 = min(0.14, 0.05 * alpha_mul)
        a3 = min(0.30, 0.14 * alpha_mul)
        c.setFillColor(Color(ov2.red, ov2.green, ov2.blue, alpha=a1))
        c.circle(W - 0.5 * inch, header_y + HEADER_H * 0.5, 1.05 * inch, stroke=0, fill=1)
        c.setFillColor(Color(ov1.red, ov1.green, ov1.blue, alpha=a2))
        c.circle(W - 1.35 * inch, header_y + HEADER_H * 0.75, 0.65 * inch, stroke=0, fill=1)
        c.setStrokeColor(Color(ov2.red, ov2.green, ov2.blue, alpha=a3))
        c.setLineWidth(1.2)
        for offset in [0, 10, 20]:
            c.line(W - 2.0 * inch + offset, header_y + HEADER_H,
                   W - 0.1 * inch + offset, header_y)

    # ── Halftone dots — grid of circles fading in from the right ─────────────
    elif pattern == "halftone":
        dot_r        = 2.8
        spacing      = 13
        max_a        = min(0.45, 0.24 * alpha_mul)
        x_fade_start = W * 0.30
        x_full_alpha = W * 0.80
        x = x_fade_start
        while x <= W + spacing:
            y = header_y + spacing * 0.5
            col_alpha = min(max_a, (x - x_fade_start) / max(1, x_full_alpha - x_fade_start) * max_a)
            if col_alpha > 0.01:
                c.setFillColor(Color(ov1.red, ov1.green, ov1.blue, alpha=col_alpha))
                while y <= header_y + HEADER_H:
                    c.circle(x, y, dot_r, stroke=0, fill=1)
                    y += spacing
            x += spacing

    # ── Circuit traces — horizontal rails with node squares ──────────────────
    elif pattern == "circuit":
        rng       = random.Random(abs(hash(brand.primary)) & 0xFFFFFF)
        rail_count = 6
        rail_sp   = HEADER_H / (rail_count + 1)
        x_start   = W * 0.35
        node_sz   = 4.5
        base_a    = min(0.42, 0.22 * alpha_mul)
        vert_a    = min(0.36, 0.18 * alpha_mul)
        c.setLineWidth(0.75)
        for i in range(1, rail_count + 1):
            ry = header_y + i * rail_sp
            c.setStrokeColor(Color(ov2.red, ov2.green, ov2.blue, alpha=base_a))
            c.line(x_start, ry, W - MARGIN * 0.4, ry)
            x = x_start + rng.uniform(15, 45)
            while x < W - MARGIN * 0.4:
                c.setFillColor(Color(ov2.red, ov2.green, ov2.blue, alpha=base_a))
                c.rect(x - node_sz / 2, ry - node_sz / 2, node_sz, node_sz, stroke=0, fill=1)
                if i < rail_count and rng.random() < 0.35:
                    c.setStrokeColor(Color(ov1.red, ov1.green, ov1.blue, alpha=vert_a))
                    c.line(x, ry, x, ry + rail_sp)
                x += rng.uniform(28, 85)

    # ── Concentric arcs — broadcast waves from right edge ────────────────────
    elif pattern == "arcs":
        cx = W + 18
        cy = header_y + HEADER_H * 0.5
        c.setLineWidth(0.9)
        for i, r in enumerate(range(28, 260, 20)):
            alpha = min(0.50, (0.06 + i * 0.016) * alpha_mul)
            c.setStrokeColor(Color(ov2.red, ov2.green, ov2.blue, alpha=alpha))
            c.arc(cx - r, cy - r, cx + r, cy + r, 90, 180)

    # ── Diagonal scan lines — dense parallel lines at 52° ────────────────────
    elif pattern == "scanlines":
        step    = 8
        x_start = W * 0.28
        max_a   = min(0.40, 0.20 * alpha_mul)
        c.setLineWidth(0.6)
        x = x_start
        while x <= W + HEADER_H:
            alpha = min(max_a, (x - x_start) / max(1, W - x_start) * max_a)
            c.setStrokeColor(Color(ov1.red, ov1.green, ov1.blue, alpha=alpha))
            c.line(x, header_y + HEADER_H, x - HEADER_H * 1.28, header_y)
            x += step

    # ── Crosshatch grid — fine h+v lines fading left ─────────────────────────
    elif pattern == "crosshatch":
        step    = 11
        x_start = W * 0.35
        h_a     = min(0.30, 0.14 * alpha_mul)
        c.setLineWidth(0.45)
        y = header_y + step
        while y < header_y + HEADER_H:
            c.setStrokeColor(Color(ov2.red, ov2.green, ov2.blue, alpha=h_a))
            c.line(x_start, y, W, y)
            y += step
        x = x_start
        while x <= W:
            dist  = (x - x_start) / max(1, W - x_start)
            alpha = min(0.32, dist * 0.16 * alpha_mul)
            c.setStrokeColor(Color(ov1.red, ov1.green, ov1.blue, alpha=alpha))
            c.line(x, header_y, x, header_y + HEADER_H)
            x += step

    c.restoreState()

# ── Smart Logo Background Detection ────────────────────────────────────────────

def _validate_logo_exists(logo_path: str, fallback_path: str) -> str:
    """
    Validate that logo exists. If not, use fallback.
    Returns valid path to use.
    """
    if logo_path and os.path.exists(logo_path):
        return logo_path

    if fallback_path and os.path.exists(fallback_path):
        return fallback_path

    return fallback_path


def _detect_logo_brightness(logo_path: str) -> str:
    """
    Detect whether a logo has light or dark text.
    Returns 'dark'  if logo has light/white text → needs dark (primary) background.
    Returns 'light' if logo has dark text         → needs light background.
    SVG: return 'dark' (assume white text on dark background).
    """
    try:
        if logo_path.lower().endswith('.svg'):
            return 'dark'

        from PIL import Image
        import numpy as np

        img = Image.open(logo_path).convert('RGBA')
        pixels = np.array(img)          # shape: H x W x 4

        alpha = pixels[:, :, 3]
        non_transparent = alpha > 10    # ignore nearly-invisible pixels
        rgb = pixels[:, :, :3][non_transparent].astype(float)

        if len(rgb) == 0:
            return 'dark'               # empty/fully transparent → safe default

        # Luminance of each visible pixel
        lum = rgb[:, 0] * 0.299 + rgb[:, 1] * 0.587 + rgb[:, 2] * 0.114

        # Bin into 16 buckets (0–15); bins 13–15 cover luminance 208–255 (near-white)
        bins = (lum // 16).astype(int).clip(0, 15)
        bin_counts = np.bincount(bins, minlength=16)
        dominant_bin = int(bin_counts.argmax())

        # Count very bright pixels that are NOT the dominant (background) bin
        bright_bins = {13, 14, 15} - {dominant_bin}
        bright_count = sum(int(bin_counts[b]) for b in bright_bins)
        bright_ratio = bright_count / len(rgb)

        # Count pixels that are very dark (bins 0-5 = luminance 0-95)
        # A logo with a dark colored background (e.g. dark purple with white text)
        # will have a high dark_ratio even if bright_ratio is below the threshold.
        dark_count = sum(int(bin_counts[b]) for b in range(0, 6))
        dark_ratio = dark_count / len(rgb)

        # Needs dark bg if:
        #   A) >4% non-background bright pixels  → logo has white text on transparent/any bg
        #   B) >50% very-dark pixels              → logo has a dark colored background (may have white text)
        result = 'dark' if (bright_ratio > 0.04 or dark_ratio > 0.50) else 'light'
        return result

    except ImportError:
        return _detect_logo_brightness_simple(logo_path)
    except Exception as e:
        return 'dark'   # safe default: dark bg


def _detect_logo_brightness_simple(logo_path: str) -> str:
    """Fallback: simple average brightness (PIL only, no numpy)."""
    try:
        from PIL import Image

        img = Image.open(logo_path)
        img_gray = img.convert('L')
        pixels = list(img_gray.getdata())
        avg_brightness = sum(pixels) / len(pixels) if pixels else 128

        result = 'dark' if avg_brightness > 180 else 'light'
        return result
    except:
        return 'dark'


def _safe_text_color(hex_color: str, fallback: str = "#1a1a1a") -> str:
    """
    Return hex_color if it is dark enough to be legible on a white/light body background.
    If the color is too light (brightness > 190), return fallback instead.
    This guards against using very pale primary/secondary colors as body text.
    """
    if _brightness_of_color(hex_color) > 190:
        return fallback
    return hex_color


def _get_logo_background_color(logo_path: str, brand: BrandConfig) -> str:
    """
    Return the background color to use behind the logo in header/footer/boilerplate.
    If brand.logo_bg_color is explicitly set, use it directly (user override).
    Otherwise auto-detect from logo brightness.
    """
    # ── User override takes priority — skip all detection ─────────────────────
    if brand.logo_bg_color and brand.logo_bg_color.strip():
        return brand.logo_bg_color.strip()

    brightness = _detect_logo_brightness(logo_path)

    # 'light' means dark text detected → logo needs a LIGHT background
    # 'dark'  means light/white text detected → logo needs a DARK (primary) background
    if brightness == 'light':
        selected_color = brand.text_light if brand.text_light else "#FFFFFF"
    else:
        # Verify that brand.primary is actually dark enough to use as background
        primary_brightness = _brightness_of_color(brand.primary)
        if primary_brightness > 190:
            # Primary is too light — fall back to text_dark or absolute dark
            text_dark_brightness = _brightness_of_color(brand.text_dark or "#333333")
            if text_dark_brightness < 150:
                selected_color = brand.text_dark
            else:
                selected_color = "#1a1a1a"
        else:
            selected_color = brand.primary
    return selected_color


def _brightness_of_color(hex_color: str) -> float:
    """Calculate brightness of a hex color (0-255)."""
    try:
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        # Standard brightness formula
        return (r * 0.299 + g * 0.587 + b * 0.114)
    except Exception:
        return 128  # Default


def _draw_logo_in_header(c, logo_path: str, x: float, y: float, size: float = 0.6, max_w: float = None):
    """
    Draw logo image directly in header band (no background box).
    Logo is positioned at (x, y) and sized to fit within the header.
    size  : max height in points
    max_w : optional max width cap in points (prevents wide logos from spanning the header)
    """
    if not logo_path or not os.path.exists(logo_path):
        return

    try:
        from reportlab.lib.utils import ImageReader

        img = ImageReader(logo_path)
        iw, ih = img.getSize()

        # Start from height constraint, then apply optional width cap
        logo_h = size
        logo_w = (iw / ih) * logo_h if ih > 0 else logo_h

        if max_w and logo_w > max_w:
            logo_w = max_w
            logo_h = (ih / iw) * logo_w if iw > 0 else logo_h


        # x is right-side anchor; logo is placed to its left
        logo_x = x - logo_w - 0.15 * inch
        logo_y = y - (logo_h / 2)

        c.drawImage(logo_path, logo_x, logo_y, width=logo_w, height=logo_h, mask="auto")
        # Note: URL linking handled by caller

    except Exception as e:
        import traceback
        traceback.print_exc()


def _draw_logo_with_background(c, logo_path: str, brand: BrandConfig, x: float, y: float, size: float = 0.5):
    """
    Draw logo with intelligent background color selection.
    Automatically chooses background based on logo brightness.
    """

    # Check file exists
    if not logo_path or not os.path.exists(logo_path):
        return
        return

    try:
        from reportlab.lib.utils import ImageReader

        # Get image dimensions
        img = ImageReader(logo_path)
        iw, ih = img.getSize()

        logo_h = size * inch
        logo_w = (iw / ih) * logo_h

        # Get background color
        bg_color = brand.logo_bg_color or _get_logo_background_color(logo_path, brand)

        # Background box with padding
        pad = 0.08 * inch
        bg_w = logo_w + pad * 2
        bg_h = logo_h + pad * 2

        # Determine corner style
        corner_radius = 4 if getattr(brand, 'corner_style', 'rounded') == 'rounded' else 0

        # Draw background rectangle FIRST (critical!)
        bg_x = x - bg_w
        bg_y = y - bg_h

        fill_color = _hex_to_color(bg_color)

        c.setFillColor(fill_color)
        c.setLineWidth(0)
        c.roundRect(bg_x, bg_y, bg_w, bg_h, corner_radius, stroke=0, fill=1)

        # Draw logo image on top
        logo_x = x - logo_w - pad
        logo_y = y - logo_h - pad

        c.drawImage(logo_path, logo_x, logo_y, width=logo_w, height=logo_h, mask="auto")


    except Exception as e:
        import traceback
        traceback.print_exc()

# ── Footer — full-bleed navy band ──────────────────────────────────────────────

def _draw_footer(c, logo_path, brand: BrandConfig):
    """Full-bleed footer band with primary color. Logo/company name right with hyperlink."""
    # Use same color logic as header/boilerplate so all three always match
    if logo_path and os.path.exists(logo_path):
        try:
            footer_bg_color = _get_logo_background_color(logo_path, brand)
        except:
            footer_bg_color = brand.primary
    else:
        # No logo: check if primary is dark enough; if not, use a dark fallback
        if _brightness_of_color(brand.primary) > 190:
            footer_bg_color = brand.text_dark if _brightness_of_color(brand.text_dark or "#333333") < 150 else "#1a1a1a"
        else:
            footer_bg_color = brand.primary

    # Footer band — full bleed, 0 to W
    c.setFillColor(_hex_to_color(footer_bg_color))
    c.rect(0, 0, W, FOOTER_H, stroke=0, fill=1)
    # Logo or company name — right side, with hyperlink to company website
    company_url = _ensure_protocol(brand.company_website) if brand.company_website else None
    if logo_path and os.path.exists(logo_path):
        # Preserve actual logo aspect ratio
        try:
            from reportlab.lib.utils import ImageReader
            img = ImageReader(logo_path)
            logo_actual_w, logo_actual_h = img.getSize()
            # Max width for footer logo
            f_logo_w = 0.9 * inch
            # Preserve actual aspect ratio
            f_logo_h = (logo_actual_h / logo_actual_w) * f_logo_w
            # Constrain height to fit in footer
            max_footer_h = FOOTER_H * 0.7
            if f_logo_h > max_footer_h:
                f_logo_h = max_footer_h
                f_logo_w = (logo_actual_w / logo_actual_h) * f_logo_h
        except:
            # Fallback to fixed ratio if image read fails
            f_logo_w = 0.9 * inch
            f_logo_h = f_logo_w * (192 / 908)

        f_logo_x = W - MARGIN - f_logo_w
        f_logo_y = (FOOTER_H - f_logo_h) / 2
        try:
            c.drawImage(logo_path, f_logo_x, f_logo_y,
                        width=f_logo_w, height=f_logo_h, mask="auto")
            if company_url:
                c.linkURL(company_url,
                          (f_logo_x, f_logo_y, f_logo_x + f_logo_w, f_logo_y + f_logo_h),
                          relative=0)
        except Exception:
            # Text fallback
            c.setFont(_font("Poppins-Bold"), 9)
            # Adjust text color based on footer background
            if footer_bg_color == brand.text_light:
                c.setFillColor(_hex_to_color(brand.text_dark))
            else:
                c.setFillColor(_hex_to_color(brand.text_light))
            fx = W - MARGIN - 48
            c.drawString(fx, FOOTER_H * 0.35, brand.company_name[:20].upper())
            if company_url:
                c.linkURL(company_url, (fx, 0, W - MARGIN, FOOTER_H), relative=0)
    else:
        # Text fallback with link
        c.setFont(_font("Poppins-Bold"), 9)
        # Adjust text color based on footer background
        if footer_bg_color == brand.text_light:
            c.setFillColor(_hex_to_color(brand.text_dark))
        else:
            c.setFillColor(_hex_to_color(brand.text_light))
        fx = W - MARGIN - 48
        c.drawString(fx, FOOTER_H * 0.35, brand.company_name[:20].upper())
        if company_url:
            c.linkURL(company_url, (fx, 0, W - MARGIN, FOOTER_H), relative=0)

    # Attribution marker — tiny, left side, links to project page
    _draw_attribution_marker(c, 0, 0, footer_bg_color, brand)

def _draw_attribution_marker(c, x: float, y: float, bg_color: str, brand: BrandConfig):
    """Tiny 'MVPMM-briefly' credit — indexable by search engines, discreet in the footer."""
    marker_font_sz = 5
    marker_text = "MVPMM-briefly"
    c.setFont(_font("OpenSans"), marker_font_sz)
    # Color: very low contrast against footer background so it's discreet but present in PDF text
    if _brightness_of_color(bg_color) > 160:
        c.setFillColor(HexColor("#333333"))
        c.setFillAlpha(0.15)
    else:
        c.setFillColor(HexColor("#FFFFFF"))
        c.setFillAlpha(0.12)
    c.drawString(x + 4, y + 3, marker_text)
    c.setFillAlpha(1.0)

# ── CTA block ─────────────────────────────────────────────────────────────────

def _ensure_protocol(url: str) -> str:
    """Ensure URL has protocol (http:// or https://)."""
    if not url:
        return url
    url = url.strip()
    if not url:
        return url
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url

def _draw_cta_block(c, elev_hdr, elev_body, cta_text, cta_url, brand: BrandConfig):
    """
    CTA / boilerplate block — full bleed (edge to edge, flush to page bottom).
    Layout: [body text left] [button + logo stacked right, centered as unit]
    """
    # Use boilerplate verbatim; fall back to header then generic line
    body = (elev_body or elev_hdr or
            f"{brand.company_name} transforms complex content into clear, actionable insights.")

    # Full bleed — edge to edge
    block_y = 0       # flush to page bottom
    box_x   = 0
    box_w   = W

    # CTA button — measure text first, then size rectangle to fit
    cta_display = (cta_text or "").strip()
    if not cta_display and cta_url:
        cta_display = "LEARN MORE"   # never show raw URL as button text
    has_btn       = bool(cta_display)
    btn_text_sz   = 10.0
    btn_text_lead = btn_text_sz * 1.35
    btn_pad_x     = 0.18 * inch
    btn_pad_y     = 0.14 * inch
    btn_inner_w   = 1.5 * inch

    if has_btn:
        btn_max_chars = max(4, int(btn_inner_w / (btn_text_sz * 0.52)))
        btn_lines     = _wrap(cta_display.upper(), btn_max_chars)
        btn_text_h    = len(btn_lines) * btn_text_lead
        btn_w         = btn_inner_w + 2 * btn_pad_x
        btn_h         = btn_text_h + 2 * btn_pad_y
        btn_x         = W - MARGIN - btn_w
    else:
        btn_w = 0; btn_h = 0; btn_x = W - MARGIN
        btn_lines = []; btn_text_h = 0

    # Text area: page margin on left, gap before button on right
    text_x = MARGIN
    text_w = btn_x - text_x - 0.25 * inch   # 0.25" gap before button (0.1" breathing room on right)

    # Body font matches page body copy
    body_sz   = BODY_FONT_SZ
    body_lead = BODY_LEADING
    lines     = _wrap_by_width(body, text_w, _font("OpenSans"), body_sz)
    n_lines   = len(lines)
    text_h    = n_lines * body_lead

    # Box height: tall enough for [button+logo stack] or body text, with equal padding
    pad_v  = 0.30 * inch
    # Estimate logo height for stack sizing (logo width = btn_w)
    _logo_h_est = btn_w * (192 / 908) if has_btn else 0
    _logo_gap_est = 0.20 * inch if has_btn else 0
    stack_h_est = btn_h + _logo_gap_est + _logo_h_est
    box_h  = max(stack_h_est + 2 * pad_v, text_h + 2 * pad_v)
    box_h  = max(1.5 * inch, box_h)

    # ── Background color: same logic as header/footer so all three always match ──
    logo_path_cta = brand.company_logo_path if brand.company_logo_path else None
    if logo_path_cta and os.path.exists(logo_path_cta):
        try:
            bg_color = _get_logo_background_color(logo_path_cta, brand)
        except Exception as e:
            bg_color = brand.primary
    else:
        bg_color = brand.primary

    # ── Background — full bleed ─────────────────────────────────────────────────
    c.setFillColor(_hex_to_color(bg_color))
    c.rect(box_x, block_y, box_w, box_h, stroke=0, fill=1)

    # ── Divider line at top of boilerplate (when background matches page) ───────
    # Add a subtle divider line to set off the boilerplate box
    divider_color = brand.border if bg_color == brand.text_light else brand.secondary
    c.setStrokeColor(_hex_to_color(divider_color))
    c.setLineWidth(1)
    c.line(0, block_y + box_h, W, block_y + box_h)

    # ── Body text — true vertical center in box ───────────────────────────────
    # Place first baseline so visual block (cap-top → descender-bottom) is centered
    _cap_h  = body_sz * 0.72
    _desc_h = body_sz * 0.18
    text_top_y = block_y + box_h / 2 + ((n_lines - 1) * body_lead + _desc_h - _cap_h) / 2

    # Text color adapts to whether the background ended up light or dark
    text_color = brand.text_dark if bg_color == brand.text_light else brand.text_light
    _draw_text_block(c, text_x, text_top_y, text_w, body,
                     _font("OpenSans"), body_sz, body_lead,
                     _hex_to_color(text_color))

    # ── Right column: [button + logo] stacked and centered as a unit ───────────
    if has_btn:
        # Measure logo
        logo_gap   = 0.20 * inch
        if logo_path_cta and os.path.exists(logo_path_cta):
            # Preserve actual logo aspect ratio - don't force to button width
            from reportlab.lib.utils import ImageReader
            try:
                img = ImageReader(logo_path_cta)
                logo_actual_w, logo_actual_h = img.getSize()
                # Max height for logo in stack (reasonable size below button)
                logo_h_cta = 0.50 * inch
                # Calculate width preserving actual aspect ratio
                logo_w_cta = (logo_actual_w / logo_actual_h) * logo_h_cta
                # Constrain width to not exceed button width
                if logo_w_cta > btn_w:
                    logo_w_cta = btn_w
                    logo_h_cta = (logo_actual_h / logo_actual_w) * logo_w_cta
            except:
                logo_w_cta = 0; logo_h_cta = 0; logo_gap = 0
        else:
            logo_w_cta = 0; logo_h_cta = 0; logo_gap = 0

        stack_h = btn_h + logo_gap + logo_h_cta
        stack_y = block_y + (box_h - stack_h) / 2   # bottom of the whole stack
        btn_y   = stack_y + logo_h_cta + logo_gap    # button sits above logo

        c.setFillColor(_hex_to_color(brand.accent))
        c.setLineWidth(0)
        c.roundRect(btn_x, btn_y, btn_w, btn_h, 4, stroke=0, fill=1)

        # Button label — vertically centered: start top of text block at center + half text height
        c.setFont(_font("OpenSans-Bold"), btn_text_sz)
        c.setFillColor(_hex_to_color(brand.text_light))
        btn_ty = btn_y + btn_h / 2 + btn_text_h / 2 - btn_text_lead + btn_text_sz * 0.35
        for bl in btn_lines:
            c.drawCentredString(btn_x + btn_w / 2, btn_ty, bl)
            btn_ty -= btn_text_lead

        if cta_url:
            url = _ensure_protocol(cta_url)
            if url:
                c.linkURL(url, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), relative=0)

        # Logo below button (bottom of stack) — or company name text if no logo
        if logo_h_cta > 0:
            logo_x_cta = btn_x + (btn_w - logo_w_cta) / 2
            logo_bottom_cta = stack_y
            try:
                c.drawImage(logo_path_cta, logo_x_cta, logo_bottom_cta,
                            width=logo_w_cta, height=logo_h_cta, mask="auto")
                logo_link = _ensure_protocol(cta_url or brand.company_website)
                if logo_link:
                    c.linkURL(logo_link, (logo_x_cta, logo_bottom_cta,
                                          logo_x_cta + logo_w_cta, logo_bottom_cta + logo_h_cta), relative=0)
            except Exception:
                pass
        elif brand.company_name:
            # No logo: draw company name centered below the button
            name_sz = 8
            name_text = brand.company_name[:24].upper()
            name_color = brand.text_dark if bg_color == brand.text_light else brand.text_light
            c.setFont(_font("Poppins-Bold"), name_sz)
            c.setFillColor(_hex_to_color(name_color))
            name_y = btn_y - 0.18 * inch
            c.drawCentredString(btn_x + btn_w / 2, name_y, name_text)
            company_url = _ensure_protocol(brand.company_website) if brand.company_website else None
            if company_url:
                name_w = pdfmetrics.stringWidth(name_text, _font("Poppins-Bold"), name_sz)
                c.linkURL(company_url, (btn_x + btn_w / 2 - name_w / 2 - 2, name_y - 2,
                                        btn_x + btn_w / 2 + name_w / 2 + 2, name_y + name_sz + 2), relative=0)

    # Attribution marker — bottom-left of CTA block
    _draw_attribution_marker(c, 0, 0, bg_color, brand)

# ── Page header ────────────────────────────────────────────────────────────────

def _render_page_header(c, title, subtitle, brand: BrandConfig):
    header_y = H - HEADER_H

    # Use same color logic as footer/boilerplate so all three always match
    logo_path = brand.company_logo_path if brand.company_logo_path else None
    if logo_path and os.path.exists(logo_path):
        header_bg_color = _get_logo_background_color(logo_path, brand)
    else:
        # No logo: ensure primary is dark enough for a readable bg; else use absolute dark
        if _brightness_of_color(brand.primary) > 190:
            header_bg_color = brand.text_dark if _brightness_of_color(brand.text_dark or "#333333") < 150 else "#1a1a1a"
        else:
            header_bg_color = brand.primary

    c.setFillColor(_hex_to_color(header_bg_color))
    c.rect(0, header_y, W, HEADER_H + 3, stroke=0, fill=1)

    # Bottom border when background is light (makes header edge visible against white page)
    if header_bg_color == brand.text_light:
        border_clr = brand.border if brand.border else "#cccccc"
        c.setStrokeColor(_hex_to_color(border_clr))
        c.setLineWidth(1.2)
        c.line(0, header_y, W, header_y)

    _draw_header_texture(c, header_y, brand, seed_str=title)
    _draw_logo(c, logo_path, brand)

    # Title + subtitle — vertically centered as a group in the header band
    title_font_sz   = 24
    title_leading   = title_font_sz * 1.3       # 31.2pt
    subtitle_sz     = 12.5
    subtitle_lead   = subtitle_sz * 1.3         # 16.25pt
    title_sub_gap   = 5                         # pts between title block and subtitle
    logo_w_header   = 1.6 * inch
    title_avail_w   = W - MARGIN - logo_w_header - 0.5 * inch
    title_max_chars = max(10, int(title_avail_w / (title_font_sz * 0.58)))
    title_lines     = _wrap(title, title_max_chars)[:3]
    n_title_lines   = len(title_lines)

    # Visual height of the combined block (cap-height on top, desc on subtitle bottom).
    # NOTE: the draw loop decrements ty one extra time after the last line, so
    # subtitle_y = ty - title_sub_gap is already n_title_lines*leading below title_y.
    # block_visual_h must match that exactly: use n_title_lines (not n-1), drop subtitle_lead.
    cap_h_title    = title_font_sz * 0.72
    desc_h_sub     = subtitle_sz * 0.22
    block_visual_h = (cap_h_title
                      + n_title_lines * title_leading
                      + title_sub_gap
                      + desc_h_sub)

    # Center block in header band
    header_center = (H - HEADER_H) + HEADER_H / 2
    title_y       = header_center + block_visual_h / 2 - cap_h_title

    header_text_color = brand.text_dark if header_bg_color == brand.text_light else brand.text_light

    c.setFont(_font("Poppins-Bold"), title_font_sz)
    c.setFillColor(_hex_to_color(header_text_color))
    ty = title_y
    for ln in title_lines:
        c.drawString(MARGIN, ty, ln)
        ty -= title_leading

    # Subtitle immediately below title block
    subtitle_y = ty - title_sub_gap
    c.setFont(_font("OpenSans"), subtitle_sz)
    c.setFillColor(_hex_to_color(header_text_color))
    sub_max   = max(10, int((W * 0.72) / (subtitle_sz * 0.52)))
    sub_lines = _wrap(subtitle, sub_max)[:1]
    if subtitle and sub_lines:
        c.drawString(MARGIN, subtitle_y, sub_lines[0])

    return header_y

def _render_narrow_band(c, brand: BrandConfig):
    """Thin band at the top of page 2 in primary color. Shows company name when no logo."""
    band_h = 0.45 * inch
    band_y = H - band_h
    c.setFillColor(_hex_to_color(brand.primary))
    c.rect(0, band_y, W, band_h + 3, stroke=0, fill=1)
    # Company name fallback (no logo case)
    logo_path = brand.company_logo_path if brand.company_logo_path else None
    if not (logo_path and os.path.exists(logo_path)) and brand.company_name:
        c.setFont(_font("Poppins-Bold"), 8)
        c.setFillColor(_hex_to_color(brand.text_light))
        name_text = brand.company_name[:24].upper()
        name_w = pdfmetrics.stringWidth(name_text, _font("Poppins-Bold"), 8)
        c.drawString(W - MARGIN - name_w, band_y + (band_h - 8) / 2 + 2, name_text)
        company_url = _ensure_protocol(brand.company_website) if brand.company_website else None
        if company_url:
            c.linkURL(company_url, (W - MARGIN - name_w - 4, band_y, W - MARGIN + 4, band_y + band_h), relative=0)

# ── Main generate function ─────────────────────────────────────────────────────

def generate_pdf(data: dict, image_paths: Optional[dict] = None, brand_config: Optional[dict] = None, page_preference: int = 2) -> bytes:
    """
    Generate PDF with custom branding.

    Args:
        data: Brief content dict (title, subtitle, exec_summary, takeaways, sections, etc.)
        image_paths: Optional dict mapping section index to image file paths
        brand_config: Optional branding config dict; defaults to neutral branding if not provided
        page_preference: 2 for 2-page template, 3 for 3-page template (default: 2)

    Returns:
        PDF file bytes
    """
    # Initialize or validate brand config
    try:
        brand = create_brand_config(brand_config) if brand_config else get_default_brand_config()
    except ValueError as e:
        # Log error but fall back to defaults rather than failing
        brand = get_default_brand_config()

    # Route to appropriate template
    if page_preference == 3:
        return _generate_3page_pdf(data, image_paths, brand)
    else:
        return _generate_2page_pdf(data, image_paths, brand)


def _generate_2page_pdf(data: dict, image_paths: Optional[dict], brand: BrandConfig) -> bytes:
    """Generate 2-page PDF template."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    title        = data.get("title", "Executive Brief")
    subtitle     = data.get("subtitle", "")
    exec_summary = data.get("exec_summary", "")
    takeaways    = [t for t in (data.get("takeaways") or [])[:3] if t.strip()]
    while len(takeaways) < 3:
        takeaways.append("")
    sections     = data.get("sections", [])
    faqs         = [f for f in data.get("faqs", []) if f.get("question", "").strip()]
    elev_hdr     = _remove_banned_phrases(data.get("elevator_pitch_header", ""))
    elev_body    = _remove_banned_phrases(data.get("elevator_pitch_body", ""))
    cta_text     = data.get("cta_text", "")
    cta_url      = data.get("cta_url", "")
    blog_url     = data.get("blog_url", "")
    image_paths  = image_paths or {}
    # Use uploaded logo if provided; no generic fallback (open-source — no default branding)
    logo_path    = brand.company_logo_path if brand.company_logo_path else None

    # ── PAGE 1: At a Glance ───────────────────────────────────────────────────
    _render_page_header(c, title, subtitle, brand)

    y = H - HEADER_H - 0.4 * inch

    # QUICK OVERVIEW label + exec summary
    y = _draw_section_label(c, MARGIN, y, "Quick Overview", brand)
    y -= 4
    y = _draw_text_block(c, MARGIN, y, CONTENT_W, exec_summary,
                         _font(brand.font_body), BODY_FONT_SZ, BODY_LEADING, _hex_to_color(brand.text_dark))
    y -= 0.32 * inch

    # Separator line before Key Takeaways
    sep_line_y = y - 0.12 * inch
    c.setStrokeColor(_hex_to_color(brand.border))
    c.setLineWidth(0.75)
    c.line(MARGIN, sep_line_y, W - MARGIN, sep_line_y)
    y = sep_line_y - 0.15 * inch  # 0.15" below every divider bar

    # KEY TAKEAWAYS label + 3 cards stretched to fill remaining page 1 space
    y = _draw_section_label(c, MARGIN, y, "Key Takeaways", brand)
    y -= 6

    page1_bottom = FOOTER_H + 0.25 * inch

    if takeaways:
        y = _draw_takeaway_cards(c, takeaways, y, brand, available_h=0)

    # FAQ section on page 1 — at least 2 questions must show
    if faqs and y - page1_bottom > 0.6 * inch:
        faq_h_all = _estimate_faq_section_height(faqs)
        faq_h_2q  = _estimate_faq_section_height(faqs[:2])   # height for 2 questions
        sep_h     = 0.75 + 0.20 * inch + 0.15 * inch         # sep line + gaps
        available = y - FOOTER_H
        total_h   = sep_h + faq_h_all
        # Guarantee at least 2 questions: minimise pad_above if space is tight
        if available >= sep_h + faq_h_2q + 0.30 * inch:
            # Enough space for ≥2; center the block (cap pad_above to 0.45")
            pad_above = min((available - total_h) / 2, 0.45 * inch)
            pad_above = max(pad_above, 0.25 * inch)  # minimum 0.25" above divider
        else:
            pad_above = 0.18 * inch   # squeeze to make room for 2nd question
        sep_line_y = y - pad_above
        c.setStrokeColor(_hex_to_color(brand.border))
        c.setLineWidth(0.75)
        c.line(MARGIN, sep_line_y, W - MARGIN, sep_line_y)
        y = sep_line_y - 0.15 * inch
        y = _draw_faq_section(c, faqs, y, page1_bottom, brand)

    _draw_footer(c, logo_path, brand)
    c.showPage()

    # ── PAGE 2: Deep Dive ─────────────────────────────────────────────────────
    _render_narrow_band(c, brand)
    y = H - 0.45 * inch - 0.4 * inch

    # Compute CTA block height (mirrors _draw_cta_block logic) to set correct bottom boundary
    _bp2_body = elev_body if elev_body else f"{brand.company_name} transforms complex content into clear, actionable insights."
    _bp2_btn_inner_w = 1.5 * inch; _bp2_btn_text_sz = 10.0; _bp2_btn_text_lead = _bp2_btn_text_sz * 1.35
    _bp2_btn_pad_x = 0.18 * inch; _bp2_btn_pad_y = 0.14 * inch
    _bp2_cta_disp = (cta_text or "").strip() or ("LEARN MORE" if cta_url else "")
    if _bp2_cta_disp:
        _bp2_btn_mc = max(4, int(_bp2_btn_inner_w / (_bp2_btn_text_sz * 0.52)))
        _bp2_btn_h = len(_wrap(_bp2_cta_disp.upper(), _bp2_btn_mc)) * _bp2_btn_text_lead + 2 * _bp2_btn_pad_y
        _bp2_btn_w = _bp2_btn_inner_w + 2 * _bp2_btn_pad_x
    else:
        _bp2_btn_h = 0; _bp2_btn_w = 0
    _bp2_btn_x = W - MARGIN - _bp2_btn_w
    _bp2_text_w = _bp2_btn_x - MARGIN - 0.25 * inch
    _bp2_text_h = len(_wrap_by_width(_bp2_body, _bp2_text_w, _font("OpenSans"), BODY_FONT_SZ)) * BODY_LEADING
    _bp2_pad_v = 0.30 * inch
    _bp2_logo_h_est = _bp2_btn_w * (192 / 908) if _bp2_cta_disp else 0
    _bp2_logo_gap   = 0.20 * inch if _bp2_cta_disp else 0
    _bp2_stack_h    = _bp2_btn_h + _bp2_logo_gap + _bp2_logo_h_est
    _bp2_box_h = max(_bp2_stack_h + 2 * _bp2_pad_v, _bp2_text_h + 2 * _bp2_pad_v)
    _bp2_box_h = max(1.5 * inch, _bp2_box_h)
    # Read button: btn_y = y_text_end - WHITE_SPACE_LINES - btn_padding_y
    # Must stay above CTA block: y_text_end > _bp2_box_h + WHITE_SPACE_LINES(12pt) + btn_padding_y(6pt)
    # Add small safety margin to avoid button kissing the CTA top edge
    _read_btn_clearance = 0.75 * BODY_LEADING + 6 + 0.12 * inch  # ~26pt
    bottom_p2 = _bp2_box_h + _read_btn_clearance

    for idx, section in enumerate(sections):
        hdr  = section.get("header", "")
        body = section.get("body", "")

        if y < bottom_p2 + 0.8 * inch:
            break

        if hdr:
            y -= 0.22 * inch   # breathing room above section header
            y = _section_header(c, MARGIN, y, hdr, brand)
            y -= 2

        # Optional embedded image
        if idx in image_paths and image_paths[idx]:
            try:
                from reportlab.lib.utils import ImageReader
                img_r = ImageReader(image_paths[idx])
                iw, ih = img_r.getSize()
                max_img_h = 2.0 * inch
                scale = min(CONTENT_W / iw, max_img_h / ih)
                dw, dh = iw * scale, ih * scale
                dx = MARGIN + (CONTENT_W - dw) / 2
                c.setStrokeColor(HexColor("#E0E0E0"))
                c.setLineWidth(0.5)
                c.rect(dx - 2, y - dh - 2, dw + 4, dh + 4, stroke=1, fill=0)
                c.drawImage(image_paths[idx], dx, y - dh,
                            width=dw, height=dh, mask="auto")
                y -= dh + 10
            except Exception:
                pass

        if body:
            avail     = y - bottom_p2
            ml        = max(4, int(avail / BODY_LEADING))
            all_lines = _wrap_by_width(body, CONTENT_W, _font(brand.font_body), BODY_FONT_SZ)
            render_n  = min(ml, len(all_lines))
            # If truncating, backtrack to last sentence-ending line
            if render_n < len(all_lines):
                for i in range(render_n, 0, -1):
                    if all_lines[i - 1].rstrip().endswith(('.', '!', '?')):
                        render_n = i
                        break
            y = _draw_text_block(c, MARGIN, y, CONTENT_W, ' '.join(all_lines[:render_n]),
                                 _font(brand.font_body), BODY_FONT_SZ, BODY_LEADING, _hex_to_color(brand.text_dark),
                                 max_lines=render_n)
        y -= 0.06 * inch  # small gap between sections (pre-header gap handles visual separation)

    # "Read the full article" link — styled as button
    # Ensure minimal white space (0.75 lines) between section text and button to fill page
    WHITE_SPACE_LINES = 0.75 * BODY_LEADING  # ~11.25 pt ≈ 0.16 inch

    # Button positioned with minimal white space above it
    read_y = y - WHITE_SPACE_LINES  # Button positioned closer to section content

    if blog_url:
        label = "READ THE FULL ARTICLE \u2192"

        # Draw button background (accent color)
        btn_padding_x = 0.15 * inch
        btn_padding_y = 6
        font_sz = 10.5
        label_width = len(label) * font_sz * 0.5
        btn_w = label_width + btn_padding_x * 2
        btn_x = MARGIN  # LEFT-ALIGNED
        btn_y = read_y - btn_padding_y
        btn_h = 20

        c.setFillColor(_hex_to_color(brand.accent))
        c.setLineWidth(0)
        c.roundRect(btn_x, btn_y, btn_w, btn_h, 3, stroke=0, fill=1)  # rounded corners

        # Draw button text (light color for contrast) - centered within button
        c.setFont(_font("OpenSans-Bold"), font_sz)
        c.setFillColor(_hex_to_color(brand.text_light))
        # Center text vertically within button
        text_x = btn_x + btn_padding_x  # Padding from left edge
        text_y = btn_y + (btn_h / 2) - 2.5  # Center vertically
        c.drawString(text_x, text_y, label)

        # Ensure URL has protocol
        blog_url_with_protocol = _ensure_protocol(blog_url)
        if blog_url_with_protocol:
            c.linkURL(blog_url_with_protocol,
                      (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h),
                      relative=0)

    # CTA block is the full-bleed bottom element on page 2 — no separate footer
    _draw_cta_block(c, elev_hdr, elev_body, cta_text, cta_url, brand)

    c.save()
    buf.seek(0)
    return buf.read()


# ────────────────────────────────────────────────────────────────────────────────
# 3-PAGE TEMPLATE GENERATION
# ────────────────────────────────────────────────────────────────────────────────

def _generate_3page_pdf(data: dict, image_paths: Optional[dict], brand: BrandConfig) -> bytes:
    """
    Generate 3-page PDF template:
    Page 1: Cover (title + subtitle + color blocks + summary)
    Page 2: Introduction + Key Takeaways + Optional Image
    Page 3: Content + Conclusion + Stats/Checklist/FAQ + Boilerplate + CTA
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    # Extract data
    title           = data.get("title", "Executive Brief")
    subtitle        = data.get("subtitle", "")
    exec_summary    = data.get("exec_summary", "")
    introduction    = data.get("introduction", "")
    takeaways       = [t for t in data.get("takeaways", [])[:3] if t.strip()]
    while len(takeaways) < 3:
        takeaways.append("")
    sections        = data.get("sections", [])
    continuing_content = data.get("continuing_content", "")
    conclusion      = data.get("conclusion", "")
    stats_or_faq_type = data.get("stats_or_faq_type", "faq")
    # Use uploaded logo if provided; no generic fallback (open-source — no default branding)
    logo_path       = brand.company_logo_path if brand.company_logo_path else None
    stats_or_faq_items = data.get("stats_or_faq_items", [])
    cta_text        = data.get("cta_text", "")
    cta_url         = data.get("cta_url", "")
    blog_url        = data.get("blog_url", "")
    elev_body       = _remove_banned_phrases(data.get("elevator_pitch_body", ""))
    image_paths     = image_paths or {}

    # ── PAGE 1: Cover ──────────────────────────────────────────────────────
    _render_3page_cover(c, title, subtitle, exec_summary, brand, logo_path)
    c.showPage()

    # First 2 sections go to page 2 (below cards); remaining go to page 3
    sections_for_page2 = sections[:2] if sections else []
    remaining_sections = sections[2:] if len(sections) > 2 else []

    # ── PAGE 2: Introduction + Takeaways + 2 sections ──────────────────────
    p2_overflow = _render_3page_page2(c, introduction, takeaways, sections_for_page2, brand, logo_path, image_paths)
    c.showPage()

    # ── PAGE 3: Overflow from P2 + remaining sections + Stats + CTA ───────
    # Any text that didn't fit on P2 continues at the top of P3
    remaining_sections = (p2_overflow or []) + remaining_sections
    _render_3page_page3(c, remaining_sections, continuing_content, conclusion,
                        stats_or_faq_type, stats_or_faq_items,
                        cta_text, cta_url, blog_url, elev_body,
                        brand, logo_path)
    c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()


def _draw_header_bar(c, brand: BrandConfig, logo_path: Optional[str] = None):
    """
    Draw full-width header band with logo (if exists).
    Band spans entire page width with logo positioned inside.
    Uses intelligent background color based on logo brightness.
    """

    # Use same color logic as footer/boilerplate so all three always match
    if logo_path and os.path.exists(logo_path):
        header_bg_color = _get_logo_background_color(logo_path, brand)
    else:
        # No logo: check if primary is dark enough; if not, use a dark fallback
        if _brightness_of_color(brand.primary) > 190:
            header_bg_color = brand.text_dark if _brightness_of_color(brand.text_dark or "#333333") < 150 else "#1a1a1a"
        else:
            header_bg_color = brand.primary

    # Draw FULL-WIDTH header band flush to top of page
    header_h = 1.0 * inch
    header_y = H - header_h   # flush to top edge


    c.setFillColor(_hex_to_color(header_bg_color))
    c.setLineWidth(0)
    c.rect(0, header_y, W, header_h + 3, stroke=0, fill=1)

    # Border at bottom edge when background is light (so header is visible against white page)
    if header_bg_color == brand.text_light:
        border_clr = brand.border if brand.border else "#cccccc"
        c.setStrokeColor(_hex_to_color(border_clr))
        c.setLineWidth(1.0)
        c.line(0, header_y, W, header_y)

    # Draw logo inside the header band (right side with padding)
    if logo_path and os.path.exists(logo_path):
        # 50% of header height for visual balance in the 1" band
        logo_size = header_h * 0.50
        # Max width cap: wide logos must not dominate the 1" header
        max_logo_w_3pg = W * 0.18  # 18% of page width ≈ 1.55" (was 30%)

        # Position: right side with margin, vertically centered in header band
        logo_x = W - MARGIN - 0.1 * inch
        logo_y = header_y + header_h / 2   # _draw_logo_in_header treats y as vertical center


        _draw_logo_in_header(c, logo_path, logo_x, logo_y, logo_size, max_w=max_logo_w_3pg)
        # Link the header logo to company website
        logo_link = _ensure_protocol(brand.company_website)
        if logo_link:
            from reportlab.lib.utils import ImageReader as _IR
            try:
                _img = _IR(logo_path)
                _iw, _ih = _img.getSize()
                _lh = logo_size
                _lw = (_iw / _ih) * _lh if _ih > 0 else _lh
                if max_logo_w_3pg and _lw > max_logo_w_3pg:
                    _lw = max_logo_w_3pg
                    _lh = (_ih / _iw) * _lw if _iw > 0 else _lh
                _lx = logo_x - _lw - 0.15 * inch
                _ly = logo_y - (_lh / 2)
                c.linkURL(logo_link, (_lx, _ly, _lx + _lw, _ly + _lh), relative=0)
            except Exception:
                pass
    else:
        # No logo: draw company name text right-aligned in header band
        if brand.company_name:
            name_text = brand.company_name[:24].upper()
            name_sz = 9
            name_w = pdfmetrics.stringWidth(name_text, _font("Poppins-Bold"), name_sz)
            text_color = brand.text_dark if header_bg_color == brand.text_light else brand.text_light
            c.setFont(_font("Poppins-Bold"), name_sz)
            c.setFillColor(_hex_to_color(text_color))
            name_x = W - MARGIN - name_w
            name_y = header_y + header_h / 2 - name_sz * 0.35
            c.drawString(name_x, name_y, name_text)
            company_url = _ensure_protocol(brand.company_website) if brand.company_website else None
            if company_url:
                c.linkURL(company_url, (name_x - 4, header_y, W - MARGIN + 4, header_y + header_h), relative=0)


def _render_3page_cover(c, title, subtitle, summary, brand: BrandConfig, logo_path):
    """PAGE 1: Cover with title, subtitle, color blocks, and summary."""
    # Logo or header bar in top right
    _draw_header_bar(c, brand, logo_path)

    # ── Layout constants ───────────────────────────────────────────────────────
    logo_space        = 1.2 * inch
    title_width       = CONTENT_W - logo_space

    summary_font_sz    = 13
    summary_leading    = 19.5
    subtitle_font_sz   = 19
    subtitle_leading   = 25
    subtitle_width     = CONTENT_W - (0.5 * inch)
    sub_gap            = 0.30 * inch
    color_blocks_total = (3 * 0.35 + 2 * 0.14) * inch  # 1.33"

    # ── Bottom accent row (fixed position) ───────────────────────────────────
    block_height  = 0.35 * inch
    corner_radius = 0 if getattr(brand, 'corner_style', 'rounded') == 'sharp' else 6
    colors        = [brand.primary, brand.secondary, brand.accent,
                     getattr(brand, 'accent2', brand.secondary)]
    row_bottom_y  = 0.45 * inch
    row_top_y     = row_bottom_y + block_height

    # ── Title: truly centered between header bottom and color-bars zone ──────────
    # Compute available zone, then center the (title + gap + bars) group within it.
    header_h_val   = 1.0 * inch
    header_bottom  = H - header_h_val   # = 720pt

    # Dynamic font sizing: shrink until title fits in 3 lines (min 30pt)
    for title_font_sz in (44, 38, 33, 30):
        title_line_height = int(title_font_sz * 1.22)
        title_lines_list  = _wrap_by_width(title, title_width, _font(brand.font_title), title_font_sz)
        if len(title_lines_list) <= 3:
            break
    # If still >3 lines at 30pt, allow up to 4 lines at 30pt
    title_lines_list = title_lines_list[:4]

    title_font_sz     = title_font_sz   # keep final value
    title_line_height = int(title_font_sz * 1.22)
    title_lines       = len(title_lines_list)

    cap_h  = title_font_sz * 0.72
    desc_h = title_font_sz * 0.18

    title_block_h  = cap_h + (title_lines - 1) * title_line_height + desc_h
    GAP_BETWEEN    = 0.45 * inch   # fixed gap from title bottom to bars top

    # Available zone for the entire (title+bars) group.
    # Leave ~3.5" below for subtitle/summary + accent row.
    content_zone_bottom = row_top_y + 3.5 * inch
    available           = header_bottom - content_zone_bottom

    group_h  = title_block_h + GAP_BETWEEN + color_blocks_total
    pad      = max(0.50 * inch, (available - group_h) / 2)   # at least 0.5" from header

    # Title baseline
    title_start_y       = header_bottom - pad - cap_h
    title_visual_bottom = title_start_y - (title_lines - 1) * title_line_height - desc_h
    color_blocks_y      = title_visual_bottom - GAP_BETWEEN

    # ── Draw 3-row color bars ─────────────────────────────────────────────────
    _draw_color_blocks(c, color_blocks_y, brand)

    # ── Bottom accent row ─────────────────────────────────────────────────────
    widths_r4  = [1.4 * inch, 0.55 * inch, 2.2 * inch, 0.9 * inch, 1.8 * inch]
    spacing_r4 = [0.17 * inch, 0.21 * inch, 0.17 * inch, 0.17 * inch]
    xr = MARGIN
    for i, w in enumerate(widths_r4):
        c.setFillColor(_hex_to_color(colors[i % len(colors)]))
        c.setLineWidth(0)
        c.roundRect(xr, row_bottom_y, w, block_height, corner_radius, stroke=0, fill=1)
        if i < len(widths_r4) - 1:
            xr += w + spacing_r4[i]

    # ── Draw title ────────────────────────────────────────────────────────────
    title_color = _safe_text_color(brand.primary)
    _draw_text_block(c, MARGIN, title_start_y, title_width, '\n'.join(title_lines_list),
                    _font(brand.font_title), title_font_sz, title_line_height,
                    _hex_to_color(title_color))

    # ── Subtitle + summary — bottom-anchored above the bottom accent row ───────
    subtitle_lines_list = _wrap_by_width(subtitle, subtitle_width, _font("OpenSans-Bold"), subtitle_font_sz)
    subtitle_height     = len(subtitle_lines_list) * subtitle_leading
    summary_lines_list  = _wrap_by_width(summary, CONTENT_W, _font(brand.font_body), summary_font_sz)
    summary_h           = len(summary_lines_list) * summary_leading

    gap_from_accent = 0.35 * inch
    total_content_h = subtitle_height + sub_gap + summary_h
    subtitle_y      = row_top_y + gap_from_accent + total_content_h
    summary_y       = subtitle_y - sub_gap - subtitle_height


    # Draw subtitle first (higher on page)
    # Pass unwrapped text; _draw_text_block will wrap it with accurate width-based logic
    _draw_text_block(c, MARGIN, subtitle_y, subtitle_width, subtitle,
                    _font("OpenSans-Bold"), subtitle_font_sz, subtitle_leading,
                    _hex_to_color(_safe_text_color(brand.secondary)))

    # Draw summary below subtitle
    _draw_text_block(c, MARGIN, summary_y, CONTENT_W, summary,
                    _font(brand.font_body), summary_font_sz, summary_leading,
                    _hex_to_color(brand.text_dark))


def _draw_color_blocks(c, y, brand: BrandConfig):
    """
    Draw decorative color blocks with ASYMMETRICAL positioning.
    Row 1 skews right, Row 2 skews left. Unequal spacing between blocks.
    All blocks same height, variable widths.
    """
    colors = [
        brand.primary,
        brand.secondary,
        brand.accent,
        getattr(brand, 'accent2', brand.secondary)  # Safe attribute access
    ]

    # Determine corner style from brand (with safe default)
    corner_radius = 0 if getattr(brand, 'corner_style', 'rounded') == 'sharp' else 6

    # All blocks same height
    block_height = 0.35 * inch

    # ROW 1: Skew RIGHT - start further right, unequal spacing
    # Widths and spacing vary for dynamic look
    widths_row1 = [2.0 * inch, 1.2 * inch, 1.8 * inch, 1.6 * inch]
    spacing_row1 = [0.22 * inch, 0.09 * inch, 0.28 * inch]  # UNEQUAL spacing between blocks

    # Calculate row 1 positions (skew to the right - larger left margin)
    x_pos_row1 = []
    x_current = MARGIN + 0.5 * inch  # Start further right
    for i, width in enumerate(widths_row1):
        x_pos_row1.append(x_current)
        if i < len(widths_row1) - 1:
            x_current += width + spacing_row1[i]
        else:
            x_current += width

    # Draw row 1
    for i in range(len(widths_row1)):
        c.setFillColor(_hex_to_color(colors[i % len(colors)]))
        c.setLineWidth(0)
        c.roundRect(x_pos_row1[i], y - block_height, widths_row1[i], block_height,
                   corner_radius, stroke=0, fill=1)

    # ROW 2: Skew LEFT - start close to left, unequal spacing (different pattern)
    y_row2 = y - block_height - 0.14 * inch

    widths_row2 = [1.5 * inch, 2.3 * inch, 1.7 * inch]
    spacing_row2 = [0.12 * inch, 0.25 * inch]  # UNEQUAL spacing - different pattern from row 1

    # Calculate row 2 positions (skew to the left - shift left by 0.25")
    x_pos_row2 = []
    x_current = MARGIN - 0.25 * inch  # Start further left (shifted 0.25" left)
    for i, width in enumerate(widths_row2):
        x_pos_row2.append(x_current)
        if i < len(widths_row2) - 1:
            x_current += width + spacing_row2[i]
        else:
            x_current += width

    # Draw row 2
    for i in range(len(widths_row2)):
        c.setFillColor(_hex_to_color(colors[(i + 2) % len(colors)]))
        c.setLineWidth(0)
        c.roundRect(x_pos_row2[i], y_row2 - block_height, widths_row2[i], block_height,
                   corner_radius, stroke=0, fill=1)

    # ROW 3: Skew RIGHT (opposite of row 2) - create visual balance with extra short bar
    y_row3 = y_row2 - block_height - 0.14 * inch

    widths_row3 = [2.2 * inch, 0.6 * inch, 1.8 * inch, 1.3 * inch]  # Added short bar in middle
    spacing_row3 = [0.08 * inch, 0.28 * inch, 0.12 * inch]  # Very uneven spacing

    # Calculate row 3 positions (skew to the right - balance row 2)
    x_pos_row3 = []
    x_current = MARGIN + 0.3 * inch
    for i, width in enumerate(widths_row3):
        x_pos_row3.append(x_current)
        if i < len(widths_row3) - 1:
            x_current += width + spacing_row3[i]
        else:
            x_current += width

    # Draw row 3
    for i in range(len(widths_row3)):
        c.setFillColor(_hex_to_color(colors[(i + 1) % len(colors)]))
        c.setLineWidth(0)
        c.roundRect(x_pos_row3[i], y_row3 - block_height, widths_row3[i], block_height,
                   corner_radius, stroke=0, fill=1)


def _render_3page_page2(c, introduction, takeaways, sections_for_page2, brand: BrandConfig, logo_path, image_paths):
    """PAGE 2: Introduction + Key Takeaways + up to 2 content sections.
    Returns a list of overflow section dicts (body text that didn't fit) to be
    continued at the top of page 3."""
    _draw_header_bar(c, brand, logo_path)

    y = H - 1.0 * inch - 0.50 * inch   # header band now flush to top

    # ── Introduction ──────────────────────────────────────────────────────────
    if introduction:
        y = _draw_section_label(c, MARGIN, y, "Introduction", brand)
        y -= 4
        y = _draw_text_block(c, MARGIN, y, CONTENT_W, introduction,
                             _font(brand.font_body), BODY_FONT_SZ, BODY_LEADING,
                             _hex_to_color(brand.text_dark))
        y -= 0.28 * inch

    # ── Separator + Key Takeaways label ───────────────────────────────────────
    c.setStrokeColor(_hex_to_color(brand.border))
    c.setLineWidth(0.75)
    c.line(MARGIN, y, W - MARGIN, y)
    y -= 0.25 * inch

    y = _draw_section_label(c, MARGIN, y, "Key Takeaways", brand)
    y -= 6

    # ── Cards — natural height (no stretch), leaving room for sections below ──
    takeaway_list = takeaways if isinstance(takeaways, list) else []
    if takeaway_list:
        y = _draw_takeaway_cards(c, takeaway_list, y, brand, available_h=0)

    # ── Divider line after key takeaways ──────────────────────────────────────
    y -= 0.61 * inch
    c.setStrokeColor(_hex_to_color(brand.border))
    c.setLineWidth(0.75)
    c.line(MARGIN, y, W - MARGIN, y)
    y -= 0.25 * inch

    # ── Content sections (up to 2) below cards — overflow flows to P3 ────────
    bottom_limit  = FOOTER_H + 0.4 * inch
    body_max_chars = max(20, int(CONTENT_W / (BODY_FONT_SZ * 0.50)))
    overflow_sections = []

    for section in (sections_for_page2 or [])[:2]:
        hdr  = section.get("header", "")
        body = section.get("body", "")
        if y < bottom_limit + 0.5 * inch:
            # No room at all — entire section overflows
            overflow_sections.append(section)
            continue
        if hdr:
            c.setFont(_font("Poppins-Bold"), 12.5)
            c.setFillColor(_hex_to_color(brand.primary))
            c.drawString(MARGIN, y, hdr)
            y -= 0.34 * inch
        if body and y > bottom_limit:
            all_lines   = _wrap_by_width(body, CONTENT_W, _font(brand.font_body), BODY_FONT_SZ)
            avail_lines = max(3, int((y - bottom_limit) / BODY_LEADING))
            render_n    = min(avail_lines, len(all_lines))
            # Backtrack to last complete sentence so we never split mid-sentence
            if render_n < len(all_lines):
                for i in range(render_n, 0, -1):
                    if all_lines[i - 1].rstrip().endswith(('.', '!', '?')):
                        render_n = i
                        break
            rendered_text = ' '.join(all_lines[:render_n])
            y = _draw_text_block(c, MARGIN, y, CONTENT_W, rendered_text,
                                 _font(brand.font_body), BODY_FONT_SZ, BODY_LEADING,
                                 _hex_to_color(brand.text_dark), max_lines=render_n)
            y -= 0.25 * inch
            # Carry leftover complete sentences to P3 (no header — it's a continuation)
            if render_n < len(all_lines):
                overflow_body = ' '.join(all_lines[render_n:])
                overflow_sections.append({"header": None, "body": overflow_body})

    return overflow_sections


FAQ_INNER_PAD = 0.22 * inch   # left/right inner padding inside the shaded FAQ box

def _draw_faq_shaded_box(c, stats_items, stats_type, brand: BrandConfig) -> float:
    """
    Draw a shaded FAQ box (content-width, not full bleed).
    Returns the height of the box so callers can position it.
    The box is drawn at a y position passed by the caller.
    """
    # Measure content first
    q_sz   = 10.5
    q_lead = 15.5
    a_sz   = 9.5
    a_lead = 14.5
    q_marker_w = 14   # width of "Q " prefix
    indent     = 0.22 * inch   # answer indent from inner left edge
    pair_gap   = 10

    items = [i for i in (stats_items or []) if i.get("label", "").strip()][:5]
    if not items:
        return 0

    # Effective text width accounts for inner padding on both sides
    inner_w = CONTENT_W - 2 * FAQ_INNER_PAD
    total_text_h = 0
    for item in items:
        # Use _wrap_by_width with actual fonts — same as the renderer — so measurement is exact
        q_lines = len(_wrap_by_width(item.get("label", ""), inner_w - q_marker_w, _font("Poppins-Bold"), q_sz))
        a_lines = len(_wrap_by_width(item.get("value", ""), inner_w - indent, _font("OpenSans"), a_sz))
        total_text_h += q_lines * q_lead + a_lines * a_lead + pair_gap

    label_h = 18  # _draw_section_label + gap below
    pad_v   = 0.25 * inch   # equal top and bottom padding
    # Subtract trailing pair_gap from last item — no gap needed after final answer
    box_h = pad_v + label_h + total_text_h - pair_gap + pad_v
    return box_h


def _draw_faq_shaded_box_at(c, stats_items, stats_type, brand: BrandConfig, box_top_y: float):
    """Draw the FAQ shaded box with its top at box_top_y. Returns y after the box."""
    q_sz       = 10.5
    q_lead     = 15.5
    a_sz       = 9.5
    a_lead     = 14.5
    q_marker_w = 14     # width of "Q " prefix
    indent     = 0.22 * inch   # answer indent from inner left edge
    pair_gap   = 10

    items = [i for i in (stats_items or []) if i.get("label", "").strip()][:5]
    if not items:
        return box_top_y

    box_h = _draw_faq_shaded_box(c, stats_items, stats_type, brand)

    # Draw content-width shaded background
    c.setFillColor(HexColor("#EEF2F8"))
    c.setLineWidth(0)
    c.rect(MARGIN, box_top_y - box_h, CONTENT_W, box_h, stroke=0, fill=1)

    # Inner left edge: box left + FAQ_INNER_PAD
    inner_x = MARGIN + FAQ_INNER_PAD
    inner_w = CONTENT_W - 2 * FAQ_INNER_PAD

    # Section label — aligned to inner padding (matches pad_v in _draw_faq_shaded_box)
    y = box_top_y - 0.25 * inch
    y = _draw_section_label(c, inner_x, y, "Frequently Asked Questions", brand)
    y -= 10

    # Q/A pairs — all drawn from inner_x
    for item in items:
        question = item.get("label", "").strip()
        answer   = item.get("value", "").strip()
        if not question:
            continue

        q_lines = _wrap_by_width(question, inner_w - q_marker_w, _font("Poppins-Bold"), q_sz)

        c.setFont(_font("Poppins-Bold"), q_sz)
        c.setFillColor(_hex_to_color(brand.accent))
        c.drawString(inner_x, y, "Q")
        c.setFillColor(_hex_to_color(brand.primary))
        ty = y
        for ln in q_lines:
            c.drawString(inner_x + q_marker_w, ty, ln)
            ty -= q_lead
        y = ty - 2

        if answer:
            y = _draw_text_block(c, inner_x + indent, y, inner_w - indent,
                                 answer, _font("OpenSans"), a_sz, a_lead,
                                 _hex_to_color(brand.text_dark))
        y -= pair_gap

    return box_top_y - box_h


def _render_3page_page3(c, sections, continuing_content, conclusion,
                       stats_type, stats_items, cta_text, cta_url, blog_url,
                       elev_body, brand: BrandConfig, logo_path):
    """
    PAGE 3 Layout (top to bottom):
      Header band
      2-3 content paragraphs (sections with headers)
      "Read the full article" button
      0.25" white gap
      FAQ shaded edge-to-edge box
      0.25" white gap
      Boilerplate box (primary color, full text, centered CTA button)
      Footer
    """
    _draw_header_bar(c, brand, logo_path)

    # ── Measure boilerplate height — must match _draw_cta_block exactly ────────
    boilerplate_body = elev_body if elev_body else (
        f"{brand.company_name} transforms complex content into clear, actionable insights.")
    bp_sz    = BODY_FONT_SZ
    bp_lead  = BODY_LEADING
    # _draw_cta_block: text_x = MARGIN, btn is rectangle sized to text
    bp_btn_text_sz   = 10.0
    bp_btn_text_lead = bp_btn_text_sz * 1.35
    bp_btn_pad_x     = 0.18 * inch
    bp_btn_pad_y     = 0.14 * inch
    bp_btn_inner_w   = 1.5 * inch
    _bp_cta_display  = (cta_text or "").strip() or ("LEARN MORE" if cta_url else "")
    if _bp_cta_display:
        _bp_btn_mc = max(4, int(bp_btn_inner_w / (bp_btn_text_sz * 0.52)))
        _bp_btn_lines = _wrap(_bp_cta_display.upper(), _bp_btn_mc)
        _bp_btn_text_h = len(_bp_btn_lines) * bp_btn_text_lead
        bp_btn_w = bp_btn_inner_w + 2 * bp_btn_pad_x
        bp_btn_h = _bp_btn_text_h + 2 * bp_btn_pad_y
    else:
        bp_btn_w = 0; bp_btn_h = 0
    bp_btn_x   = W - MARGIN - bp_btn_w
    bp_text_w  = bp_btn_x - MARGIN - 0.25 * inch
    bp_text_h  = len(_wrap_by_width(boilerplate_body, bp_text_w, _font("OpenSans"), bp_sz)) * bp_lead
    pad_v      = 0.30 * inch   # must match _draw_cta_block exactly
    _bp_logo_h_est  = bp_btn_w * (192 / 908) if _bp_cta_display else 0
    _bp_logo_gap    = 0.20 * inch if _bp_cta_display else 0
    _bp_stack_h     = bp_btn_h + _bp_logo_gap + _bp_logo_h_est
    bp_box_h   = max(_bp_stack_h + 2 * pad_v, bp_text_h + 2 * pad_v)
    bp_box_h   = max(1.5 * inch, bp_box_h)

    # ── Measure FAQ box height ─────────────────────────────────────────────────
    faq_h = _draw_faq_shaded_box(c, stats_items, stats_type, brand)

    # ── Fixed bottom zone: boilerplate → gap → FAQ (button is in content zone) ─
    white_gap        = 0.35 * inch   # gap between boilerplate and FAQ
    btn_to_faq_gap   = 0.22 * inch   # gap between READ button bottom and FAQ top
    read_btn_h       = 22            # read button height (pt)
    cta_block_offset = 0

    # faq_top: y-coordinate of top of FAQ box
    faq_top = cta_block_offset + bp_box_h + white_gap + faq_h

    # Content must end above: button renders at by = y - 0.05" - read_btn_h
    # so y_text_end > faq_top + read_btn_h + small safety margin
    bottom_y = faq_top + read_btn_h + 0.12 * inch

    # ── Content paragraphs fill top section ───────────────────────────────────
    y = H - 1.0 * inch - 0.50 * inch   # header band now flush to top

    def _render_p3_body(c, y, text, bottom_y, brand):
        """Render body text with sentence-boundary safety when truncating."""
        all_lines = _wrap_by_width(text, CONTENT_W, _font(brand.font_body), BODY_FONT_SZ)
        avail_ml  = max(3, int((y - bottom_y) / BODY_LEADING))
        render_n  = min(avail_ml, len(all_lines))

        # If all lines fit, use them all (no truncation)
        if render_n >= len(all_lines):
            rendered_text = ' '.join(all_lines)
        else:
            # Truncating - backtrack to last line ending a complete sentence
            sentence_found = False
            for i in range(render_n, 0, -1):
                if all_lines[i - 1].rstrip().endswith(('.', '!', '?')):
                    render_n = i
                    sentence_found = True
                    break

            # If no sentence boundary found, backtrack to word boundary (previous space)
            if not sentence_found and render_n > 1:
                render_n -= 1  # Remove last incomplete line

            rendered_text = ' '.join(all_lines[:render_n])
        return _draw_text_block(c, MARGIN, y, CONTENT_W, rendered_text,
                                _font(brand.font_body), BODY_FONT_SZ, BODY_LEADING,
                                _hex_to_color(brand.text_dark))

    for section in sections[:3]:
        hdr  = section.get("header", "")
        body = section.get("body", "")
        if y < bottom_y + 0.5 * inch:
            break
        if hdr:
            c.setFont(_font("OpenSans-Bold"), 12)
            c.setFillColor(_hex_to_color(brand.primary))
            c.drawString(MARGIN, y, hdr)
            y -= 0.32 * inch
        if body and y > bottom_y:
            y = _render_p3_body(c, y, body, bottom_y, brand)
            y -= 0.18 * inch

    if continuing_content:
        if y >= bottom_y + 0.5 * inch:
            y = _render_p3_body(c, y, continuing_content, bottom_y, brand)
            y -= 0.18 * inch

    # ── "Read the full article" button — close to content, above FAQ ────────
    if blog_url:
        label     = "READ THE FULL ARTICLE \u2192"
        btn_sz    = 10.5
        btn_pad_x = 0.15 * inch
        c.setFont(_font("OpenSans-Bold"), btn_sz)
        lw = c.stringWidth(label, _font("OpenSans-Bold"), btn_sz)
        bw = lw + btn_pad_x * 2
        bh = read_btn_h
        bx = MARGIN
        # Button sits tight below content; only a minimal safety gap above FAQ
        by = y - 0.05 * inch - bh
        by = max(by, faq_top + 0.05 * inch)   # emergency: don't overlap FAQ box

        c.setFillColor(_hex_to_color(brand.accent))
        c.setLineWidth(0)
        c.roundRect(bx, by, bw, bh, 3, stroke=0, fill=1)
        c.setFillColor(_hex_to_color(brand.text_light))
        c.drawString(bx + btn_pad_x, by + bh / 2 - btn_sz * 0.35, label)

        url = _ensure_protocol(blog_url)
        if url:
            c.linkURL(url, (bx, by, bx + bw, by + bh), relative=0)

    # ── FAQ shaded box ────────────────────────────────────────────────────────
    if stats_items:
        _draw_faq_shaded_box_at(c, stats_items, stats_type, brand, faq_top)

    # ── Boilerplate box ────────────────────────────────────────────────────────
    _draw_cta_block(c, "", boilerplate_body, cta_text, cta_url, brand)

    y = H - 1.0 * inch - 0.50 * inch  # reset — not used after this


def _extract_root_domain(url: str) -> str:
    """Extract root domain from URL for fallback brand home page."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        # Reconstruct root URL
        return f"{parsed.scheme}://{domain}" if parsed.scheme else f"https://{domain}"
    except Exception:
        return ""
