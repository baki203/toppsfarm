"""Browser-Engine: persistenter Chromium-Context mit Fingerprint und Human-Tools."""
from __future__ import annotations

import asyncio

from playwright.async_api import async_playwright

from core.fingerprint import apply as apply_fingerprint
from core.human import Human

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

_STORAGE = "var/browser"


class Browser:
    def __init__(self, user_data_dir: str = _STORAGE, headless: bool = True,
                 seed: int | None = None):
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.seed = seed if seed is not None else 1337
        self.pw = self.browser = None
        self.human = Human(seed)

    async def start(self):
        if self.browser:
            return
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch_persistent_context(
            self.user_data_dir, headless=self.headless,
            user_agent=UA, locale="de-DE", timezone_id="Europe/Berlin",
            viewport={"width": 1366, "height": 768},
            args=["--disable-blink-features=AutomationControlled",
                  "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"])
        await apply_fingerprint(self.browser, self.seed)

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.pw:
            await self.pw.stop()
        self.browser = self.pw = None

    async def new_page(self):
        await self.start()
        return await self.browser.new_page()

    @property
    def ready(self) -> bool:
        return self.browser is not None

    def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.stop()


async def new_context(profile: dict | None = None) -> Browser:
    """Kurzform: liefert einen gestarteten Browser (persistenter Kontext).
    `profile` kann {'headless': bool, 'seed': int} tragen."""
    p = profile or {}
    b = Browser(headless=bool(p.get("headless", True)),
                seed=p.get("seed", 1337),
                user_data_dir=p.get("user_data_dir", _STORAGE))
    await b.start()
    return b