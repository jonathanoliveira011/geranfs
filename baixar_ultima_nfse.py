"""
Utilitário manual: abre a última NFS-e emitida e ajuda a baixar o PDF (DANFSe).

O download exige resolver um captcha visual (hCaptcha) toda vez - por isso este
script roda com o navegador visível (headless=false) e pausa para você resolver
o captcha manualmente antes de clicar em baixar.
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

DASHBOARD_URL = "https://www.nfse.gov.br/EmissorNacional/Dashboard"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        context = await browser.new_context(
            storage_state="data/govbr_session.json", accept_downloads=True
        )
        page = await context.new_page()

        await page.goto(DASHBOARD_URL)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1500)

        if "/Login" in page.url:
            print("Sessão expirada - reexporte os cookies (veja README) antes de continuar.")
            await browser.close()
            return

        primeiro_visualizar = page.locator('img[alt="Visualizar"]').first
        await primeiro_visualizar.click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1500)
        print("Nota aberta:", page.url)

        await page.locator("#btnDownloadDANFSE").click()
        print(">>> Resolva o captcha na janela do navegador e clique em Confirmar.")

        async with page.expect_download(timeout=120_000) as download_info:
            pass  # o download começa assim que o captcha for resolvido e confirmado
        download = await download_info.value
        pdf_path = Path("data") / download.suggested_filename
        await download.save_as(pdf_path)
        print("PDF baixado em:", pdf_path)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
