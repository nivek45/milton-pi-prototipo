-- MILTON PI API — Protótipo do Modelo Físico PostgreSQL

-- Habilita extensões úteis para protótipo
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- FASE 2: TABELAS DE DIMENSÃO / CONTROLE TEMPORAL
-- =============================================================================

-- estado — Origem: IBGE API Localidades (real)
CREATE TABLE estado (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_ibge     varchar(2)   NOT NULL,
    sigla           varchar(2)   NOT NULL,
    nome            varchar(100) NOT NULL,
    regiao          varchar(20)  NOT NULL,
    created_at      timestamptz  DEFAULT now(),

    CONSTRAINT uq_estado_codigo_ibge UNIQUE (codigo_ibge),
    CONSTRAINT uq_estado_sigla       UNIQUE (sigla)
);

COMMENT ON TABLE  estado             IS 'Unidades federativas brasileiras — IBGE API Localidades';
COMMENT ON COLUMN estado.codigo_ibge IS 'Código de 2 dígitos do IBGE para a UF';
COMMENT ON COLUMN estado.regiao      IS 'Região geográfica: Norte, Nordeste, Centro-Oeste, Sudeste, Sul';

-- municipio — Origem: IBGE API Localidades (real)
CREATE TABLE municipio (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_ibge     varchar(7)   NOT NULL,
    nome            varchar(150) NOT NULL,
    id_estado       bigint       NOT NULL REFERENCES estado(id),
    latitude        numeric(9,6),
    longitude       numeric(9,6),
    created_at      timestamptz  DEFAULT now(),

    CONSTRAINT uq_municipio_codigo_ibge UNIQUE (codigo_ibge)
);

COMMENT ON TABLE  municipio             IS 'Municípios brasileiros — IBGE API Localidades';
COMMENT ON COLUMN municipio.codigo_ibge IS 'Código IBGE de 7 dígitos do município';

-- serie_temporal_anual — Controle interno
CREATE TABLE serie_temporal_anual (
    id          bigint   GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ano         smallint NOT NULL,

    CONSTRAINT uq_serie_anual_ano   UNIQUE (ano),
    CONSTRAINT chk_serie_anual_ano  CHECK  (ano BETWEEN 2000 AND 2100)
);

COMMENT ON TABLE serie_temporal_anual IS 'Dimensão de controle temporal anual';

-- serie_temporal_mensal — Controle interno
CREATE TABLE serie_temporal_mensal (
    id              bigint   GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_serie_anual  bigint   NOT NULL REFERENCES serie_temporal_anual(id),
    ano             smallint NOT NULL,
    mes             smallint NOT NULL,
    competencia     varchar(7) NOT NULL,

    CONSTRAINT uq_serie_mensal_ano_mes UNIQUE (ano, mes),
    CONSTRAINT chk_serie_mensal_mes    CHECK  (mes BETWEEN 1 AND 12)
);

COMMENT ON TABLE  serie_temporal_mensal             IS 'Dimensão de controle temporal mensal';
COMMENT ON COLUMN serie_temporal_mensal.competencia IS 'Período no formato YYYY-MM, alinhado com padrão ANS';

-- operadora — Origem: ANS Dados Abertos cadoper.csv (real)
CREATE TABLE operadora (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    registro_ans    varchar(6)   NOT NULL,
    cnpj            varchar(14)  NOT NULL,
    razao_social    varchar(200) NOT NULL,
    nome_fantasia   varchar(200),
    modalidade      varchar(60)  NOT NULL,
    uf_sede         varchar(2),
    situacao        varchar(20)  NOT NULL DEFAULT 'ativa',
    data_registro   date,
    created_at      timestamptz  DEFAULT now(),
    updated_at      timestamptz  DEFAULT now(),

    CONSTRAINT uq_operadora_registro_ans UNIQUE (registro_ans),
    CONSTRAINT uq_operadora_cnpj         UNIQUE (cnpj)
);

COMMENT ON TABLE  operadora              IS 'Operadoras de planos de saúde — ANS cadoper.csv';
COMMENT ON COLUMN operadora.registro_ans IS 'Código ANS de 6 dígitos que identifica a operadora';
COMMENT ON COLUMN operadora.modalidade   IS 'Modalidade ANS: Cooperativa Médica, Medicina de Grupo, Seguradora, Filantropia, Autogestão, Administradora';

