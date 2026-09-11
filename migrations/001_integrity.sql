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
