# briefly

Turn any blog post into a polished, print-ready PDF brief — in seconds.

Paste a URL, upload your brand kit, and briefly extracts the key takeaways, FAQs, and summary, then lays it out in a branded 2-page or 3-page PDF you can share immediately.

Built with FastAPI, ReportLab, and GPT-4o.

---

## Quickstart

```bash
git clone https://github.com/nicole-os/mvpmm
cd mvpmm/briefly
bash setup.sh
```

The setup script handles everything: pip dependencies, the Playwright browser binary, and a `.env` template. Open `.env` and add your OpenAI API key, then:

```bash
python3 run.py
```

Open `http://localhost:8003`.

---

## Manual setup (if you prefer)

### 1. Install dependencies
```bash
python3 -m pip install -r requirements.txt
```

### 2. Install Playwright browser ⚠️ required — separate from pip
```bash
python3 -m playwright install chromium
```
> `pip install` only installs the Python library. The browser binary is a separate download.
> Skipping this step will cause briefly to fail on JS-rendered pages.

### 3. Add your OpenAI API key
```
OPENAI_API_KEY=sk-...
```

### 4. Run
```bash
python3 run.py
```

---

## Features

- **Scrapes any blog URL** — handles static pages and JS-rendered sites (via Playwright)
- **LLM extraction** — GPT-4o pulls title, subtitle, summary, takeaways, and FAQs
- **Two templates** — 2-page (with pull quote) and 3-page (full layout)
- **Custom branding** — upload your logo, pick colors, load/save brand JSON
- **Clean PDF output** — ReportLab canvas, Poppins + Open Sans, press-ready

---

## Requirements

- Python 3.10+
- OpenAI API key (GPT-4o)
- Chromium (installed via `python3 -m playwright install chromium`)

---

## License

MIT — see LICENSE file.
