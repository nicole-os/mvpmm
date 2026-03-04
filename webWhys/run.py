#!/usr/bin/env python3
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

Website Competitor Scanner - Development Server
Run this script to start the webapp locally.
"""

import os
import sys

# Add the web-scanner directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Change to web-scanner directory for static file serving
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn

    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    print("\n" + "="*60)
    print("  webWhys — Website & Competitor Analysis")
    print("  SEO | GEO | LLM Discoverability")
    print("="*60)
    print("\n  Starting server at: http://localhost:8000")
    print("  Press Ctrl+C to stop\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."]
    )
