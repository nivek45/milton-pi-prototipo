# Milton PI API — Protótipo do Modelo Físico PostgreSQL

Sistema de recomendação de planos de saúde — banco protótipo com 14 tabelas,
dados reais (IBGE + ANS) e dados sintéticos para validação do modelo ER.

---

## Pré-requisitos

- Docker + Docker Compose
- Python 3.9+

```bash
pip install psycopg2-binary faker requests
```

---

## Como rodar o projeto (One-Click Deploy)

O projeto possui um orquestrador integrado que sobe o banco, baixa os dados e inicia o dashboard automaticamente.

```bash
# Executa tudo de uma vez
python start.py
```

O script ira:
1. Subir a infraestrutura (`docker compose up -d`).
2. Aguardar o banco de dados estar pronto.
3. Perguntar se voce deseja carregar os **dados reais do IBGE e ANS** (opcional).
4. Gerar os dados ficticios (`seed.py`) para completar as demais tabelas.
5. Iniciar o dashboard e abri-lo no seu navegador (`http://localhost:5001`).

---

## Fontes de dados — URL real verificada × autenticação (17/08/2026)

> **Aviso:** Os caminhos do FTP da ANS mudam com frequência.
> Antes de rodar em produção, confirmar o índice em:
> `https://dadosabertos.ans.gov.br/FTP/PDA/`

| Fonte | URL verificada | Auth? | Script |
|---|---|---|---|
| IBGE Localidades (estados) | `servicodados.ibge.gov.br/api/v1/localidades/estados` | Não | `fetch_real_data.py` |
| IBGE Localidades (municípios) | `servicodados.ibge.gov.br/api/v1/localidades/municipios` | Não | `fetch_real_data.py` |
| ANS CADOP (operadoras ativas) | `.../operadoras_de_plano_de_saude_ativas/Relatorio_cadop.csv` | Não¹ | `fetch_real_data.py` |
| ANS Produtos (planos) | `.../caracteristicas_produtos_saude_suplementar-008/` | Não¹ | — (cabeçalho a confirmar) |
| CNES / CADSUS / SISREG | `apidadosabertos.saude.gov.br` | **Sim** | — (fora do protótipo) |
| CNES via BigQuery | Base dos Dados | **Sim (GCP)** | — (fora do protótipo) |

¹ Público, mas caminho muda — confirmar no índice FTP antes de rodar.

**Nota sobre `produto_saude`:** o cabeçalho real do CSV de produtos ANS ainda
não foi verificado (só linhas de exemplo). Antes de escrever o parser,
conferir o header em `caracteristicas_produtos_saude_suplementar-008/`.

---

## Smoke tests rápidos

```sql
-- Contar registros em todas as tabelas
SELECT relname AS tabela, n_live_tup AS linhas
FROM pg_stat_user_tables
ORDER BY relname;

-- Verificar FKs de market_share
SELECT ms.id, m.nome AS municipio, o.nome_fantasia AS operadora,
       ms.percentual_market_share
FROM market_share ms
JOIN municipio m ON m.id = ms.id_municipio
JOIN operadora o ON o.id = ms.id_operadora
LIMIT 10;

-- Planos disponíveis em um município
SELECT ps.nome_plano, ps.tipo_contratacao, ps.segmentacao
FROM produto_saude ps
JOIN abrangencia_plano ap ON ap.id_produto_saude = ps.id
JOIN municipio m ON m.id = ap.id_municipio
WHERE m.nome = 'São Paulo'
  AND ps.ativo = true;
```

---

## Exportar schema para revisão

```bash
docker exec milton_pg pg_dump -U milton -d miltondb --schema-only > schema_dump.sql
```

---

## Tabelas do modelo (14)

| # | Tabela | Origem |
|---|---|---|
| 1 | `estado` | IBGE — real (`fetch_real_data.py`) |
| 2 | `municipio` | IBGE — real (`fetch_real_data.py`) |
| 3 | `serie_temporal_anual` | Controle interno |
| 4 | `serie_temporal_mensal` | Controle interno |
| 5 | `operadora` | ANS CADOP — real (`fetch_real_data.py`) |
| 6 | `produto_saude` | ANS — real (cabeçalho a confirmar) |
| 7 | `abrangencia_plano` | ANS + IBGE — derivado |
| 8 | `preco_faixa_etaria` | ANS TISS — real |
| 9 | `market_share` | ANS beneficiários — estimado |
| 10 | `rede_credenciada_sintetica` | **SINTÉTICO** — aguardando e-SUS |
| 11 | `perfil_saude_publica` | IBGE PNAD + Datasus — real |
| 12 | `usuario` | Sistema interno |
| 13 | `historico_busca_recomendacao` | Sistema interno |
| 14 | `feedback_usuario` | Sistema interno |

---

## Resetar o banco

```bash
docker compose down -v        # remove container + volume
docker compose up -d          # recria tudo do zero
python fetch_real_data.py     # dados reais (opcional)
python seed.py                # dados fictícios (obrigatório para demais tabelas)
```

---

## pgAdmin (opcional)

```bash
docker compose --profile admin up -d
```

Acesse: http://localhost:5050  
Login: `admin@milton.local` / `pgadminpass`  
Servidor: `milton_pg` / porta `5432` / usuário `milton` / senha `miltonpass`
