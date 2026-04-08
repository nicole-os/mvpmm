# briefly

**briefly** turns a company blog post into a branded, print-ready executive brief — a 2- or 3-page PDF formatted for sales enablement, investor updates, or content repurposing.

Paste a blog URL, upload your brand kit (logo, colors, messaging doc), and briefly scrapes the article, extracts the key points with GPT-4o, and generates a polished PDF in your brand.

---

## What it generates

**2-page brief**
- Page 1: header with logo, exec summary, 3 key takeaway cards, optional FAQ
- Page 2: deep-dive sections, read-more button, branded boilerplate block

**3-page brief**
- Page 1: header with logo, subtitle, exec summary
- Page 2: introduction, takeaway cards, 2 content sections
- Page 3: remaining sections, FAQ box, branded boilerplate block

Both templates support full custom branding: colors, fonts, logo, company name, website, and boilerplate copy. Save your brand config as JSON and reload it any time.

---

## Setup

**Requirements:** Python 3.10+, an OpenAI API key

```bash
git clone https://github.com/nicole-os/mvpmm.git
cd mvpmm/briefly

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then add your OpenAI key
python run.py
```

Open [http://localhost:8003](http://localhost:8003)

---

## Environment variables

```
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o        # optional, defaults to gpt-4o
```

You can use any model supported by [litellm](https://docs.litellm.ai) — Claude, Gemini, local Ollama, etc.

---

## How to use

1. Paste a blog post URL
2. Upload your company logo (PNG or JPG)
3. Optionally upload brand documents (PDF, DOCX, TXT) — messaging docs, pitch decks, one-pagers. briefly uses these to extract your boilerplate copy and CTA verbatim.
4. Set your brand colors and fonts
5. Choose 2-page or 3-page layout
6. Click **Generate Brief**

Use **Save Branding** to export your config as JSON. Load it next time to skip the setup.

A demo brand kit (Vela Analytics) is included in the `demo/` folder to try without your own assets.

---

## Features

- **Font-aware layout:** All text wrapping uses actual PDF font metrics — no character-count guessing. Long titles, unusual fonts, and edge-case content all lay out correctly.
- **Smart boilerplate extraction:** Finds your "About" paragraph in uploaded brand docs and copies it word-for-word into the PDF footer block. Falls back to LLM synthesis if no boilerplate is found.
- **Logo background detection:** Automatically detects whether your logo needs a dark or light background based on pixel brightness analysis. Override manually if needed.
- **Geometric header patterns:** 2-page briefs support solid, geometric, or surprise header texture overlays — deterministic per article so the same post always gets the same pattern.
- **Brand JSON save/load:** Full brand config (colors, fonts, logo path, company info) serializes to JSON for reuse.

---

## Stack

- **Backend:** Python, FastAPI, ReportLab, litellm, pypdf, python-docx, BeautifulSoup
- **Frontend:** Vanilla JS SPA, no build step
- **LLM:** OpenAI gpt-4o by default (configurable)
- **PDF:** ReportLab canvas — no LaTeX, no headless browser

---

## Part of the mvpmm toolkit

briefly is one tool in a set of open-source PMM utilities at [github.com/nicole-os/mvpmm](https://github.com/nicole-os/mvpmm). Each tool is standalone and runs locally.

---

*Built by Nicole Scott https://www.linkedin.com/in/nicolescottfromraleigh/*
