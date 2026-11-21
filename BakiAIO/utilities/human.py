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

    async def pause(self, lo: float = 2.0, hi: float = 9.0) -> None:
        await asyncio.sleep(self.rng.uniform(lo, hi))

    async def move_to(self, page, x: float, y: float) -> None:
        try:
            pos = await page.mouse.position() or (0, 0)
            dx, dy = x - pos[0], y - pos[1]
            ox = x + dx * self.rng.uniform(0.04, 0.12) if abs(dx) > 40 else x
            oy = y + dy * self.rng.uniform(0.04, 0.12) if abs(dy) > 40 else y
            steps = self.rng.randint(10, 26)
            for i in range(steps + 1):
                t = i / steps
                ease = t * t * (3 - 2 * t)
                cx = pos[0] + (ox - pos[0]) * ease + self.rng.uniform(-2, 2)
                cy = pos[1] + (oy - pos[1]) * ease + self.rng.uniform(-2, 2)
                await page.mouse.move(cx, cy)
                await asyncio.sleep(self._delay(8, 26))
            await asyncio.sleep(self._delay(60, 220))
            await page.mouse.move(x + self.rng.uniform(-3, 3),
                                  y + self.rng.uniform(-3, 3), steps=3)
        except Exception:
            pass

    async def wander(self, page) -> None:
        try:
            vp = page.viewport_size or {"width": 1366, "height": 768}
            for _ in range(self.rng.randint(2, 4)):
                x = self.rng.uniform(vp["width"] * 0.1, vp["width"] * 0.9)
                y = self.rng.uniform(vp["height"] * 0.12, vp["height"] * 0.88)
                await self.move_to(page, x, y)
                await asyncio.sleep(self._delay(200, 900))
        except Exception:
            pass

    async def click(self, page, loc) -> bool:
        try:
            box = await loc.bounding_box(timeout=3000)
            if not box or not box.get("width") or not box.get("height"):
                return False
            x = box["x"] + box["width"] * self.rng.uniform(0.3, 0.7)
            y = box["y"] + box["height"] * self.rng.uniform(0.3, 0.7)
            await self.wander(page)
            await self.move_to(page, x, y)
            await asyncio.sleep(self._delay(120, 480))
            await loc.hover(timeout=3000)
            await loc.click(timeout=10000)
            return True
        except Exception:
            return False

    async def type_slow(self, page, loc, text: str) -> None:
        try:
            await self.click(page, loc)
            await page.keyboard.press("ControlOrMeta+A")
            await page.keyboard.press("Backspace")
            for i, ch in enumerate(text):
                if self.rng.random() < 0.035:
                    wrong = self.rng.choice("abcdefghijklmnopqrstuvwxyz")
                    await page.keyboard.type(wrong, delay=self.rng.randint(70, 220))
                    await asyncio.sleep(self._delay(90, 260))
                    await page.keyboard.press("Backspace")
                    await asyncio.sleep(self._delay(80, 240))
                await page.keyboard.type(ch, delay=self.rng.randint(70, 220))
                if i and i % self.rng.randint(7, 10) == 0:
                    await asyncio.sleep(self.rng.uniform(0.4, 1.2))
        except Exception:
            pass

    async def scroll_bursts(self, page, count: int = 4) -> None:
        direction = 1
        for _ in range(count):
            pixels = self.rng.randint(180, 620)
            for _ in range(max(1, pixels // 45)):
                await page.mouse.wheel(0, direction * 45)
                await asyncio.sleep(self._delay(18, 70))
            await asyncio.sleep(self.rng.uniform(0.6, 2.4))
            direction = -direction if self.rng.random() < 0.45 else direction