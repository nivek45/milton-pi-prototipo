# Milton Analytics — Observatório de Saúde Suplementar

Dashboard Flask + PostgreSQL, com JavaScript modular, D3 e Chart.js. Esta revisão corrige agregações, sincronização assíncrona, proveniência, segurança e navegação das três personas. O mapa mostra UFs; o detalhamento municipal ocorre na tabela por seleção explícita.

## Executar

Requisitos: Python 3.11+, PostgreSQL 16+; Node 20+ apenas para os testes JavaScript. Docker é opcional, para fornecer PostgreSQL.

1. Crie um ambiente: `python -m venv .venv` e ative-o (`.venv\Scripts\Activate.ps1` no PowerShell).
2. Instale: `python -m pip install -r requirements.txt`.
3. Copie `.env.example` para `.env`, configure seu banco e defina uma senha. Variáveis de ambiente já exportadas têm precedência.
4. Com Docker: `docker compose up -d`. Sem Docker, crie o usuário/banco configurados em um PostgreSQL existente.
5. Primeira execução: `python start.py --init-db`. Acesse http://127.0.0.1:5001.
6. Para uma base demonstrativa, use explicitamente `python start.py --init-db --demo`. Interrompa o servidor anterior antes de iniciar outro.
7. Execuções seguintes: `python start.py`.

`python migrate.py` aplica o schema novo ou migrações atômicas em banco legado. Faça backup do banco legado antes de migrar: dados antigos incompatíveis com constraints bloqueiam a transação e precisam ser corrigidos na origem. A inicialização nunca apaga tabelas. A seed é determinística e idempotente, e recusa misturar amostras com fatos preexistentes não reconhecidos.

## Dados reais e demonstração

`python fetch_real_data.py --only estados municipios operadoras` importa cadastros públicos IBGE e ANS, com UPSERT e transação por conjunto. O cadastro de operadoras não fornece números de beneficiários nem market share. A carga foi executada nesta revisão: 27 UFs, 5.571 municípios e 1.111 operadoras do cadastro ANS. Valores são uma fotografia da execução, não totais permanentes.

Beneficiários, planos e perfis da seed são exemplos explicitamente sintéticos. Vacinação, cobertura APS, alertas, leitos, profissionais e estabelecimentos não são inferidos de proxies. Sem fonte cadastrada em `indicador_saude`, aparecem como indisponíveis. Essa tabela exige unidade, competência e fonte; a ingestão de cada série oficial ainda precisa ser implementada e validada. Não há malha municipal nem promessa de vacinação real nesta versão.

Market share no mapa é a participação da maior operadora no total da UF, no mês escolhido. Cobertura e renda são ponderadas pela população dos municípios com dados; IDH é média municipal, não o IDH oficial da UF. Ausência é `null`, distinta de zero. O período automático usa fatos existentes, não apenas dimensões de calendário. A competência dos indicadores próprios aparece na fonte do tooltip.

## Estrutura e API

- `dashboard.html`: estrutura; `static/styles/`: apresentação.
- `static/js/store.js`: estado validado; `api.js`: timeout, cancelamento e descarte de respostas antigas.
- `map.js`, `table.js`, `panels.js`: mapa, tabelas e painéis; `app.js`: coordenação e eventos; `config.js`: personas e métricas.
- `backend/db.py`: pool limitado, transações de leitura e timeout SQL; `queries.py`: agregações; `routes.py`: validação, rotas e serialização.
- `schema.sql`, `migrations/`, `migrate.py`: bootstrap e evolução versionada.

`GET /api/snapshot` entrega estados, totais, indicadores e metadados em uma transação consistente. Listas `/api/operadoras`, `/api/market-share`, `/api/planos`, `/api/perfil-saude` retornam `{items,total,page,page_size,meta}`; página máxima de 100 itens. Filtros são validados e parametrizados. Veja `backend/routes.py` para nomes e valores aceitos. `/api/municipios?uf=SP` lista o cadastro municipal da UF. `/api/health` verifica PostgreSQL. Histórico pessoal não é publicado: `/api/historico` retorna 403. Aplicação e assets usam mesma origem; arquivos do repositório e credenciais não são servidos.

## Verificação

Com o banco configurado, execute:

```sh
python validate_schema.py
python -m pytest -q
npm test
```

Os testes de integração criam e removem somente um schema temporário próprio; o usuário de teste precisa de permissão para criar schemas. Cobrem agregações sem multiplicação, datas, paginação, filtros, constraints, falhas da API e rollback de importação. Os testes JavaScript cobrem estado, concorrência, cancelamento e ausência de dados. Testes não substituem medição de carga com o volume real futuro.

## Próximas etapas

1. Adicionar ingestores oficiais por indicador com testes de unidade, período e cobertura territorial; manter exemplos separados das bases oficiais.
2. Criar testes de navegador reproduzíveis e pipeline CI com PostgreSQL, preservando os contratos atuais.
3. Medir consultas com EXPLAIN ANALYZE em volume representativo antes de materializar agregados ou aumentar o pool.
4. Evoluir os módulos independentes para componentes conforme necessidade, sem migração obrigatória para React/Vue.
5. Antes de expor dados pessoais, implementar autenticação, autorização e uma política de retenção específica; a rota pública permanece fechada.

## Bibliotecas e geografia

D3 7.9.0 e Chart.js 4.4.9 estão em `static/vendor`, com licenças incluídas. A geometria estadual vendorizada vem de https://github.com/codeforamerica/click_that_hood/blob/master/public/data/brazil-states.geojson; o cadastro de códigos e nomes vem da API de Localidades do IBGE. A malha é destinada à visualização do protótipo, não a uso cartográfico de precisão. Fontes tipográficas Google são opcionais e têm fallback local.

## Atualização de UX e acessibilidade

A primeira rodada aprovada adiciona busca por cidade, explicações dos indicadores, painéis por persona, filtros recolhíveis e preservação de contexto. Consulte [Design e acessibilidade](DESIGN-ACESSIBILIDADE.md) para mudanças e verificação (33 testes PostgreSQL e 11 JavaScript).
