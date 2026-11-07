import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)
LOCAL = {"estado": "SP", "cidade": "São Paulo", "bairro": "Moema"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.parametrize("tipo", ["apartamento", "casa"])
def test_buscar_imoveis_formato(tipo):
    r = client.get("/buscar-imoveis/", params={"tipo": tipo, **LOCAL})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == len(body["resultados"]) == 10
    for imovel in body["resultados"]:
        assert {"tipo", "estado", "cidade", "bairro", "area_construida",
                "area_terreno", "vagas", "valor"} <= imovel.keys()
        assert imovel["valor"] > 0
        if tipo == "apartamento":
            assert imovel["area_terreno"] is None
        else:
            assert imovel["area_terreno"] >= imovel["area_construida"]


def test_buscar_imoveis_deterministico_e_normalizado():
    a = client.get("/buscar-imoveis/", params={"tipo": "casa", **LOCAL}).json()
    b = client.get("/buscar-imoveis/", params={
        "tipo": "casa", "estado": "São Paulo", "cidade": "sao  paulo", "bairro": "MOEMA",
    }).json()
    assert [i["valor"] for i in a["resultados"]] == [i["valor"] for i in b["resultados"]]


def test_quantidade():
    r = client.get("/buscar-imoveis/", params={"tipo": "casa", "quantidade": 3, **LOCAL})
    assert r.json()["total"] == 3
    assert client.get("/buscar-imoveis/",
                      params={"tipo": "casa", "quantidade": 999, **LOCAL}).status_code == 422


@pytest.mark.parametrize("params", [
    {"tipo": "terreno", **LOCAL},
    {"tipo": "casa", **{**LOCAL, "bairro": "   "}},
    {"tipo": "casa", "estado": "SP", "cidade": "São Paulo"},
])
def test_validacao(params):
    assert client.get("/buscar-imoveis/", params=params).status_code == 422


def test_estimar_valor_apartamento():
    r = client.get("/estimar-valor/", params={
        "tipo": "apartamento", "area_construida": 80, "vagas": 1, **LOCAL})
    assert r.status_code == 200
    e = r.json()
    assert e["faixa"]["minimo"] <= e["valor_estimado"] <= e["faixa"]["maximo"]
    assert e["area_terreno"] is None


def test_estimar_valor_cresce_com_area():
    def valor(area):
        return client.get("/estimar-valor/", params={
            "tipo": "apartamento", "area_construida": area, **LOCAL}).json()["valor_estimado"]
    assert valor(120) > valor(60)


def test_estimar_casa_exige_terreno():
    params = {"tipo": "casa", "area_construida": 150, **LOCAL}
    assert client.get("/estimar-valor/", params=params).status_code == 422
    r = client.get("/estimar-valor/", params={**params, "area_terreno": 250})
    assert r.status_code == 200


def test_cors_sem_credenciais_com_curinga():
    r = client.get("/health", headers={"Origin": "http://exemplo.com"})
    assert r.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in r.headers


def test_estado_nao_reconhecido_e_aceito():
    """O frontend envia texto livre; a API não deve recusar estados digitados diferente."""
    r = client.get("/buscar-imoveis/", params={**LOCAL, "tipo": "casa", "estado": "Sampa"})
    assert r.status_code == 200
    assert r.json()["resultados"][0]["estado"] == "Sampa"


def test_chamada_identica_ao_frontend():
    """Mesma URL montada pelo index.html do GitHub Pages."""
    r = client.get("/buscar-imoveis/?tipo=casa&estado=sp&cidade=Campinas&bairro=Cambuí")
    assert r.status_code == 200
    for i in r.json()["resultados"]:
        assert isinstance(i["valor"], int) and i["vagas"] >= 0