-- =============================================================================
-- FASE 3: ENTIDADES PRINCIPAIS DE NEGÓCIO
-- =============================================================================

-- produto_saude — Origem: ANS Dados Abertos (real)
CREATE TABLE produto_saude (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_plano_ans    varchar(12)  NOT NULL,
    nome_plano          varchar(200) NOT NULL,
    id_operadora        bigint       NOT NULL REFERENCES operadora(id),
    tipo_contratacao    varchar(30)  NOT NULL,
    segmentacao         varchar(50)  NOT NULL,
    cobertura           varchar(30)  NOT NULL,
    possui_copart       boolean      NOT NULL DEFAULT false,
    ativo               boolean      NOT NULL DEFAULT true,
    data_inicio_venda   date,
    data_fim_venda      date,
    created_at          timestamptz  DEFAULT now(),
    updated_at          timestamptz  DEFAULT now(),

    CONSTRAINT uq_produto_saude_codigo_ans UNIQUE (codigo_plano_ans)
);

COMMENT ON TABLE  produto_saude                  IS 'Planos de saúde registrados na ANS';
COMMENT ON COLUMN produto_saude.codigo_plano_ans IS 'Código único do produto na ANS (CODPLANO)';
COMMENT ON COLUMN produto_saude.segmentacao      IS 'Segmentação ANS: ambulatorial, hospitalar, odontologico, referencia';
COMMENT ON COLUMN produto_saude.tipo_contratacao IS 'individual | coletivo_empresarial | coletivo_adesao';

-- abrangencia_plano — PK composta: (id_produto_saude, id_municipio)
CREATE TABLE abrangencia_plano (
    id_produto_saude    bigint NOT NULL REFERENCES produto_saude(id),
    id_municipio        bigint NOT NULL REFERENCES municipio(id),
    created_at          timestamptz DEFAULT now(),

    CONSTRAINT pk_abrangencia_plano PRIMARY KEY (id_produto_saude, id_municipio)
);

COMMENT ON TABLE abrangencia_plano IS 'Relação N:N entre plano e municípios de cobertura — ANS + IBGE derivado';

-- preco_faixa_etaria — Origem: ANS TISS (real)
CREATE TABLE preco_faixa_etaria (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_produto_saude    bigint          NOT NULL REFERENCES produto_saude(id),
    id_serie_mensal     bigint          NOT NULL REFERENCES serie_temporal_mensal(id),
    faixa_etaria        varchar(20)     NOT NULL,
    valor_mensalidade   numeric(12,2)   NOT NULL,
    reajuste_percentual numeric(5,4),
    created_at          timestamptz     DEFAULT now(),

    CONSTRAINT uq_preco_faixa UNIQUE (id_produto_saude, id_serie_mensal, faixa_etaria)
);

COMMENT ON TABLE  preco_faixa_etaria              IS 'Preços por faixa etária por competência — ANS TISS';
COMMENT ON COLUMN preco_faixa_etaria.faixa_etaria IS 'Faixas ANS: 00-18, 19-23, 24-28, 29-33, 34-38, 39-43, 44-48, 49-53, 54-58, 59+';

-- market_share — Origem: ANS beneficiários (real estimado)
CREATE TABLE market_share (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_municipio            bigint          NOT NULL REFERENCES municipio(id),
    id_serie_mensal         bigint          NOT NULL REFERENCES serie_temporal_mensal(id),
    id_operadora            bigint          NOT NULL REFERENCES operadora(id),
    total_beneficiarios     integer         NOT NULL DEFAULT 0,
    percentual_market_share numeric(5,4)    NOT NULL DEFAULT 0,
    created_at              timestamptz     DEFAULT now(),

    CONSTRAINT uq_market_share UNIQUE (id_municipio, id_serie_mensal, id_operadora)
);

COMMENT ON TABLE  market_share                         IS 'Market share de operadoras por município/competência — ANS';
COMMENT ON COLUMN market_share.percentual_market_share IS 'Percentual em decimal: 0.1234 = 12,34% do mercado local';

