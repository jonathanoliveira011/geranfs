"""
Automação de emissão de NFS-e via nfse.gov.br/EmissorNacional usando Playwright.

Autenticação: NÃO faz login automatizado (o gov.br exige captcha de imagem que
bloqueia automação). Em vez disso, reutiliza uma sessão previamente exportada
via extensão de cookies do navegador (ver README) e salva em
`data/govbr_session.json`. Quando essa sessão expirar, é necessário repetir a
exportação manual dos cookies.

Fluxo mapeado manualmente em 22/08/2026 (4 abas): Pessoas -> Serviço -> Valores
-> Emitir NFS-e (revisão final).
"""

import asyncio
import datetime
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext, Page

from config import config

PRAZO_PAGAMENTO_DIAS = 15

PESSOAS_URL = "https://www.nfse.gov.br/EmissorNacional/DPS/Pessoas"


class SessaoExpiradaError(Exception):
    """A sessão salva não está mais autenticada - precisa reexportar os cookies."""


@dataclass
class EmissaoResultado:
    chave_acesso: str
    valor_total: float


DASHBOARD_URL = "https://www.nfse.gov.br/EmissorNacional/Dashboard"


async def sessao_esta_ativa() -> bool:
    """Visita o Dashboard para checar (e resetar o timeout de) a sessão salva.

    Usado como keep-alive periódico: o timeout de sessão do portal é por
    inatividade, então visitas regulares evitam a expiração por ociosidade
    (não elimina um eventual limite absoluto de sessão do servidor).
    """
    state_path = Path(config.browser_state_path)
    if not state_path.exists():
        return False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=config.playwright_headless, channel="chrome")
        context = await browser.new_context(storage_state=str(state_path))
        page = await context.new_page()

        await page.goto(DASHBOARD_URL)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)

        ativa = "/Login" not in page.url
        if ativa:
            await context.storage_state(path=str(state_path))

        await browser.close()
        return ativa


