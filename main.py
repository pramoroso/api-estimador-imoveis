"""API Estimador de Imóveis.

Gera imóveis comparáveis (dados simulados) para uma localidade e estima o valor
de mercado de um imóvel a partir desses comparáveis.

Os dados são SIMULADOS, porém determinísticos: a mesma localidade sempre gera
os mesmos imóveis e o mesmo preço médio por m², o que torna as respostas
consistentes entre chamadas e permite testes automatizados.
"""

import hashlib
import os
import random
import statistics
import unicodedata
from enum import Enum
from typing import List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

__version__ = "2.0.0"

ESTADOS = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia",
    "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}

# Faixa de preço por m² construído (R$) usada na simulação, por tipo de imóvel.
FAIXA_PRECO_M2 = {
    "apartamento": (4_000, 14_000),
    "casa": (3_000, 10_000),
}
# Valor do m² de terreno como fração do m² construído (somente casas).
FATOR_TERRENO = 0.35


class TipoImovel(str, Enum):
    apartamento = "apartamento"
    casa = "casa"


class Imovel(BaseModel):
    tipo: TipoImovel
    estado: str
    cidade: str
    bairro: str
    area_construida: int = Field(description="Área construída em m²")
    area_terreno: Optional[int] = Field(description="Área do terreno em m² (somente casas)")
    vagas: int
    valor: int = Field(description="Valor do imóvel em R$")
    preco_m2: int = Field(description="Valor dividido pela área construída (R$/m²)")


class ResultadoBusca(BaseModel):
    total: int
    preco_m2_medio: int
    resultados: List[Imovel]
    aviso: str


class Faixa(BaseModel):
    minimo: int
    maximo: int


class Estimativa(BaseModel):
    tipo: TipoImovel
    estado: str
    cidade: str
    bairro: str
    area_construida: int
    area_terreno: Optional[int]
    vagas: int
    valor_estimado: int
    faixa: Faixa
    preco_m2_referencia: int
    amostras: int
    aviso: str


AVISO = "Dados simulados para fins de demonstração; não representam ofertas reais."

# ---------------------------------------------------------------------------
# Aplicação
# ---------------------------------------------------------------------------

app = FastAPI(
    title="API Estimador de Imóveis",
    version=__version__,
    description="Busca de imóveis comparáveis e estimativa de valor (dados simulados).",
)

# CORS: por padrão libera qualquer origem SEM credenciais (combinação válida).
# Para restringir, defina CORS_ORIGINS="https://meusite.com,https://outro.com".
_origens = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origens,
    allow_credentials="*" not in _origens,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Regras de negócio
# ---------------------------------------------------------------------------

