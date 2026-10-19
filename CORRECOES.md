# Correções implementadas — Milton Analytics

10/09/2026. Revisão local sobre o commit `59f23cc568664879483e451046157e0e5f1e72bf`. Este relatório complementa a auditoria inicial, que descreve o código anterior às correções. As alterações ainda não foram enviadas ao GitHub.

## 🔴 Erros críticos corrigidos

### C1 — Exposição de arquivos

[backend/routes.py:15](backend/routes.py#L15). Assets limitados a /static e dashboard servido explicitamente. Testes de acesso a código, .git, configurações e caminhos codificados retornam 404. CSP e cabeçalhos de segurança aplicados; não se usa servidor debug.

### C2/C3 — Agregações incorretas

[backend/queries.py:17](backend/queries.py#L17). Fatos mensais são agregados por operadora/território antes das demais junções. Contagem de planos ocorre separadamente. Um único mês/ano é consultado. O teste com múltiplos municípios, operadoras e planos confirma SP=400 beneficiários, líder=80%, cobertura ponderada=14% e total nacional=450, sem multiplicação.

### C4 — Indicadores inventados

[static/js/config.js:18](static/js/config.js#L18). Removidas fórmulas que transformavam cobertura ou população em vacinação, leitos e outros indicadores. Valores só vêm do campo próprio ou de indicador_saude; ausência aparece como indisponível. Nenhuma série clínica oficial foi fabricada.

### C5/C6 — Falhas silenciosas e estado divergente

[static/js/api.js:19](static/js/api.js#L19). Cancelamento, timeout incluindo leitura do corpo e identificação da requisição mais recente impedem sobrescrita por resposta atrasada. Estado de carregamento/erro limpa dados anteriores. Um snapshot consistente alimenta mapa, painel, legenda e PIP; zeros são preservados.

### C7 — Falso detalhamento municipal

[static/js/app.js:12](static/js/app.js#L12). Zoom só altera a câmera. UF e código IBGE selecionados explicitamente filtram a tabela. O mapa permanece estadual e informa essa limitação. Corrigido também o código de Campinas na seed.

### C8 — Histórico pessoal exposto

[backend/routes.py:182](backend/routes.py#L182). A rota pública de histórico retorna 403 e a navegação não a oferece. Personas são perfis de apresentação, não mecanismos de autenticação.

### C9/C10 — Importação e seed

[fetch_real_data.py:72](fetch_real_data.py#L72). Carga atômica por dataset, UPSERT repetível, validação de identificadores e tratamento do CSV real em UTF-8 com cabeçalhos maiúsculos. Testes confirmam rollback integral em conflito e atualização sem duplicação. Seed exige --demo, é determinística e não popula dados pessoais fictícios.

## 🟡 Performance e UX implementadas

### U1/U2/U3/U4 — Ciclo de vida D3

[static/js/map.js:5](static/js/map.js#L5). Join por chave reutiliza os 27 paths. Transições de cor são nomeadas/interrompidas, separadas do zoom e respeitam movimento reduzido. Tooltip calcula conteúdo na entrada e posição por requestAnimationFrame; resize é observado e cancelado. Retry descarta respostas antigas. Eventos, observadores, requisições e gráficos têm descarte explícito. Não foi realizado perfil de heap/FPS; não se afirma que havia vazamento permanente comprovado.

### U5/U6/U7/U8 — Contrato visual

[static/js/store.js:2](static/js/store.js#L2). Preferências são validadas antes do primeiro render. PIP alterna mapa/tabela nas duas direções. UF representa atuação/abrangência, não sede da operadora. Métrica, unidade, escala, legenda e formato são compartilhados. Ausência não vira zero, e camada sem valores não mostra gradiente enganoso.

### U9/U10 — Dados auxiliares e API

[backend/routes.py:115](backend/routes.py#L115). Contagens são consultas exatas; listas têm busca, ordenação permitida, paginação de até 100 itens e recorte territorial/temporal. Queries não executam uma consulta por linha. Pool limitado a 8 conexões, timeout SQL de 8s e erros estruturados 400/404/500/503. Gráficos identificam que representam a página visível, e são limpos ao trocar a consulta.

### U11 — Acessibilidade e responsividade

[static/js/dom.js:1](static/js/dom.js#L1). Texto de dados entra por textContent, sem interpolação HTML. Controles possuem foco/teclado, estados ARIA e mensagens de carregamento/erro. Corrigidos corte vertical do mapa e layout mobile. Verificação em navegador a 390×844 confirmou largura do documento igual à viewport, sem transbordamento horizontal.

## 🔵 Estrutura e banco

O monólito de 5.021 linhas foi separado em estrutura HTML, CSS e módulos JavaScript de estado, rede, mapa, tabela, painéis, configuração e coordenação. Flask foi dividido em conexão, consultas e rotas. Dependências foram fixadas; D3 e Chart.js são servidos localmente com suas licenças.

O schema ganhou proveniência, constraints de domínio, integridade entre ano e competência, integridade territorial, índices por período e território, atualização de timestamps e relacionamento normalizado entre histórico e produtos. A nova tabela indicador_saude define grão, unidade e fonte. A migração preserva dados existentes e falha atomicamente se houver valores incompatíveis. A FK de feedback está NOT VALID para preservar legado: novos registros são validados, mas registros antigos precisam de saneamento antes de VALIDATE CONSTRAINT. Não foi feito saneamento de um banco de produção fornecido pelo usuário.

O README contém o roadmap incremental: ingestão oficial por indicador, testes de navegador em CI, medição de consultas em escala e eventual evolução dos módulos para componentes. Nenhuma troca de framework é necessária para executar a versão atual.

## Evidências de execução

- PostgreSQL 16.15 real iniciado localmente; schema novo executado, migração repetida e seed repetida sem duplicação.
- 31 testes de integração passaram na pasta de entrega em 35,35s, incluindo regressão do cabeçalho UTF-8 da ANS; 8 testes JavaScript passaram.
- DDL completo validado em schema temporário e revertido; testes usam schemas isolados. O schema original do GitHub seguido da migração 001 também foi executado com sucesso em uma transação de validação revertida.
- API e dashboard executados com Waitress em http://127.0.0.1:5001.
- Cadastros reais importados: 27 UFs, 5.571 municípios e 1.111 operadoras. Quatro operadoras de demonstração permanecem identificadas, totalizando 1.115 na tabela local.
- Navegador: três personas, mudança de camada, persistência após reload, UF São Paulo, município Campinas, PIP nas duas direções, visão geral, segunda página de operadoras e responsividade. Nenhum erro no console nas verificações finais.

## Limites da entrega

Não houve teste de carga, medição de heap/FPS, deploy público, push no GitHub nem acesso a uma base de produção. Vacinação, APS, alertas, leitos, profissionais e estabelecimentos ainda dependem de fontes oficiais e ingestores específicos. A malha municipal não foi implementada; a consulta municipal funciona por código IBGE na tabela. Os exemplos de beneficiários, planos e perfis são demonstrativos e ficam assim identificados. O projeto corrigido é executável, mas não deve ser apresentado como base clínica oficial completa.

O ZIP contém código, testes e instruções, sem credenciais, ambiente Python, binários PostgreSQL ou banco local. Para este computador, use `iniciar-milton-local.ps1` na pasta outputs; ele reutiliza o ambiente instalado em work. Para outro computador, siga o README do projeto.