-- rede_credenciada_sintetica — SINTÉTICO (aguardando API e-SUS Regulação)
CREATE TABLE rede_credenciada_sintetica (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_produto_saude    bigint          NOT NULL REFERENCES produto_saude(id),
    id_municipio        bigint          NOT NULL REFERENCES municipio(id),
    tipo_servico        varchar(60)     NOT NULL,   -- sintético (aguardando API e-SUS Regulação)
    especialidade       varchar(100),               -- sintético (aguardando API e-SUS Regulação)
    quantidade_estimada integer         NOT NULL DEFAULT 0,  -- sintético (aguardando API e-SUS Regulação)
    fonte_estimativa    varchar(100)    DEFAULT 'estimativa_interna_v1',
    created_at          timestamptz     DEFAULT now(),
    updated_at          timestamptz     DEFAULT now()
);

COMMENT ON TABLE rede_credenciada_sintetica IS 'SINTÉTICO — rede de prestadores estimada; substituir quando API e-SUS Regulação estiver disponível';

-- perfil_saude_publica — Origem: IBGE PNAD + Datasus (real agregado)
CREATE TABLE perfil_saude_publica (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_municipio                bigint          NOT NULL REFERENCES municipio(id),
    id_serie_anual              bigint          NOT NULL REFERENCES serie_temporal_anual(id),
    populacao_estimada          integer,
    idh                         numeric(5,3),
    taxa_cobertura_plano_saude  numeric(5,4),
    renda_per_capita            numeric(12,2),
    taxa_mortalidade_infantil   numeric(6,2),
    indice_gini                 numeric(5,3),
    created_at                  timestamptz     DEFAULT now(),

    CONSTRAINT uq_perfil_saude_pub UNIQUE (id_municipio, id_serie_anual)
);

COMMENT ON TABLE  perfil_saude_publica                            IS 'Indicadores socioeconômicos e de saúde por município — IBGE PNAD + Datasus';
COMMENT ON COLUMN perfil_saude_publica.taxa_cobertura_plano_saude IS 'Proporção da população com plano de saúde privado (0.0 a 1.0)';

-- usuario — Sistema interno
CREATE TABLE usuario (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email           varchar(255) NOT NULL,
    nome            varchar(150) NOT NULL,
    senha_hash      text         NOT NULL,
    perfil_busca    jsonb,
    ativo           boolean      NOT NULL DEFAULT true,
    ultimo_acesso   timestamptz,
    created_at      timestamptz  DEFAULT now(),
    updated_at      timestamptz  DEFAULT now(),

    CONSTRAINT uq_usuario_email UNIQUE (email)
);

COMMENT ON TABLE  usuario              IS 'Usuários do sistema Milton PI';
COMMENT ON COLUMN usuario.perfil_busca IS 'JSON com preferências: {faixa_etaria, renda_familiar, tipo_plano, municipio_interesse}';

-- =============================================================================
-- FASE 4: TABELAS TRANSACIONAIS
-- =============================================================================

-- historico_busca_recomendacao — Sistema interno
CREATE TABLE historico_busca_recomendacao (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario          bigint      NOT NULL REFERENCES usuario(id),
    id_municipio        bigint      NOT NULL REFERENCES municipio(id),
    filtros_utilizados  jsonb       NOT NULL DEFAULT '{}',
    resultado_ids       jsonb       NOT NULL DEFAULT '[]',
    canal_acesso        varchar(30) DEFAULT 'web',
    created_at          timestamptz DEFAULT now()
);

COMMENT ON TABLE  historico_busca_recomendacao                    IS 'Histórico de buscas e recomendações de planos por usuário';
COMMENT ON COLUMN historico_busca_recomendacao.filtros_utilizados IS 'JSON com filtros aplicados na busca';
COMMENT ON COLUMN historico_busca_recomendacao.resultado_ids      IS 'Array JSON com IDs de produto_saude recomendados nesta sessão';