def _normalizar(texto: str) -> str:
    """Remove acentos, espaços extras e caixa para comparar localidades."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def _limpar(texto: str) -> str:
    return " ".join(texto.split())


def _rng(*partes: str) -> random.Random:
    """Gerador aleatório determinístico a partir da localidade."""
    chave = "|".join(_normalizar(p) for p in partes)
    semente = int(hashlib.sha256(chave.encode()).hexdigest()[:16], 16)
    return random.Random(semente)


def preco_m2_base(tipo: TipoImovel, estado: str, cidade: str, bairro: str) -> int:
    minimo, maximo = FAIXA_PRECO_M2[tipo.value]
    return _rng("m2", tipo.value, estado, cidade, bairro).randint(minimo, maximo)


def gerar_imoveis(
    tipo: TipoImovel, estado: str, cidade: str, bairro: str, quantidade: int
) -> List[Imovel]:
    base = preco_m2_base(tipo, estado, cidade, bairro)
    rng = _rng("imoveis", tipo.value, estado, cidade, bairro)
    imoveis = []
    for _ in range(quantidade):
        if tipo is TipoImovel.casa:
            area = rng.randint(70, 300)
            terreno = max(area, rng.randint(125, 500))
        else:
            area = rng.randint(40, 200)
            terreno = None
        vagas = rng.randint(0, 1) if area < 60 else rng.randint(1, 4)
        m2 = base * rng.uniform(0.85, 1.15)
        valor = area * m2 + (terreno or 0) * base * FATOR_TERRENO + vagas * base * 2
        valor = int(round(valor, -3))
        imoveis.append(
            Imovel(
                tipo=tipo,
                estado=estado,
                cidade=cidade,
                bairro=bairro,
                area_construida=area,
                area_terreno=terreno,
                vagas=vagas,
                valor=valor,
                preco_m2=round(valor / area),
            )
        )
    return imoveis


def estimar(
    tipo: TipoImovel,
    estado: str,
    cidade: str,
    bairro: str,
    area_construida: int,
    area_terreno: Optional[int],
    vagas: int,
) -> Estimativa:
    comparaveis = gerar_imoveis(tipo, estado, cidade, bairro, 30)
    base = preco_m2_base(tipo, estado, cidade, bairro)
    # m² "limpo" dos comparáveis: desconta terreno e vagas para comparar só a construção.
    m2_construcao = [
        (i.valor - (i.area_terreno or 0) * base * FATOR_TERRENO - i.vagas * base * 2)
        / i.area_construida
        for i in comparaveis
    ]
    m2_ref = statistics.median(m2_construcao)
    q1, _, q3 = statistics.quantiles(m2_construcao, n=4)

    terreno = area_terreno if tipo is TipoImovel.casa else None
    extras = (terreno or 0) * base * FATOR_TERRENO + vagas * base * 2

    def _valor(m2: float) -> int:
        return int(round(area_construida * m2 + extras, -3))

    return Estimativa(
        tipo=tipo,
        estado=estado,
        cidade=cidade,
        bairro=bairro,
        area_construida=area_construida,
        area_terreno=terreno,
        vagas=vagas,
        valor_estimado=_valor(m2_ref),
        faixa=Faixa(minimo=_valor(q1), maximo=_valor(q3)),
        preco_m2_referencia=round(m2_ref),
        amostras=len(comparaveis),
        aviso=AVISO,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

EstadoQ = Query(
    ..., min_length=1, max_length=60,
    description="UF (ex.: SP) ou nome do estado (ex.: São Paulo)",
)
CidadeQ = Query(..., min_length=1, max_length=80)
BairroQ = Query(..., min_length=1, max_length=80)


_UF_POR_NOME = {_normalizar(n): uf for uf, nome in ESTADOS.items() for n in (uf, nome)}


def _uf(estado: str) -> str:
    """Converte sigla ou nome do estado (com ou sem acento) para a UF.

    Texto não reconhecido é mantido como digitado, para não quebrar o frontend.
    """
    return _UF_POR_NOME.get(_normalizar(estado), _limpar(estado))


def _local(estado: str, cidade: str, bairro: str) -> Tuple[str, str, str]:
    estado, cidade, bairro = _uf(estado), _limpar(cidade), _limpar(bairro)
    if not (estado and cidade and bairro):
        raise HTTPException(status_code=422, detail="Informe estado, cidade e bairro.")
    return estado, cidade, bairro


@app.get("/", include_in_schema=False)
def raiz():
    return {"nome": app.title, "versao": __version__, "documentacao": "/docs"}


@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok", "versao": __version__}


@app.get("/buscar-imoveis/", response_model=ResultadoBusca, tags=["imoveis"])
def buscar_imoveis(
    tipo: TipoImovel = Query(..., description="apartamento ou casa"),
    estado: str = EstadoQ,
    cidade: str = CidadeQ,
    bairro: str = BairroQ,
    quantidade: int = Query(10, ge=1, le=50, description="Quantidade de imóveis"),
):
    """Lista imóveis comparáveis (simulados) para a localidade informada."""
    estado, cidade, bairro = _local(estado, cidade, bairro)
    imoveis = gerar_imoveis(tipo, estado, cidade, bairro, quantidade)
    return ResultadoBusca(
        total=len(imoveis),
        preco_m2_medio=round(statistics.mean(i.preco_m2 for i in imoveis)),
        resultados=imoveis,
        aviso=AVISO,
    )


@app.get("/estimar-valor/", response_model=Estimativa, tags=["imoveis"])
def estimar_valor(
    tipo: TipoImovel = Query(..., description="apartamento ou casa"),
    estado: str = EstadoQ,
    cidade: str = CidadeQ,
    bairro: str = BairroQ,
    area_construida: int = Query(..., ge=15, le=2000, description="Área construída em m²"),
    area_terreno: Optional[int] = Query(
        None, ge=20, le=20000, description="Área do terreno em m² (obrigatória para casa)"
    ),
    vagas: int = Query(1, ge=0, le=10),
):
    """Estima o valor de mercado do imóvel com base em comparáveis da localidade."""
    if tipo is TipoImovel.casa and area_terreno is None:
        raise HTTPException(status_code=422, detail="area_terreno é obrigatória para casa")
    estado, cidade, bairro = _local(estado, cidade, bairro)
    return estimar(tipo, estado, cidade, bairro, area_construida, area_terreno, vagas)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
