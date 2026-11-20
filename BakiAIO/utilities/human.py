"""Human-Engine: natuerlich wirkende Eingaben und Maus-/Scroll-Bewegungen."""
from __future__ import annotations

import asyncio
import random


class Human:
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    @staticmethod
    def _delay(lo: int, hi: int) -> float:
        return random.uniform(lo, hi) / 1000.0

    async def type_text(self, page, selector: str, text: str,
                        lo_ms: int = 60, hi_ms: int = 180) -> None:
        """Schreibt Text Zeichen fuer Zeichen mit menschlichem Jitter."""
        loc = page.locator(selector).first
        await loc.click(timeout=8000)
        for ch in text:
            await loc.press_sequentially(ch, delay=random.uniform(lo_ms, hi_ms))

    async def move_mouse(self, page, steps: int = 6) -> None:
        """Bewegt die Maus in kleinen, leicht unregelmaessigen Schritten."""
        try:
            box = await page.mouse.position()
            x, y = box or (0, 0)
            for _ in range(steps):
                x += self.rng.randint(-90, 90)
                y += self.rng.randint(-60, 60)
                await page.mouse.move(x, y)
                await asyncio.sleep(self._delay(15, 60))
        except Exception:
            pass

    async def scroll(self, page, amount: int | None = None) -> None:
        """Scrollt mit Pausen; amount in Pixeln (Default: zufaellig)."""
        a = amount if amount is not None else self.rng.randint(-400, 400)
        steps = max(1, abs(a) // 40)
        for _ in range(steps):
            await page.mouse.wheel(0, 40 if a > 0 else -40)
            await asyncio.sleep(self._delay(20, 80))