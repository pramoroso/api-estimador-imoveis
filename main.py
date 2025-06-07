from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/buscar-imoveis/")
def buscar_imoveis(
    tipo: str = Query(..., enum=["apartamento", "casa"]),
    estado: str = Query(...),
    cidade: str = Query(...),
    bairro: str = Query(...)
):
    imoveis = []
    for i in range(10):
        imovel = {
            "tipo": tipo,
            "estado": estado,
            "cidade": cidade,
            "bairro": bairro,
            "area_construida": random.randint(50, 250),
            "area_terreno": random.randint(100, 400) if tipo == "casa" else None,
            "vagas": random.randint(1, 4),
            "valor": random.randint(200000, 1200000)
        }
        imoveis.append(imovel)
    return {"resultados": imoveis}