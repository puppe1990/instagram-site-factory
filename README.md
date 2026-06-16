# Instagram Site Factory

Pipeline para gerar demos de sites de negócios locais a partir do Instagram.

**Fluxo:** extrair perfil → `site_data.json` → HTML puro → Netlify (demo) → TanStack Start (pós-venda).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

## Testes (TDD)

```bash
# Rodar toda a suíte
pytest tests/

# Verbose + cobertura
pytest tests/ -v --cov=pipeline --cov-report=term-missing

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
| `linktree/` | Página estilo Linktree (link na bio), com toggle claro/escuro |
| `demo/` | Site completo local para revisão |
| `publish/` | **Pacote para apresentar ao cliente** — linktree na raiz + site em `/site/` |

### Site editorial (`/site/`)

O template em `templates/local-demo/` gera um site com visual editorial (Instrument Serif + Sora), montado automaticamente a partir do `site_data.json`:

| Seção | Fonte no perfil |
|-------|-----------------|
| Hero | Nome, categoria, OAB (se houver), foto de perfil |
| Manifesto | Primeiro highlight ou trecho da bio |
| Onde atuo | Serviços/áreas de atuação (cards numerados) |
| Conteúdo em destaque | Primeiro post da galeria ou highlight |
| Sobre | Bio estendida + credenciais (OAB, tópicos) |
| Contato | WhatsApp (se houver) ou Instagram |

CTAs e botão flutuante seguem o canal disponível: perfis com WhatsApp na bio usam `wa.me`; os demais apontam para o Instagram.

Estilos de perfil (`profile_style`):

- `professional` — layout editorial padrão (advogados, clínicas, serviços)
- `creator` — mesma estrutura, copy e fontes ajustadas para criadores

## Deploy Netlify

```bash
cd output/salao_exemplo/publish
netlify deploy --prod --dir=.
```

O cliente abre o link e vê o linktree; ao clicar em "Ver site completo" vai para o site editorial em `/site/`.

URLs de preview social (`og:image`) são geradas com caminho absoluto e nome por username (`og-{slug}.jpg`) para evitar cache antigo no Instagram/WhatsApp.

## Estrutura

- `pipeline/` — scripts Python (extração, parse, geração HTML, transcrição)
- `pipeline/lib/` — utilitários compartilhados (Instagram, favicon, metadata)
- `templates/local-demo/` — template do site (`index.html`, `styles.css`, `editorial.css`)
- `templates/linktree-demo/` — template do link na bio (tema claro/escuro)
- `output/` — demos gerados (gitignored)
- `clients/` — sites TanStack após fechamento
- `outreach/` — scripts de prospecção