class NfseEmitter:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context: BrowserContext | None = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=config.playwright_headless, channel="chrome"
        )

        state_path = Path(config.browser_state_path)
        if not state_path.exists():
            raise SessaoExpiradaError(
                f"Nenhuma sessão salva em {state_path}. Exporte os cookies primeiro."
            )

        self._context = await self._browser.new_context(
            storage_state=str(state_path), reduced_motion="reduce"
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _dismiss_confirm_dialog(self, page: Page) -> None:
        btn = page.locator(".jconfirm-buttons button.btn-blue")
        if await btn.count() > 0 and await btn.first.is_visible():
            await btn.first.click()
            await page.wait_for_timeout(600)

    async def _select2_escolher(self, page: Page, select_id: str, termo_busca: str) -> None:
        await page.locator(f"#{select_id}").wait_for(state="attached", timeout=15000)
        container = (
            page.locator(f"#{select_id}")
            .locator("xpath=following-sibling::span[1]")
            .locator(".select2-selection")
        )
        await container.wait_for(state="visible", timeout=15000)
        await container.click()
        await page.wait_for_timeout(600)

        search = page.locator(".select2-search__field")
        await search.fill(termo_busca)
        await page.wait_for_timeout(1500)

        resultado = page.locator(".select2-results__option").first
        await resultado.wait_for(state="visible", timeout=8000)
        await resultado.click()

    async def _avancar(self, page: Page, url_contem: str) -> None:
        """Clica em Avançar e confirma que a URL realmente mudou, com uma nova tentativa
        caso a navegação não ocorra (ex: validação client-side ainda não concluída)."""
        for tentativa in range(3):
            await page.get_by_role("button", name="Avançar").click()
            try:
                await page.wait_for_url(f"**{url_contem}**", timeout=10000)
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1500)
                return
            except Exception:
                if tentativa < 2:
                    await page.wait_for_timeout(1500)
                    continue
                raise

    async def _chosen_escolher(self, page: Page, chosen_id: str, termo_busca: str) -> None:
        await page.locator(f"#{chosen_id}").click()
        await page.wait_for_timeout(600)
        search = page.locator(f"#{chosen_id} .chosen-search input")
        await search.press_sequentially(termo_busca, delay=80)
        await page.wait_for_timeout(1500)
        primeira_opcao = page.locator(f"#{chosen_id} .chosen-results li").first
        await primeira_opcao.click()

    async def _preencher_pessoas(self, page: Page) -> datetime.date:
        await page.goto(PESSOAS_URL)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1200)

        if "/Login" in page.url:
            raise SessaoExpiradaError(
                "Sessão expirada - reexporte os cookies do gov.br e rode convert_cookies.py"
            )

        # Interruptor mestre: sem ele o resto do formulário fica desabilitado
        await page.locator('input[name="PreencherInfoIBSCBS"][value="0"]').dispatch_event("click")
        await page.wait_for_timeout(700)
        await self._dismiss_confirm_dialog(page)

        data_competencia_str = await page.locator("#DataCompetencia").input_value()
        if not data_competencia_str:
            data_competencia = datetime.date.today()
            await page.locator("#DataCompetencia").fill(data_competencia.strftime("%d/%m/%Y"))
            await page.wait_for_timeout(700)
            await self._dismiss_confirm_dialog(page)
        else:
            data_competencia = datetime.datetime.strptime(
                data_competencia_str, "%d/%m/%Y"
            ).date()

        await page.locator('input[name="EhCompraGovernamental"][value="0"]').dispatch_event("click")
        await page.wait_for_timeout(700)
        await self._dismiss_confirm_dialog(page)

        # Município do prestador é fixo (único vínculo), mas só é preenchido depois de
        # clicar no widget (dispara a lógica JS que seleciona a única opção existente).
        for _tentativa_municipio in range(3):
            await page.locator("#Prestador_EnderecoNacional_CodigoMunicipio_chosen").click()
            try:
                await page.wait_for_function(
                    "document.querySelector('#Prestador_EnderecoNacional_CodigoMunicipio')?.value",
                    timeout=6000,
                )
                break
            except Exception:
                await self._dismiss_confirm_dialog(page)
                await page.wait_for_timeout(1000)
        else:
            raise RuntimeError("Município do prestador não foi preenchido após 3 tentativas")
        await self._dismiss_confirm_dialog(page)

        await page.locator("#Tomador_Inscricao").fill(config.tomador_cnpj)
        await page.locator("#Tomador_Inscricao").press("Tab")

        # aguarda a busca AJAX do CNPJ preencher o nome (não usar espera fixa - servidor
        # mais lento pode demorar mais que o esperado e deixar o Avançar sem efeito)
        await page.wait_for_function(
            "document.querySelector('#Tomador_Nome')?.value?.trim().length > 0",
            timeout=15000,
        )
        await self._dismiss_confirm_dialog(page)

        # reforça (pode resetar após o confirm dialog acima)
        await page.locator('input[name="EhCompraGovernamental"][value="0"]').dispatch_event("click")
        await page.wait_for_timeout(500)
        await self._dismiss_confirm_dialog(page)

        await self._avancar(page, "/DPS/Servico")

        return data_competencia

    async def _preencher_servico(self, page: Page, data_competencia: datetime.date) -> None:
        await self._select2_escolher(page, "LocalPrestacao_CodigoMunicipioPrestacao", "Atibaia")
        await page.wait_for_timeout(1000)

        await self._select2_escolher(
            page, "ServicoPrestado_CodigoTributacaoNacional", config.codigo_tributacao_nacional
        )
        await page.wait_for_timeout(1000)

        await page.locator(
            'input[name="ServicoPrestado.HaExportacaoImunidadeNaoIncidencia"][value="0"]'
        ).dispatch_event("click")
        await page.wait_for_timeout(500)
        await self._dismiss_confirm_dialog(page)
        await page.wait_for_timeout(1500)  # overlay "Por favor, aguarde..."

        await self._chosen_escolher(page, "ServicoPrestado_CodigoNBS_chosen", "120015000")
        await page.wait_for_timeout(800)

        await page.locator("#ServicoPrestado_Descricao").fill(config.descricao_servico)
        await page.wait_for_timeout(500)

        vencimento = data_competencia + datetime.timedelta(days=PRAZO_PAGAMENTO_DIAS)
        info_complementares = (
            f"Condições de pagamento -{PRAZO_PAGAMENTO_DIAS}DDL | "
            f"Vencimento {vencimento.strftime('%d/%m/%Y')}"
        )
        await page.locator("#Complemento_InformacoesComplementares").fill(info_complementares)
        await page.wait_for_timeout(500)

        await self._avancar(page, "/DPS/Tributacao")

    async def _preencher_valores(self, page: Page, valor_total: float) -> None:
        valor_formatado = f"{valor_total:.2f}".replace(".", ",")
        await page.locator("#Valores_ValorServico").fill(valor_formatado)
        await page.locator("#Valores_ValorServico").press("Tab")
        await page.wait_for_timeout(1500)
        await self._dismiss_confirm_dialog(page)

        await self._avancar(page, "/DPS/EmitirNFSe")

    async def emitir(self, quantidade: int) -> EmissaoResultado:
        valor_total = round(quantidade * config.valor_unitario, 2)

        page = await self._context.new_page()

        eventos_debug: list[str] = []

        async def _on_dialog(dialog):
            eventos_debug.append(f"DIALOG: {dialog.type} - {dialog.message}")
            await dialog.accept()

        page.on("dialog", lambda d: asyncio.ensure_future(_on_dialog(d)))
        page.on("console", lambda m: eventos_debug.append(f"CONSOLE[{m.type}]: {m.text}"))
        page.on("pageerror", lambda e: eventos_debug.append(f"PAGEERROR: {e}"))
        page.on(
            "requestfailed",
            lambda r: eventos_debug.append(f"REQFAILED: {r.url} - {r.failure}"),
        )
        page.on(
            "response",
            lambda r: eventos_debug.append(f"RESPONSE: {r.status} {r.url}")
            if r.request.method == "POST" or r.status >= 400
            else None,
        )

        try:
            data_competencia = await self._preencher_pessoas(page)
            await self._preencher_servico(page, data_competencia)
            await self._preencher_valores(page, valor_total)

            # Tela final de revisão: o botão "Emitir NFS-e" é um <a id="btnProsseguir">
            await page.locator("#btnProsseguir").click()
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)

            chave_acesso = await page.locator(
                "text=Chave de Acesso:"
            ).locator("xpath=following::*[1]").inner_text()
        except Exception:
            debug_dir = Path(config.browser_state_path).parent / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            await page.screenshot(path=str(debug_dir / f"erro_{timestamp}.png"), full_page=True)
            (debug_dir / f"erro_{timestamp}.html").write_text(
                await page.content(), encoding="utf-8"
            )
            (debug_dir / f"erro_{timestamp}.txt").write_text(page.url, encoding="utf-8")
            (debug_dir / f"erro_{timestamp}_eventos.log").write_text(
                "\n".join(eventos_debug), encoding="utf-8"
            )
            raise

        return EmissaoResultado(chave_acesso=chave_acesso.strip(), valor_total=valor_total)
