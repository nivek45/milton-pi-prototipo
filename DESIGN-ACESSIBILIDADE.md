# Design e acessibilidade — primeira rodada

Implementação de 11/09/2026, sobre a versão corrigida do Milton Analytics.

## O que mudou

- **Começar pela cidade:** busca pelo nome em todo o cadastro, com ou sem acentos. Resultados incluem estado para distinguir nomes semelhantes. O endpoint `/api/localidades?q=...` limita resultados a 20 e valida a entrada. Escolher uma cidade aplica seu código IBGE à consulta municipal.
- **Linguagem:** estado, cidade e mês de referência substituem abreviações nos controles principais. Explicações acessíveis por clique e teclado descrevem as métricas e termos das tabelas, como APS, ANS, IDH, Gini, participação de mercado e coparticipação.
- **Personas:** o painel lateral mostra as três métricas do perfil ativo e oferece atalhos específicos. Dados não disponíveis permanecem identificados como ausentes.
- **Filtros:** localização permanece visível. Mês e ano ficam em “Mais filtros”, com o período resumido mesmo quando fechado. Filtros ativos podem ser removidos individualmente.
- **Contexto:** atualização de dados e trocas de persona preservam cidade e período. Voltar à tabela restaura página e ordenação da consulta. A busca na tabela é lembrada por persona durante a sessão. A posição de rolagem é lembrada por página e visualização. Isso não salva localização em um servidor nem depende de cadastro do usuário.
- **Apresentação:** faixa informativa compacta, contraste reforçado, painel mais legível e botões com resposta visual. Cores e tipografia principais foram preservadas. O PIP identifica o local e a ação de retorno.
- **Animações:** indicador deslizante de persona, entradas curtas de painel/tabela e transição de cores do mapa. Animações interrompidas são canceladas. Os números não recebem contagem artificial.

## Acessibilidade implementada

- Link “Pular para o conteúdo”, estrutura de títulos, rótulos nos campos e legendas nas tabelas.
- Busca com formulário nativo e resultados em botões: Enter busca/seleciona, Tab navega, Escape fecha resultados.
- Seletores de camadas permanecem no DOM durante a troca da métrica, preservando o foco.
- Menu mobile com foco contido, fechamento por Escape e retorno ao botão de abertura. Conteúdo ao fundo fica inerte enquanto aberto; menu fechado não entra na sequência de Tab.
- Foco visível e mensagens de busca, carregamento, paginação e erro disponíveis em regiões de anúncio para tecnologia assistiva.
- Paginação mantém o foco após atualizar as linhas; região da tabela permite rolagem por teclado.
- Movimento reduzido desativa CSS animado e as novas animações JavaScript; alterar essa preferência cancela animações em andamento.
- Gráficos têm identificação textual; tabelas e contagens continuam oferecendo acesso aos valores sem depender de cor ou canvas.
- Controles de toque e disposição do mapa foram revistos em 390 × 844. Zoom, camadas e alternância de tabela ficam separados.

## Verificação realizada

- **33 testes de integração PostgreSQL passaram**, incluindo busca sem acentos, código IBGE correto, limites de entrada e tratamento literal de caracteres de busca.
- **11 testes JavaScript passaram**, incluindo preservação de contexto, paginação/ordenação, respostas concorrentes e movimento reduzido.
- Navegador: busca e seleção de Campinas por Enter; mês preservado na mudança de persona; atualização preservando cidade; remoção de filtro com retorno do foco; troca de camada sem perda do foco; menu mobile com Shift+Tab e Escape; tabela retornando à página 2 após alternar mapa/tabela.
- Nenhum campo input/select sem rótulo acessível na verificação final do DOM. Nenhum ID duplicado. Sem transbordamento horizontal do conteúdo principal nas larguras conferidas (390 px e desktop padrão). Sem erros no console nas verificações finais.

Essas verificações não constituem uma certificação WCAG nem substituem testes com pessoas que usam leitores de tela. Não houve execução manual com NVDA/JAWS nesta rodada. Comparação entre cidades e resumos interpretativos automáticos continuam fora desta primeira rodada aprovada.

## Arquivos principais

- `static/styles/refinements.css`: ajustes visuais e responsivos.
- `static/js/location.js`: busca de cidades e filtros ativos.
- `static/js/accessibility.js`: ciclo de foco do menu mobile.
- `static/js/motion.js`: animações canceláveis e movimento reduzido.
- `static/js/app.js`, `panels.js`, `table.js`: integração, personas e preservação de contexto.
- `backend/routes.py`: busca de cidades no cadastro existente.

O mapa continua estadual; o detalhe municipal usa a tabela. Dados demonstrativos continuam sinalizados. Para executar em outro computador, siga o README; para o ambiente local já instalado, use o iniciador na pasta outputs.
