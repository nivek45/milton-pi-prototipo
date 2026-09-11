"""Keep each fact at its native grain before aggregation."""
PERIOD = """
WITH period AS (
 SELECT id, competencia FROM serie_temporal_mensal
 WHERE competencia = COALESCE(%(competencia)s,
   (SELECT MAX(s.competencia) FROM market_share f JOIN serie_temporal_mensal s ON s.id=f.id_serie_mensal))
), year AS (
 SELECT id, ano FROM serie_temporal_anual
 WHERE ano = COALESCE(%(ano)s,
   (SELECT MAX(s.ano) FROM perfil_saude_publica f JOIN serie_temporal_anual s ON s.id=f.id_serie_anual))
), ms AS (
 SELECT f.* FROM market_share f JOIN period ON period.id=f.id_serie_mensal
), profiles AS (
 SELECT f.* FROM perfil_saude_publica f JOIN year ON year.id=f.id_serie_anual
)
"""
SUMMARY = PERIOD + """
, by_operator AS (
 SELECT m.id_estado, f.id_operadora, SUM(f.total_beneficiarios) AS ben,
        BOOL_OR(f.sintetico) AS sintetico
 FROM ms f JOIN municipio m ON m.id=f.id_municipio
 GROUP BY m.id_estado, f.id_operadora
), state_market AS (
 SELECT id_estado, SUM(ben) AS ben, COUNT(*) AS op,
        MAX(ben)*100.0/NULLIF(SUM(ben),0) AS mkt_share,
        BOOL_OR(sintetico) AS sintetico
 FROM by_operator GROUP BY id_estado
), state_profiles AS (
 SELECT m.id_estado, SUM(p.populacao_estimada) AS pop,
 SUM(p.taxa_cobertura_plano_saude*p.populacao_estimada)*100.0 /
 NULLIF(SUM(p.populacao_estimada) FILTER (WHERE p.taxa_cobertura_plano_saude IS NOT NULL),0) AS cob,
 AVG(p.idh) AS idh,
 SUM(p.renda_per_capita*p.populacao_estimada) /
 NULLIF(SUM(p.populacao_estimada) FILTER (WHERE p.renda_per_capita IS NOT NULL),0) AS renda,
 COUNT(*) AS municipios_perfil, BOOL_OR(p.sintetico) AS sintetico
 FROM profiles p JOIN municipio m ON m.id=p.id_municipio GROUP BY m.id_estado
), municipality_counts AS (
 SELECT id_estado, COUNT(*) AS mun FROM municipio GROUP BY id_estado
)
SELECT e.sigla AS uf, e.codigo_ibge, e.nome, e.regiao AS reg,
       a.ben, a.op, a.mkt_share, p.cob, p.idh, p.renda, p.pop,
       COALESCE(c.mun,0) AS mun, COALESCE(p.municipios_perfil,0) AS municipios_perfil,
       COALESCE(a.sintetico,false) OR COALESCE(p.sintetico,false) OR e.sintetico AS sintetico,
       (SELECT competencia FROM period) AS competencia, (SELECT ano FROM year) AS ano
FROM estado e LEFT JOIN state_market a ON a.id_estado=e.id
LEFT JOIN state_profiles p ON p.id_estado=e.id
LEFT JOIN municipality_counts c ON c.id_estado=e.id ORDER BY e.sigla
"""
NATIONAL = PERIOD + """
SELECT (SELECT SUM(total_beneficiarios) FROM ms) AS ben,
 (SELECT NULLIF(COUNT(DISTINCT id_operadora),0) FROM ms) AS op,
 (SELECT COUNT(*) FROM municipio) AS mun,
 (SELECT SUM(populacao_estimada) FROM profiles) AS pop,
 (SELECT SUM(taxa_cobertura_plano_saude*populacao_estimada)*100.0 /
 NULLIF(SUM(populacao_estimada) FILTER(WHERE taxa_cobertura_plano_saude IS NOT NULL),0) FROM profiles) AS cob,
 (SELECT AVG(idh) FROM profiles) AS idh,
 (SELECT COUNT(*) FROM profiles) AS municipios_perfil
"""
OPERATORS = PERIOD + """
, territory AS (
 SELECT m.id FROM municipio m JOIN estado e ON e.id=m.id_estado
 WHERE (%(uf)s IS NULL OR e.sigla=%(uf)s)
 AND (%(municipio)s IS NULL OR m.codigo_ibge=%(municipio)s)
), market AS (
 SELECT id_operadora, SUM(total_beneficiarios) AS ben, BOOL_OR(sintetico) AS sintetico
 FROM ms WHERE id_municipio IN (SELECT id FROM territory) GROUP BY id_operadora
), plans AS (
 SELECT id_operadora, COUNT(*) AS pl FROM produto_saude WHERE ativo GROUP BY id_operadora
)
SELECT o.id, o.registro_ans, COALESCE(o.nome_fantasia,o.razao_social) AS nm,
 o.modalidade AS mod, o.uf_sede AS uf, o.situacao, a.ben,
 a.ben*100.0/NULLIF(SUM(a.ben) OVER(),0) AS pct, COALESCE(p.pl,0) AS pl,
 (o.sintetico OR COALESCE(a.sintetico,false)) AS sintetico,
 (SELECT competencia FROM period) AS competencia
FROM operadora o LEFT JOIN market a ON a.id_operadora=o.id
LEFT JOIN plans p ON p.id_operadora=o.id
WHERE (%(uf)s IS NULL AND %(municipio)s IS NULL OR a.id_operadora IS NOT NULL)
"""
PLANS = """
SELECT p.id,p.nome_plano AS nm,COALESCE(o.nome_fantasia,o.razao_social) AS op,
 p.tipo_contratacao AS tipo,p.segmentacao AS seg,p.cobertura AS cob,
 p.possui_copart AS copart,COUNT(a.id_municipio) AS mun,
 p.sintetico OR o.sintetico AS sintetico
FROM produto_saude p JOIN operadora o ON o.id=p.id_operadora
LEFT JOIN abrangencia_plano a ON a.id_produto_saude=p.id
WHERE p.ativo AND (
 (%(uf)s IS NULL AND %(municipio)s IS NULL) OR EXISTS (
 SELECT 1 FROM abrangencia_plano x JOIN municipio m ON m.id=x.id_municipio
 JOIN estado e ON e.id=m.id_estado WHERE x.id_produto_saude=p.id
 AND (%(uf)s IS NULL OR e.sigla=%(uf)s)
 AND (%(municipio)s IS NULL OR m.codigo_ibge=%(municipio)s)))
GROUP BY p.id,o.id
"""
PROFILES = PERIOD + """
SELECT m.id,m.codigo_ibge,m.nome AS m,e.sigla AS uf,p.populacao_estimada AS pop,
 p.idh,p.taxa_cobertura_plano_saude*100 AS cob,p.renda_per_capita AS renda,
 p.indice_gini AS gini,p.sintetico,p.fonte,(SELECT ano FROM year) AS ano
FROM profiles p JOIN municipio m ON m.id=p.id_municipio
JOIN estado e ON e.id=m.id_estado
WHERE (%(uf)s IS NULL OR e.sigla=%(uf)s)
AND (%(municipio)s IS NULL OR m.codigo_ibge=%(municipio)s)
"""
