FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# O emissor usa channel="chrome" (Chrome real) em vez do Chromium padrão,
# para reduzir sinais de automação detectados pelo nfse.gov.br.
RUN playwright install --with-deps chrome

COPY . .

RUN mkdir -p /app/data

CMD ["python", "main.py"]
