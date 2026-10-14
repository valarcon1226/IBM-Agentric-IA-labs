"""Asynchronous crawler respecting robots.txt, domain scope, and rate limits."""

import asyncio
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.checks.seo_page import extract_internal_links
from app.config import DEFAULT_CONFIG, AuditConfig
from app.validators import is_local_hostname, is_private_or_loopback_ip, validate_url


class SiteCrawler:
    """Polite same-domain web crawler."""

    def __init__(self, config: AuditConfig = DEFAULT_CONFIG, allow_local: bool = False):
        self.config = config
        self.allow_local = allow_local
        self.robot_parser: RobotFileParser | None = None
        self.robots_content: str | None = None
        self.robots_status: int = 404
        self.sitemap_content: str | None = None
        self.sitemap_status: int = 404
        self.llms_content: str | None = None
        self.llms_status: int = 404

    async def _init_robots(self, client: httpx.AsyncClient, base_url: str) -> None:
        """Fetch and parse robots.txt for the given domain."""
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        try:
            resp = await client.get(robots_url, timeout=self.config.request_timeout)
            self.robots_status = resp.status_code
            if resp.status_code == 200:
                self.robots_content = resp.text
                parser = RobotFileParser()
                parser.parse(resp.text.splitlines())
                self.robot_parser = parser
        except Exception:
            self.robots_status = 0
            self.robot_parser = None

    async def _fetch_auxiliary_files(self, client: httpx.AsyncClient, base_url: str) -> None:
        """Fetch sitemap.xml and llms.txt."""
        parsed = urlparse(base_url)
        root = f"{parsed.scheme}://{parsed.netloc}"

        # 1. sitemap.xml
        try:
            s_resp = await client.get(f"{root}/sitemap.xml", timeout=self.config.request_timeout)
            self.sitemap_status = s_resp.status_code
            if s_resp.status_code == 200:
                self.sitemap_content = s_resp.text
        except Exception:
            self.sitemap_status = 0

        # 2. llms.txt
        try:
            l_resp = await client.get(f"{root}/llms.txt", timeout=self.config.request_timeout)
            self.llms_status = l_resp.status_code
            if l_resp.status_code == 200:
                self.llms_content = l_resp.text
            else:
                # Fallback to /.well-known/llms.txt
                l_resp2 = await client.get(f"{root}/.well-known/llms.txt", timeout=self.config.request_timeout)
                self.llms_status = l_resp2.status_code
                if l_resp2.status_code == 200:
                    self.llms_content = l_resp2.text
        except Exception:
            self.llms_status = 0

    async def _check_image_sizes(
        self, client: httpx.AsyncClient, base_url: str, html: str
    ) -> dict[str, int]:
        """Check image sizes via HEAD requests."""
        soup = BeautifulSoup(html, "html.parser")
        sizes: dict[str, int] = {}

        tasks = []
        image_urls = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if not src or src.startswith("data:"):
                continue
            abs_url = urljoin(base_url, src)
            if abs_url not in image_urls:
                image_urls.append(abs_url)

        async def fetch_head(img_url: str):
            try:
                r = await client.head(img_url, timeout=5.0)
                cl = r.headers.get("content-length")
                if cl and cl.isdigit():
                    return img_url, int(cl)
                # If HEAD didn't return content-length or was 405, do lightweight stream GET
                if r.status_code >= 400 or not cl:
                    r_get = await client.get(img_url, timeout=5.0)
                    return img_url, len(r_get.content)
            except Exception:
                pass
            return img_url, 0

        for u in image_urls[:15]:  # limit to top 15 images to be polite and fast
            tasks.append(fetch_head(u))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, tuple):
                    sizes[res[0]] = res[1]

        return sizes

    async def _check_broken_links(
        self, client: httpx.AsyncClient, links: list[str]
    ) -> list[str]:
        """Verify internal links to detect 404 or broken responses."""
        broken: list[str] = []

        async def check_url(target: str):
            try:
                r = await client.get(target, timeout=self.config.request_timeout)
                if r.status_code >= 400:
                    return target
            except Exception:
                return target
            return None

        # Check unique links up to 20
        unique_links = list(set(links))[:20]
        if not unique_links:
            return []

        results = await asyncio.gather(*(check_url(u) for u in unique_links), return_exceptions=True)
        for res in results:
            if isinstance(res, str):
                broken.append(res)

        return broken

    async def crawl(self, start_url: str, max_pages: int = DEFAULT_CONFIG.default_max_pages) -> dict:
        """
        Execute domain-bounded crawl starting from start_url.
        """
        validated_url = validate_url(start_url, allow_local=self.allow_local)
        parsed_start = urlparse(validated_url)
        target_host = (parsed_start.netloc or "").lower()

        is_local = (
            is_local_hostname(parsed_start.hostname or "")
            or is_private_or_loopback_ip(parsed_start.hostname or "")
        )

        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es,en;q=0.9",
        }

        pages_data = []
        visited = set()
        queue = [validated_url]
        max_pages = min(max_pages, self.config.max_crawl_pages_limit)

        async with httpx.AsyncClient(headers=headers, follow_redirects=True, verify=False) as client:
            # 1. Fetch robots.txt, sitemap.xml, llms.txt
            await self._init_robots(client, validated_url)
            await self._fetch_auxiliary_files(client, validated_url)

            # 2. Crawl loop
            while queue and len(pages_data) < max_pages:
                curr_url = queue.pop(0)

                # Normalize without fragment
                p = urlparse(curr_url)
                norm_url = f"{p.scheme}://{p.netloc}{p.path}"
                if p.query:
                    norm_url += f"?{p.query}"

                if norm_url in visited:
                    continue
                visited.add(norm_url)

                # Check robots.txt permission
                if self.robot_parser and not self.robot_parser.can_fetch(self.config.user_agent, norm_url):
                    continue

                # Polite delay between requests
                if pages_data:
                    await asyncio.sleep(self.config.crawl_delay_seconds)

                t0 = time.perf_counter()
                try:
                    resp = await client.get(norm_url, timeout=self.config.request_timeout)
                    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

                    content_type = resp.headers.get("content-type", "").lower()
                    if "text/html" not in content_type and not norm_url.endswith((".html", "/")):
                        continue

                    html_text = resp.text

                    # Extract internal links for queue
                    extracted_links = extract_internal_links(norm_url, html_text)
                    for lk in extracted_links:
                        p_lk = urlparse(lk)
                        if (p_lk.netloc or "").lower() == target_host and lk not in visited and lk not in queue:
                            queue.append(lk)

                    # Inspect images and broken links
                    image_sizes = await self._check_image_sizes(client, norm_url, html_text)
                    broken_links = await self._check_broken_links(client, extracted_links)

                    pages_data.append({
                        "url": norm_url,
                        "status_code": resp.status_code,
                        "html": html_text,
                        "response_time_ms": elapsed_ms,
                        "headers": dict(resp.headers),
                        "image_sizes": image_sizes,
                        "broken_links": broken_links,
                    })

                except Exception as exc:
                    pages_data.append({
                        "url": norm_url,
                        "status_code": 0,
                        "html": "",
                        "response_time_ms": 0,
                        "headers": {},
                        "image_sizes": {},
                        "broken_links": [],
                        "error": str(exc),
                    })

        return {
            "base_url": validated_url,
            "target_host": target_host,
            "is_local": is_local,
            "is_https": parsed_start.scheme == "https",
            "pages": pages_data,
            "sitemap_response": (self.sitemap_status, self.sitemap_content or ""),
            "robots_response": (self.robots_status, self.robots_content or ""),
            "llms_response": (self.llms_status, self.llms_content or ""),
        }
