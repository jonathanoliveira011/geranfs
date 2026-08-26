# GeraNfs

Bot de Telegram para emissão de NFS-e (portal NFS-e Nacional, gov.br) a partir da quantidade de peças produzidas.

## Como funciona

1. No grupo do Telegram, `/nota` → o bot pergunta a quantidade de peças.
2. Bot mostra um resumo (quantidade × valor unitário fixo = total) com botões Confirmar/Cancelar.
3. Ao confirmar, o Playwright abre o portal nfse.gov.br já autenticado (sessão reaproveitada, ver abaixo) e preenche o formulário de emissão completa: prestador (fixo), tomador (fixo), serviço (fixo), valor calculado.
4. Bot responde com a chave de acesso da NFS-e emitida e registra no histórico local (`data/historico.csv`). O PDF **não** é anexado automaticamente (ver limitações).

## Comandos

- `/nota` — inicia a emissão (pergunta quantidade → confirma → emite)
- `/status` — checa se a sessão do gov.br está ativa e mostra as últimas 3 notas emitidas
- `/cancelar` — cancela um fluxo de `/nota` em andamento
- `/chatid` — mostra o ID do chat atual (útil para configurar `TELEGRAM_GROUP_CHAT_ID`)

## Limitações importantes (por quê o fluxo não é 100% automático)

- **Login no gov.br exige captcha de imagem.** Não dá pra automatizar do zero a cada emissão. Solução: a sessão é autenticada manualmente de vez em quando (exportando cookies do Chrome já logado) e reaproveitada pelo bot enquanto durar.
- **Baixar o PDF (DANFSe) exige outro captcha (hCaptcha).** Por isso o bot não anexa o PDF no Telegram — só informa a chave de acesso. Para baixar o PDF, use `baixar_ultima_nfse.py` manualmente (abre navegador visível, você resolve o captcha).

## Renovando a sessão (quando o bot disser "sessão expirada")

1. Abra o Chrome no perfil correto (o que tem login no gov.br/nfse.gov.br), instale a extensão **Cookie-Editor**.
2. Acesse nfse.gov.br e confirme que está logado (Dashboard, não a tela de login). Se caiu, faça login normal (vai pedir captcha).
3. Clique no ícone do Cookie-Editor → **Export** → **Export as JSON**.
4. Cole o conteúdo em `cookies.json` na raiz do projeto.
5. Rode `python convert_cookies.py` — isso gera `data/govbr_session.json`, usado pelo bot.

## Rodando localmente

```
cp .env.example .env   # preencher com os dados reais
pip install -r requirements.txt
playwright install chrome
python main.py
```

Para testar a automação sem o Telegram (ex: depurar o preenchimento do formulário), use `check_session.py` para validar a sessão.

## Configuração (`.env`)

| Variável | Descrição |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token do bot, via @BotFather |
| `TELEGRAM_ALLOWED_USER_IDS` | IDs do Telegram autorizados a emitir (separados por vírgula) |
| `PRESTADOR_CNPJ` / `TOMADOR_CNPJ` | CNPJs fixos usados em toda emissão |
| `VALOR_UNITARIO` | Valor por peça, usado para calcular o total |
| `PLAYWRIGHT_HEADLESS` | `true` em produção; `false` só para depuração visual |
| `BROWSER_STATE_PATH` | Onde fica a sessão exportada (`data/govbr_session.json`) |

## Proteção contra múltiplas instâncias

O bot recusa iniciar se já existir outra instância com heartbeat recente (arquivo
`data/bot.lock`, atualizado a cada 45s, considerado "vivo" por até 90s). Isso evita o
erro `Conflict: terminated by other getUpdates request` que acontece quando um deploy
deixa o container antigo rodando junto com o novo. Se o bot se recusar a iniciar após
um deploy e você tiver certeza de que não há outra instância rodando, apague
`data/bot.lock` manualmente pelo terminal do serviço.

## Deploy no EasyPanel

O `Dockerfile` já inclui o Chrome real (não o Chromium padrão do Playwright) e todas as dependências. Configure as variáveis de ambiente do `.env` no painel do EasyPanel e monte um volume persistente para `/app/data` (guarda a sessão exportada).

**Atenção**: como a sessão expira periodicamente, alguém (você) vai precisar repetir o processo de "Renovando a sessão" de tempos em tempos — não tem como fugir disso sem um certificado digital A1 (ver conversa original sobre alternativas).
