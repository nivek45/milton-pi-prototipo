# Perfil Pessoa Comum — dados reais da ANS

Implementação local de 02/10/2026. Na interface, Pessoa Comum aparece como **Convênios**.

## Entrega

- Mapa: quantidade de planos ativos com cobertura cadastrada por UF, sem substituir planos por beneficiários.
- Busca de cidades: cadastro real do IBGE, incluindo cidades fora da antiga demonstração.
- Catálogo paginado: busca por plano, operadora ou registro; filtros médico-hospitalar/odontológico e contratação.
- Operadoras: filtradas pelos planos com cobertura no território, independentemente do endereço da sede.
- Detalhes: registro ANS, segmentação, contratação, fator moderador original, acomodação, abrangência, estados, situação e data da fonte.
- Fontes e limitações explícitas; valores ausentes não viram zero ou “Não”.
- Menu fechado inicialmente, detalhes progressivos, suporte a teclado, diálogo nativo e movimento reduzido mantidos.

## Fontes integradas

| Base | Uso |
| --- | --- |
| PDA-008 características de produtos | Identificação, situação e características dos planos |
| PDA-008 detalhamento de municípios | Cobertura geográfica por ID_GEO_COBERTURA |
| CADOP de operadoras ativas | Registro, razão social, nome fantasia e modalidade |
| Cadastro municipal IBGE já existente | Correspondência dos códigos municipais e nomes |

Os URLs completos ficam em `import_ans_catalog.py`, no manifesto do download e nas respostas da API.

Carga realizada: **166.244 registros de planos** (incluindo históricos/inativos, que não aparecem na consulta), **883.925 relações geográficas** e **1.106 operadoras no CADOP**. O filtro de plano Ativo + operadora ativa retorna **28.990 planos de 863 operadoras** nesta edição. Data do catálogo: **2026-10-02**.

`ID_PLANO` é a chave interna ANS. `CD_PLANO` é preservado como texto. A ligação territorial usa o identificador de grupo geográfico; códigos ANS municipais de seis posições são associados aos códigos IBGE de sete posições pelo cadastro oficial. Grupos nacionais são compartilhados, sem replicar milhões de pares plano/município. Contagens por UF não devem ser somadas como total nacional.

**Cobertura geográfica não é área de comercialização nem confirmação de rede credenciada.** A consulta não afirma que um plano pode ser comprado por qualquer pessoa: planos coletivos e autogestões têm regras próprias. Planos sem vínculo geográfico correspondente podem aparecer no catálogo nacional, mas não são atribuídos artificialmente a uma UF.

## Separação dos bancos

- Perfil Pessoa Comum: rotas `/api/pessoa-comum/*`, conexão `MILTON_COMMON_DB_NAME` (padrão `miltondb`).
- Demais perfis: rotas existentes, conexão `MILTON_DB_NAME`; no iniciador local, `milton_demo_20261001`.
- Se o catálogo real não estiver carregado, a API responde 503 com orientação. **Não há fallback para mock.**
- Trocar de perfil cancela requisições anteriores, recarrega a base e invalida tabelas de outra persona.

Endpoints: `snapshot`, `localidades?q=`, `municipios?uf=`, `planos`, `operadoras`, `planos/<id>` sob `/api/pessoa-comum/`.
Listas aceitam `uf`, `municipio`, `q`, `page`, `page_size` (1–100), `sort`, `direction`. Planos aceitam `assistencia=medica|odonto` e `contratacao` com o valor exibido no seletor. Identificadores de ordenação são validados em lista fixa; valores SQL são parametrizados.

## Reproduzir a carga

1. Instalar `requirements.txt` e configurar PostgreSQL conforme `.env.example`.
2. Selecionar o banco real em `MILTON_DB_NAME`; executar `python migrate.py`.
3. Se não houver cadastro territorial: `python fetch_real_data.py --only estados municipios`.
4. Executar `python import_ans_catalog.py --directory caminho/para/cache-ans --download`.
5. Para reprocessar os arquivos já baixados, omitir `--download`.
6. Iniciar o servidor com `python start.py`. Para a configuração desta máquina: `outputs/iniciar-milton-local.ps1`, porta 5002.

O importador valida cabeçalhos, completude mínima, chaves únicas e correspondência municipal. A substituição ocorre em uma única transação, sob lock de importação. Uma falha preserva a edição anterior. URLs e SHA-256 são gravados em `manifest.json` no diretório de download. Os CSVs não são publicados no GitHub.

## Bases fornecidas ainda não integradas

NTRP/área de comercialização, rede hospitalar, operadoras acreditadas, serviços opcionais, preços, vínculos de beneficiários e taxa de cobertura não foram utilizados para inventar campos do catálogo. São integrações separadas: exigem seus próprios identificadores, competências e regras de agregação. A tela informa que preço e prestadores específicos ainda não estão disponíveis. Market share permanece somente no perfil privado de demonstração, identificado como fictício.

## Verificação

Testes de integração usam um schema temporário isolado, sem alterar a carga oficial. Cobrem geografia versus sede, exclusão de plano/operadora inativos, ausência de fallback, coparticipação desconhecida, limites de paginação, parâmetros inválidos, busca literal e filtros de contratação/assistência. Testes de frontend cobrem roteamento por persona, colunas próprias, estado e requisições concorrentes. Validação no navegador inclui busca de cidade, catálogo, detalhes, troca de perfil e teclado.

Nada foi enviado ao GitHub nesta entrega.