-- feedback_usuario — Sistema interno
CREATE TABLE feedback_usuario (
    id               bigint   GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_historico     bigint   NOT NULL REFERENCES historico_busca_recomendacao(id),
    id_produto_saude bigint   NOT NULL REFERENCES produto_saude(id),
    nota             smallint NOT NULL,
    comentario       text,
    util             boolean,
    created_at       timestamptz DEFAULT now(),

    CONSTRAINT chk_feedback_nota CHECK (nota BETWEEN 1 AND 5)
);

COMMENT ON TABLE feedback_usuario IS 'Feedback do usuário sobre planos recomendados';

-- =============================================================================
-- FASE 5: ÍNDICES PARA CONSULTAS MAIS PROVÁVEIS
-- =============================================================================

CREATE INDEX idx_market_share_municipio_serie  ON market_share (id_municipio, id_serie_mensal);
CREATE INDEX idx_market_share_operadora        ON market_share (id_operadora);
CREATE INDEX idx_preco_produto_serie           ON preco_faixa_etaria (id_produto_saude, id_serie_mensal);
CREATE INDEX idx_abrangencia_municipio         ON abrangencia_plano (id_municipio);
CREATE INDEX idx_historico_usuario             ON historico_busca_recomendacao (id_usuario);
CREATE INDEX idx_historico_municipio           ON historico_busca_recomendacao (id_municipio);
CREATE INDEX idx_feedback_historico            ON feedback_usuario (id_historico);
CREATE INDEX idx_feedback_produto              ON feedback_usuario (id_produto_saude);
CREATE INDEX idx_produto_operadora             ON produto_saude (id_operadora);
CREATE INDEX idx_produto_ativo_tipo            ON produto_saude (ativo, tipo_contratacao);
CREATE INDEX idx_rede_cred_produto_municipio   ON rede_credenciada_sintetica (id_produto_saude, id_municipio);
CREATE INDEX idx_rede_cred_municipio_tipo      ON rede_credenciada_sintetica (id_municipio, tipo_servico);
CREATE INDEX idx_perfil_saude_municipio        ON perfil_saude_publica (id_municipio);
CREATE INDEX idx_municipio_estado              ON municipio (id_estado);

-- =============================================================================
-- Modelo legado; extensões de integridade abaixo
-- =============================================================================


