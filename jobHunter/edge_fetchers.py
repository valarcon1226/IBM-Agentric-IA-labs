"""Scrapling's browser fetchers, defaulted to Microsoft Edge instead of Playwright's Chromium.

Import from here, never from scrapling.fetchers (that one launches Chromium):
    from edge_fetchers import DynamicFetcher, StealthyFetcher, DynamicSession
"""
import os
from pathlib import Path

from scrapling import fetchers as _f
from scrapling.fetchers import AsyncFetcher, Fetcher, FetcherSession  # noqa: F401  (plain HTTP, no browser)

EDGE = next(
    (p for p in [
        os.environ.get("SCRAPLING_EXECUTABLE_PATH"),  # same variable Scrapling's CLI and MCP server read
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/microsoft-edge",
    ] if p and Path(p).is_file()),
    None,
)
if not EDGE:
    raise RuntimeError("No encontré msedge.exe; define SCRAPLING_EXECUTABLE_PATH con su ruta.")


def _edge(kw):
    # real_chrome would switch to Google Chrome; Edge only here
    return {**kw, "executable_path": kw.get("executable_path") or EDGE, "real_chrome": False}


class DynamicFetcher(_f.DynamicFetcher):
    @classmethod
    def fetch(cls, url, **kw):
        return super().fetch(url, **_edge(kw))

    @classmethod
    async def async_fetch(cls, url, **kw):
        return await super().async_fetch(url, **_edge(kw))


class StealthyFetcher(_f.StealthyFetcher):
    @classmethod
    def fetch(cls, url, **kw):
        return super().fetch(url, **_edge(kw))

    @classmethod
    async def async_fetch(cls, url, **kw):
        return await super().async_fetch(url, **_edge(kw))


class DynamicSession(_f.DynamicSession):
    def __init__(self, **kw):
        super().__init__(**_edge(kw))


class AsyncDynamicSession(_f.AsyncDynamicSession):
    def __init__(self, **kw):
        super().__init__(**_edge(kw))


class StealthySession(_f.StealthySession):
    def __init__(self, **kw):
        super().__init__(**_edge(kw))


class AsyncStealthySession(_f.AsyncStealthySession):
    def __init__(self, **kw):
        super().__init__(**_edge(kw))


if __name__ == "__main__":  # self-check: py -m edge_fetchers
    import asyncio

    url, seen = "https://quotes.toscrape.com/js/", []

    def brands(page):
        seen.append(page.evaluate("navigator.userAgentData.brands.map(b => b.brand)"))

    async def abrands(page):
        seen.append(await page.evaluate("navigator.userAgentData.brands.map(b => b.brand)"))

    def check(name, page):
        assert page.status == 200 and len(page.css(".quote")) == 10, name
        assert "Microsoft Edge" in seen[-1], f"{name} lanzó {seen[-1]}"
        print("OK", name, seen[-1])

    check("DynamicFetcher", DynamicFetcher.fetch(url, page_action=brands))
    check("StealthyFetcher", StealthyFetcher.fetch(url, page_action=brands, real_chrome=True))
    with DynamicSession() as s:
        check("DynamicSession", s.fetch(url, page_action=brands))
    with StealthySession() as s:
        check("StealthySession", s.fetch(url, page_action=brands))

    async def async_checks():
        check("DynamicFetcher.async_fetch", await DynamicFetcher.async_fetch(url, page_action=abrands))
        async with AsyncStealthySession() as s:
            check("AsyncStealthySession", await s.fetch(url, page_action=abrands))

    asyncio.run(async_checks())
