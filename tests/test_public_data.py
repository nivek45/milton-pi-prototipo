"""Public-source contracts, exercised offline without the catalog database."""
import pytest
from backend import public_data
from backend.routes import app


@pytest.fixture
def client():
    public_data.municipal_mesh.cache_clear()
    public_data.facility_types.cache_clear()
    return app.test_client()


def test_cep_returns_only_the_municipality(client, monkeypatch):
    monkeypatch.setattr(public_data, 'upstream', lambda *a, **kw: {
        'ibge':'3550308', 'uf':'SP', 'localidade':'São Paulo', 'logradouro':'Praça da Sé'})
    assert client.get('/api/publico/cep/01001000').json == {
        'items':[{'codigo_ibge':'3550308', 'uf':'SP', 'nome':'São Paulo'}]}
    assert client.get('/api/publico/cep/12345').status_code == 400
    monkeypatch.setattr(public_data, 'upstream', lambda *a, **kw: {'erro':'true'})
    assert client.get('/api/publico/cep/00000000').status_code == 404


def test_mesh_joins_by_code_and_caches_success(client, monkeypatch):
    calls = []

    def upstream(url, source, **params):
        calls.append(url)
        if '/v3/' in url:
            assert params['intrarregiao'] == 'municipio'
            return {'features':[{'properties':{'codarea':'2800308'}, 'geometry':{
                'type':'Polygon', 'coordinates':[[[0,0],[0,1],[1,0],[0,0]]]}}]}
        return [{'id':2800308, 'nome':'Aracaju'}]

    monkeypatch.setattr(public_data, 'upstream', upstream)
    for _ in range(2):
        response = client.get('/api/publico/malhas/SE')
        assert response.json['features'][0]['properties'] == {'nome':'Aracaju','code':'2800308'}
    assert len(calls) == 2
    assert client.get('/api/publico/malhas/XY').status_code == 400


def test_cnes_uses_six_digits_and_lookahead_without_skipping_a_unit(client, monkeypatch):
    def upstream(url, source, **params):
        if url.endswith('tipounidades'):
            return {'tipos_unidade':[{'codigo_tipo_unidade':2,'descricao_tipo_unidade':'UBS'}]}
        assert params['codigo_municipio'] == '280030'
        assert params['limit'] == 20
        start = params['offset']
        return {'estabelecimentos':[{'codigo_cnes':i,'nome_fantasia':'Unidade',
                                     'codigo_municipio':280030,'codigo_tipo_unidade':2,
                                     'latitude_estabelecimento_decimo_grau':'',
                                     'longitude_estabelecimento_decimo_grau':None}
                                    for i in range(start, min(start + 20, 22))]}

    monkeypatch.setattr(public_data, 'upstream', upstream)
    first = client.get('/api/publico/unidades/2800308').json
    second = client.get('/api/publico/unidades/2800308?page=2').json
    assert first['has_next'] and not second['has_next']
    items = first['items'] + second['items']
    assert [int(item['cnes']) for item in items] == list(range(22))
    assert all(item['lat'] is None and item['tipo'] == 'UBS' for item in items)
    assert client.get('/api/publico/unidades/2800308?page=0').status_code == 400


def test_cnes_rejects_rows_from_another_city(client, monkeypatch):
    monkeypatch.setattr(public_data, 'upstream', lambda *a, **kw: {
        'estabelecimentos':[{'codigo_municipio':355030}]})
    assert client.get('/api/publico/unidades/2800308').status_code == 502


def test_upstream_timeout_is_retryable(client, monkeypatch):
    def timeout(*args, **kwargs):
        raise public_data.requests.Timeout()
    monkeypatch.setattr(public_data.requests, 'get', timeout)
    response = client.get('/api/publico/malhas/SE')
    assert response.status_code == 503
    assert 'IBGE' in response.json['error']

