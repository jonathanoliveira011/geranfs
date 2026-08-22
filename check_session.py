import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

DASHBOARD_URL = "https://www.nfse.gov.br/EmissorNacional/Dashboard"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        context = await browser.new_context(storage_state="data/govbr_session.json")
        page = await context.new_page()

        await page.goto(DASHBOARD_URL)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        Path("data/test_shots").mkdir(parents=True, exist_ok=True)
        await page.screenshot(path="data/test_shots/session_cookie_check.png", full_page=True)

        print("URL final:", page.url)
        print("AUTENTICADO" if "/Login" not in page.url else "NAO AUTENTICADO (sessão expirada)")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
