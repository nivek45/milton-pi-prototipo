"""Read-only adapters for the public sources used by the territory explorer."""
from datetime import date
from functools import lru_cache
import math
import re

import requests
from flask import Blueprint, abort, jsonify, request

bp = Blueprint('public_data', __name__, url_prefix='/api/publico')
UFS = set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())
IBGE = 'https://servicodados.ibge.gov.br/api'
CNES = 'https://apidadosabertos.saude.gov.br/cnes'
# The CNES caps each response at 20. Reserve one row for the next-page check.
PAGE_SIZE = 19


def upstream(url, source, **params):
    try:
        response = requests.get(url, params=params, timeout=(3, 7))
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        abort(503, f'{source} indisponível no momento. Tente novamente.')


def rows(payload, key, source):
    values = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(values, list):
        abort(502, f'Resposta inválida de {source}.')
    return values


@bp.get('/cep/<cep>')
def resolve_cep(cep):
    if not re.fullmatch('[0-9]{8}', cep):
        abort(400, 'Informe um CEP de oito dígitos.')
    data = upstream(f'https://viacep.com.br/ws/{cep}/json/', 'ViaCEP')
    if not isinstance(data, dict):
        abort(502, 'Resposta inválida do ViaCEP.')
    if data.get('erro'):
        abort(404, 'CEP não encontrado. Confira os dígitos ou busque pelo nome da cidade.')
    code = str(data.get('ibge', ''))
    if not re.fullmatch('[0-9]{7}', code) or data.get('uf') not in UFS or not data.get('localidade'):
        abort(502, 'O ViaCEP não identificou um município para este CEP.')
    return jsonify(items=[dict(codigo_ibge=code, nome=data['localidade'], uf=data['uf'])])


@lru_cache(maxsize=54)
def municipal_mesh(uf, day):
    geometry = upstream(f'{IBGE}/v3/malhas/estados/{uf}', 'IBGE', intrarregiao='municipio',
                        qualidade='minima', formato='application/vnd.geo+json')
    cities = upstream(f'{IBGE}/v1/localidades/estados/{uf}/municipios', 'IBGE')
    if not isinstance(cities, list):
        abort(502, 'Lista de municípios inválida no IBGE.')
    names = {str(city['id']): city['nome'] for city in cities}
    features = []
    for feature in rows(geometry, 'features', 'IBGE'):
        code = str(feature['properties']['codarea'])
        shape = feature['geometry']
        if shape['type'] in ('Polygon', 'MultiPolygon') and re.fullmatch('[0-9]{7}', code):
            features.append(dict(type='Feature', geometry=shape,
                                 properties=dict(code=code, nome=names.get(code, f'Município {code}'))))
    if not features:
        abort(502, 'O IBGE não retornou limites municipais para esta UF.')
    return dict(type='FeatureCollection', features=features)


@bp.get('/malhas/<uf>')
def mesh(uf):
    if uf not in UFS:
        abort(400, 'UF inválida.')
    return jsonify(municipal_mesh(uf, date.today()))


@lru_cache(maxsize=2)
def facility_types(day):
    payload = upstream(f'{CNES}/tipounidades', 'CNES')
    return {str(row['codigo_tipo_unidade']): row['descricao_tipo_unidade']
            for row in rows(payload, 'tipos_unidade', 'CNES')}


def coordinate(value, limit):
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) and abs(number) <= limit else None


@bp.get('/unidades/<code>')
def facilities(code):
    if not re.fullmatch('[0-9]{7}', code):
        abort(400, 'Código IBGE inválido.')
    page = request.args.get('page', '1')
    if not re.fullmatch('[1-9][0-9]{0,3}', page):
        abort(400, 'Página inválida.')
    page = int(page)
    # CNES uses the six-digit DATASUS municipality code (without the IBGE check digit).
    payload = upstream(f'{CNES}/estabelecimentos', 'CNES', codigo_municipio=code[:6],
                       limit=PAGE_SIZE + 1, offset=(page - 1) * PAGE_SIZE)
    records = rows(payload, 'estabelecimentos', 'CNES')
    if any(str(row.get('codigo_municipio')) != code[:6] for row in records):
        abort(502, 'O CNES retornou dados fora do município solicitado.')
    types = facility_types(date.today()) if records else {}
    items = []
    for row in records[:PAGE_SIZE]:
        kind = str(row.get('codigo_tipo_unidade', ''))
        items.append(dict(cnes=str(row['codigo_cnes']).zfill(7),
                          nome=row.get('nome_fantasia') or row.get('nome_razao_social') or 'Sem nome cadastrado',
                          tipo=types.get(kind, f'Tipo CNES {kind}'),
                          lat=coordinate(row.get('latitude_estabelecimento_decimo_grau'), 90),
                          lon=coordinate(row.get('longitude_estabelecimento_decimo_grau'), 180)))
    return jsonify(items=items, page=page, has_next=len(records) > PAGE_SIZE)

