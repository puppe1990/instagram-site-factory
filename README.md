# Instagram Site Factory

Pipeline para gerar demos de sites de negócios locais a partir do Instagram.

**Fluxo:** extrair perfil → `site_data.json` → HTML puro → Netlify (demo) → TanStack Start (pós-venda).

## Setup

```bash
cd /Users/matheuspuppe/Desktop/Infoprodutos/instagram-site-factory
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

## Testes (TDD)

```bash
# Rodar toda a suíte
pytest

# Verbose + cobertura
pytest -v --cov=pipeline --cov-report=term-missing

# Um módulo específico
pytest tests/test_parse_context.py -v
```

Cobertura atual: funções puras do pipeline (`parse_context`, `readiness_score`, `generate_demo_html`, `transcribe`, `metadata_enrich`, `instagram`).

Requer `ffmpeg` apenas se for transcrever reels (`brew install ffmpeg`).

## Uso rápido

```bash
# Gerar demo completo (extração + transcrição + site + linktree)
python pipeline/make_demo.py https://www.instagram.com/salao_exemplo

# Só transcrever vídeos já baixados
python pipeline/transcribe_videos.py output/salao_exemplo --limit 12

# Só extrair dados (sem HTML)
python pipeline/extract_profile.py @salao_exemplo

# Gerar HTML a partir de site_data.json existente
python pipeline/generate_demo_html.py output/salao_exemplo
```

## O que é gerado

| Pasta | Conteúdo |
|-------|----------|
| `linktree/` | Página estilo Linktree (link na bio) |
| `demo/` | Site completo com galeria e serviços |
| `publish/` | **Pacote para apresentar ao cliente** — linktree na raiz + site em `/site/` |

## Deploy Netlify

```bash
cd output/salao_exemplo/publish
netlify deploy --prod --dir=.
```

O cliente abre o link e vê o linktree; ao clicar em "Ver site completo" vai para o site.

## Estrutura

- `pipeline/` — scripts Python
- `templates/local-demo/` — template HTML puro
- `output/` — demos gerados (gitignored)
- `clients/` — sites TanStack após fechamento
- `outreach/` — scripts de prospecção