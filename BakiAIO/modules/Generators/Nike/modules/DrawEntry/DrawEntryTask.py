#!/usr/bin/env python3
"""Nike Draw-Entry Task: fuehrt einen Draw-Entry je Konto aus."""
from __future__ import annotations

import asyncio

from modules.base import BaseTask
from modules.Generators.Nike.modules.DrawEntry.DrawEntryModule import DrawEntry


class DrawEntryTask(BaseTask):
    def __init__(self, run_feature, email: str = "", password: str = "",
                 url: str = "", size: str = "", wait_until: str = "",
                 headless: bool = True, **kw):
        super().__init__(**kw)
        self.run_feature = run_feature
        self.email, self.password = email, password
        self.url, self.size, self.wait_until = url, size, wait_until
        self.headless = headless

    async def startRequest(self, cfg):
        self.feature = DrawEntry(self.url, size=self.size, wait_until=self.wait_until,
                                 headless=self.headless)
        return self.feature

    async def runTask(self, cfg) -> dict:
        f = self.feature or await self.startRequest(cfg)
        return await f.run(self.email, self.password)