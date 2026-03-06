"""
Playwright Browser Manager - Singleton Instance & Context Pooling
Manages a shared browser instance with lazy initialization, context pooling,
and graceful error handling for JavaScript-heavy site rendering.
"""

import asyncio
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext

class PlaywrightBrowserManager:
    """Singleton pattern for shared Playwright browser instance with context pooling."""

    _browser: Optional[Browser] = None
    _playwright = None
    _lock = asyncio.Lock()
    _context_pool: list[BrowserContext] = []
    _max_pool_size = 5
    _browser_retry_count = 0
    _browser_max_retries = 2

    @staticmethod
    async def get_browser() -> Browser:
        """
        Get or initialize the shared browser instance (lazy initialization).
        Returns the singleton browser instance.
        """
        if PlaywrightBrowserManager._browser is None:
            async with PlaywrightBrowserManager._lock:
                # Double-check pattern to avoid race conditions
                if PlaywrightBrowserManager._browser is None:
                    try:
                        PlaywrightBrowserManager._playwright = await async_playwright().start()
                        PlaywrightBrowserManager._browser = await PlaywrightBrowserManager._playwright.chromium.launch(
                            args=["--disable-blink-features=AutomationControlled"],  # Stealth mode
                            headless=True
                        )
                        print("[BrowserManager] ✅ Playwright browser initialized (lazy start)")
                    except Exception as e:
                        print(f"[BrowserManager] ❌ Failed to initialize browser: {str(e)}")
                        raise

        return PlaywrightBrowserManager._browser

    @staticmethod
    async def _get_or_create_context() -> BrowserContext:
        """
        Get an existing context from the pool or create a new one.
        Each context is isolated (no shared cookies/state).
        """
        # Reuse existing context if available
        if PlaywrightBrowserManager._context_pool:
            context = PlaywrightBrowserManager._context_pool.pop()
            return context

        # Create new context
        browser = await PlaywrightBrowserManager.get_browser()
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"latitude": 40.7128, "longitude": -74.0060},  # NYC as default
            permissions=[]  # No geolocation permission
        )
        return context

    @staticmethod
    async def _return_context_to_pool(context: BrowserContext):
        """Return a context to the pool for reuse."""
        if len(PlaywrightBrowserManager._context_pool) < PlaywrightBrowserManager._max_pool_size:
            try:
                # Clear cookies and storage for clean reuse
                await context.clear_cookies()
                await context.add_init_script("window.localStorage.clear(); window.sessionStorage.clear();")
                PlaywrightBrowserManager._context_pool.append(context)
            except Exception as e:
                # If cleanup fails, just close the context
                try:
                    await context.close()
                except:
                    pass
        else:
            # Pool is full, close the context
            try:
                await context.close()
            except:
                pass

    @staticmethod
    async def render_page(url: str, timeout: int = 10) -> Tuple[str, dict]:
        """
        Render a JavaScript-heavy page and return the rendered HTML + metadata.

        Args:
            url: URL to render
            timeout: Timeout in seconds for page load (default: 10s)

        Returns:
            Tuple of (html_string, metadata_dict)
            Returns ("", {}) on timeout or error (graceful fallback)
        """
        context = None
        try:
            # Get or create a browser context
            context = await PlaywrightBrowserManager._get_or_create_context()
            page = await context.new_page()

            try:
                # Navigate to URL with timeout
                await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)

                # Get rendered HTML
                html = await page.content()

                # Collect metadata
                metadata = {
                    "rendered_at": True,
                    "url": url,
                    "title": await page.title(),
                }

                await page.close()
                return html, metadata

            except asyncio.TimeoutError:
                await page.close()
                print(f"[BrowserManager] ⚠️ Timeout rendering {url} (>{timeout}s)")
                return "", {"error": "timeout", "url": url}
            except Exception as e:
                await page.close()
                print(f"[BrowserManager] ⚠️ Error rendering page {url}: {str(e)}")
                return "", {"error": str(e), "url": url}

        except Exception as e:
            print(f"[BrowserManager] ❌ Critical error in render_page: {str(e)}")
            # Browser might have crashed - reset it for retry
            await PlaywrightBrowserManager._reset_browser()
            return "", {"error": f"critical: {str(e)}", "url": url}

        finally:
            # Return context to pool for reuse
            if context:
                await PlaywrightBrowserManager._return_context_to_pool(context)

    @staticmethod
    async def _reset_browser():
        """Reset the browser instance (on crash or critical error)."""
        PlaywrightBrowserManager._browser_retry_count += 1

        if PlaywrightBrowserManager._browser_retry_count > PlaywrightBrowserManager._browser_max_retries:
            print("[BrowserManager] ❌ Browser max retries exceeded, not restarting")
            return

        print(f"[BrowserManager] ⚠️ Resetting browser (attempt {PlaywrightBrowserManager._browser_retry_count})")

        async with PlaywrightBrowserManager._lock:
            # Close all contexts
            for ctx in PlaywrightBrowserManager._context_pool:
                try:
                    await ctx.close()
                except:
                    pass
            PlaywrightBrowserManager._context_pool.clear()

            # Close browser
            if PlaywrightBrowserManager._browser:
                try:
                    await PlaywrightBrowserManager._browser.close()
                except:
                    pass

            # Close playwright
            if PlaywrightBrowserManager._playwright:
                try:
                    await PlaywrightBrowserManager._playwright.stop()
                except:
                    pass

            # Reset for next initialization
            PlaywrightBrowserManager._browser = None
            PlaywrightBrowserManager._playwright = None

    @staticmethod
    async def shutdown():
        """
        Graceful shutdown - close all contexts and browser instance.
        Call this on application shutdown.
        """
        print("[BrowserManager] Shutting down Playwright browser...")

        async with PlaywrightBrowserManager._lock:
            # Close all contexts in pool
            for context in PlaywrightBrowserManager._context_pool:
                try:
                    await context.close()
                    print("[BrowserManager] ✅ Closed context")
                except Exception as e:
                    print(f"[BrowserManager] ⚠️ Error closing context: {str(e)}")

            PlaywrightBrowserManager._context_pool.clear()

            # Close browser
            if PlaywrightBrowserManager._browser:
                try:
                    await PlaywrightBrowserManager._browser.close()
                    print("[BrowserManager] ✅ Closed browser")
                except Exception as e:
                    print(f"[BrowserManager] ⚠️ Error closing browser: {str(e)}")

            # Stop playwright
            if PlaywrightBrowserManager._playwright:
                try:
                    await PlaywrightBrowserManager._playwright.stop()
                    print("[BrowserManager] ✅ Stopped Playwright")
                except Exception as e:
                    print(f"[BrowserManager] ⚠️ Error stopping Playwright: {str(e)}")

            # Reset
            PlaywrightBrowserManager._browser = None
            PlaywrightBrowserManager._playwright = None
            PlaywrightBrowserManager._browser_retry_count = 0

        print("[BrowserManager] ✅ Shutdown complete")
