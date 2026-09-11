# Milton Analytics - Observatorio de Saude Suplementar

Dashboard interativo utilizando **Flask + PostgreSQL** no backend, e **JavaScript modular, D3.js e Chart.js** no frontend. 

O projeto foi totalmente reestruturado para ser modular, separando responsabilidades e melhorando a UX (Experiencia do Usuario) e Acessibilidade (leia mais em [Design e Acessibilidade](DESIGN-ACESSIBILIDADE.md)). O sistema apresenta dados da saude suplementar e publica no Brasil, filtrados por **Tres Personas** (Pessoa Comum, Setor Publico, Setor Privado).

---

## Tutorial Passo a Passo: Como Rodar o Projeto

Siga os passos abaixo para rodar a aplicacao localmente no seu computador.

### 1. Pre-requisitos
*   **Python 3.11** ou superior instalado.
*   **PostgreSQL 16** ou superior (Pode ser instalado nativamente ou via Docker).
*   *Opcional para testes front-end:* Node.js 20+.

### 2. Preparando o Ambiente Python
Abra o seu terminal (PowerShell, CMD ou Bash) e execute os seguintes comandos:

`ash
# 1. Crie um ambiente virtual para nao misturar dependencias
python -m venv .venv

# 2. Ative o ambiente virtual
# No Windows (PowerShell):
.venv\Scripts\Activate.ps1
# No Linux/Mac:
source .venv/bin/activate

# 3. Instale todas as dependencias do projeto
python -m pip install -r requirements.txt
`

### 3. Configurando o Banco de Dados (PostgreSQL)
O sistema precisa de um banco de dados para buscar as informacoes.

1.  Copie o arquivo .env.example e cole com o nome .env.
2.  Abra o arquivo .env gerado e defina uma senha forte na variavel MILTON_DB_PASS.
3.  **Para subir o banco com Docker:**
    *   Basta rodar o comando: docker compose up -d
4.  **Se nao for usar Docker:**
    *   Crie um banco de dados no seu PostgreSQL local com o nome, usuario e senha que voce definiu no arquivo .env.

### 4. Inicializando e Rodando o Servidor

Agora que o banco esta pronto, vamos criar as tabelas, inserir dados de exemplo e rodar o site.

`ash
# 1. Aplique o schema e popule o banco de dados com dados de demonstracao
python start.py --init-db --demo

# 2. Acesse o painel pelo seu navegador no endereco:
# http://127.0.0.1:5001
`

> **Nota:** Nas proximas vezes que for iniciar o servidor (sem precisar recriar o banco), basta rodar apenas python start.py.

---

## Nova Estrutura do Projeto

O projeto deixou de ser um arquivo HTML gigante e agora adota uma estrutura limpa e profissional:

*   **pi.py / start.py**: Pontos de entrada do servidor backend Flask.
*   **ackend/**: Contem a logica do servidor.
    *   db.py: Conexao, transacoes e pool de banco de dados.
    *   queries.py: Logicas de agregacoes e SQL.
    *   
outes.py: Endpoints da API REST.
*   **dashboard.html**: A casca da estrutura principal da pagina.
*   **static/**: Arquivos do Frontend, organizados por:
    *   js/: Scripts modulares (pp.js, map.js, 	able.js, store.js, pi.js).
    *   styles/: CSS dividido em responsabilidades (dashboard.css, ixes.css, 
efinements.css).
    *   endor/: Bibliotecas de terceiros (D3.js, Chart.js).
    *   data/: Arquivos geojson (ex: malha do Brasil para o mapa).
*   **migrations/ & migrate.py**: Ferramentas para controle de versao e evolucao do banco de dados.

---

## Dados Reais vs Demonstracao

*   **Dados de Teste (Demo):** O comando --demo (mostrado acima) popula tabelas com dados de pacientes ficticios, planos sinteticos e numeros gerados matematicamente. Serve para ver a plataforma funcionando.
*   **Dados Reais do IBGE/ANS:** Voce pode rodar o comando python fetch_real_data.py --only estados municipios operadoras para baixar cadastros publicos atualizados (tabelas geograficas oficiais). *Nota: os cadastros de operadoras abertos da ANS nao fornecem quantidade de beneficiarios na mesma fonte primaria.*

## Como Testar a Aplicacao

Para certificar que o banco e a API estao consistentes, execute:

`ash
# Valida se todas as constraints e schemas do banco estao corretos
python validate_schema.py

# Roda a bateria de testes Python (Pytest)
python -m pytest -q

# Roda os testes de Frontend (Jest)
npm test
`

## Proximos Passos (Roadmap)

1.  **Ingestores Oficiais:** Adicionar ingestores automaticos por indicador de saude real (Cobertura, IDH atualizado).
2.  **CI/CD:** Criar pipeline de testes reproduziveis automatizados.
3.  **Otimizacao de Banco:** Medir gargalos com EXPLAIN ANALYZE quando o volume de dados crescer.
4.  **Autenticacao:** Implementar controle de acesso e autorizacao antes de expor dados de pacientes a internet.

---
*D3.js e Chart.js estao localizados em static/vendor/ sob suas respectivas licencas de codigo aberto.*
