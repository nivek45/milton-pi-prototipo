-- ANS identifiers are retained verbatim. Geographic groups avoid expanding
-- national plans into millions of redundant plan/municipality pairs.
CREATE TABLE IF NOT EXISTS ans_plano (
 id bigint PRIMARY KEY, registro text NOT NULL, nome text NOT NULL,
 registro_operadora text NOT NULL, contratacao text NOT NULL,
 segmentacao text NOT NULL, abrangencia text NOT NULL, geo_id text,
 fator_moderador text NOT NULL, acomodacao text NOT NULL,
 situacao text NOT NULL, atualizado_em date NOT NULL
);
CREATE INDEX IF NOT EXISTS ans_plano_geo ON ans_plano(geo_id);
CREATE INDEX IF NOT EXISTS ans_plano_operadora ON ans_plano(registro_operadora);
CREATE TABLE IF NOT EXISTS ans_geografia (
 geo_id text NOT NULL, codigo_ibge varchar(7) NOT NULL REFERENCES municipio(codigo_ibge),
 PRIMARY KEY(geo_id,codigo_ibge)
);
CREATE INDEX IF NOT EXISTS ans_geografia_municipio ON ans_geografia(codigo_ibge,geo_id);
CREATE TABLE IF NOT EXISTS ans_geo_estado (
 geo_id text NOT NULL, uf varchar(2) NOT NULL REFERENCES estado(sigla),
 PRIMARY KEY(geo_id,uf)
);
CREATE TABLE IF NOT EXISTS ans_resumo (
 uf varchar(2) PRIMARY KEY REFERENCES estado(sigla), planos integer NOT NULL,
 operadoras integer NOT NULL
);