-- Existing data is preserved. Invalid legacy data makes this atomic migration fail.
CREATE TABLE dataset_carga (
 nome text PRIMARY KEY, fonte text NOT NULL, sintetico boolean NOT NULL,
 atualizado_em timestamptz NOT NULL DEFAULT now(), notas text NOT NULL DEFAULT ''
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['estado','municipio','operadora','produto_saude','market_share','perfil_saude_publica'] LOOP
   EXECUTE format('ALTER TABLE %I ADD COLUMN fonte text NOT NULL DEFAULT ''não informada'', ADD COLUMN sintetico boolean NOT NULL DEFAULT true',t);
 END LOOP;
END $$;
ALTER TABLE estado ADD CONSTRAINT estado_codigo_formato CHECK(codigo_ibge ~ '^[0-9]{2}$');
ALTER TABLE municipio ADD CONSTRAINT municipio_codigo_formato CHECK(codigo_ibge ~ '^[0-9]{7}$'),
 ADD CONSTRAINT municipio_lat CHECK(latitude BETWEEN -90 AND 90),
 ADD CONSTRAINT municipio_lon CHECK(longitude BETWEEN -180 AND 180),
 ADD CONSTRAINT municipio_id_estado_unique UNIQUE(id,id_estado);
ALTER TABLE serie_temporal_anual ADD CONSTRAINT serie_id_ano_unique UNIQUE(id,ano);
ALTER TABLE serie_temporal_mensal ADD CONSTRAINT mensal_ano_fk
 FOREIGN KEY(id_serie_anual,ano) REFERENCES serie_temporal_anual(id,ano),
 ADD CONSTRAINT mensal_competencia CHECK(competencia=ano::text||'-'||lpad(mes::text,2,'0'));
ALTER TABLE market_share ADD CONSTRAINT market_ben_nonnegative CHECK(total_beneficiarios>=0),
 ADD CONSTRAINT market_pct_range CHECK(percentual_market_share BETWEEN 0 AND 1);
ALTER TABLE preco_faixa_etaria ADD CONSTRAINT preco_nonnegative CHECK(valor_mensalidade>=0);
ALTER TABLE produto_saude ADD CONSTRAINT plano_datas CHECK(data_fim_venda IS NULL OR data_inicio_venda IS NULL OR data_fim_venda>=data_inicio_venda);
ALTER TABLE rede_credenciada_sintetica ADD CONSTRAINT rede_quantidade CHECK(quantidade_estimada>=0);
ALTER TABLE perfil_saude_publica ADD CONSTRAINT perfil_pop CHECK(populacao_estimada>=0),
 ADD CONSTRAINT perfil_idh CHECK(idh BETWEEN 0 AND 1),
 ADD CONSTRAINT perfil_cob CHECK(taxa_cobertura_plano_saude BETWEEN 0 AND 1),
 ADD CONSTRAINT perfil_renda CHECK(renda_per_capita>=0),
 ADD CONSTRAINT perfil_gini CHECK(indice_gini BETWEEN 0 AND 1),
 ADD CONSTRAINT perfil_mortalidade CHECK(taxa_mortalidade_infantil>=0);
ALTER TABLE historico_busca_recomendacao ADD CONSTRAINT filtros_object CHECK(jsonb_typeof(filtros_utilizados)='object'),
 ADD CONSTRAINT resultados_array CHECK(jsonb_typeof(resultado_ids)='array');
CREATE TABLE historico_produto (
 id_historico bigint NOT NULL REFERENCES historico_busca_recomendacao(id),
 id_produto_saude bigint NOT NULL REFERENCES produto_saude(id),
 PRIMARY KEY(id_historico,id_produto_saude)
);
-- Historical snapshots remain in JSON for compatibility. Valid references get a FK-backed association.
INSERT INTO historico_produto
 SELECT DISTINCT h.id,p.id FROM historico_busca_recomendacao h
 CROSS JOIN LATERAL jsonb_array_elements_text(h.resultado_ids) x(value)
 JOIN produto_saude p ON p.id::text=x.value ON CONFLICT DO NOTHING;
-- NOT VALID preserves legacy feedback; every new feedback must reference a recommended product.
ALTER TABLE feedback_usuario ADD CONSTRAINT feedback_recommended_fk
 FOREIGN KEY(id_historico,id_produto_saude) REFERENCES historico_produto(id_historico,id_produto_saude) NOT VALID;
CREATE TABLE indicador_saude (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 id_estado bigint NOT NULL REFERENCES estado(id),
 id_municipio bigint,
 metrica text NOT NULL CHECK(metrica IN ('vacina','alertas','cob_aps','leitos','prof','estab')),
 competencia varchar(7) NOT NULL CHECK(competencia ~ '^20[0-9]{2}-(0[1-9]|1[0-2])$'),
 valor numeric NOT NULL CHECK(valor>=0),
 unidade text NOT NULL,
 numerador numeric CHECK(numerador>=0), denominador numeric CHECK(denominador>0),
 fonte text NOT NULL, sintetico boolean NOT NULL DEFAULT true,
 extraido_em timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(id_municipio,id_estado) REFERENCES municipio(id,id_estado),
 CHECK(metrica NOT IN ('vacina','cob_aps') OR valor<=100),
 CHECK((metrica IN ('vacina','cob_aps') AND unidade='%') OR
       (metrica='prof' AND unidade='por 1.000 habitantes') OR
       (metrica IN ('alertas','leitos','estab') AND unidade='quantidade')),
 UNIQUE NULLS NOT DISTINCT(id_estado,id_municipio,metrica,competencia)
);
CREATE INDEX market_period_territory ON market_share(id_serie_mensal,id_municipio);
CREATE INDEX perfil_period_territory ON perfil_saude_publica(id_serie_anual,id_municipio);
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
 BEGIN NEW.updated_at=now(); RETURN NEW; END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['operadora','produto_saude','rede_credenciada_sintetica','usuario'] LOOP
  EXECUTE format('CREATE TRIGGER touch_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION touch_updated_at()',t);
 END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS schema_migrations(name text PRIMARY KEY,applied_at timestamptz NOT NULL DEFAULT now());
INSERT INTO schema_migrations(name) VALUES('001_integrity.sql') ON CONFLICT DO NOTHING;
