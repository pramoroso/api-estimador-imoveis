# API Estimador de Imóveis

API em FastAPI que gera imóveis comparáveis para uma localidade e estima o valor de mercado de um imóvel.

> **Importante:** os dados são **simulados** (não são ofertas reais). A simulação é determinística: a mesma localidade sempre devolve os mesmos imóveis e o mesmo preço/m², e os valores são proporcionais à área, ao terreno e às vagas.

## Arquitetura

```
Frontend (GitHub Pages)                         API (Render)
pramoroso.github.io/estimador-imovel  ──HTTP──▶  api-estimador-imoveis.onrender.com
repo: pramoroso/estimador-imovel                 repo: este (main.py)
```

O GitHub Pages hospeda apenas arquivos estáticos; o Python roda no Render, que faz o deploy automático a partir do branch `main` deste repositório.

### Deploy no Render

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Versão do Python:** definida no arquivo `.python-version`
- **Health check path:** `/health`
- No plano gratuito o serviço "dorme" após ~15 min sem uso; a primeira chamada pode levar até 1 minuto.

## Como executar localmente

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Documentação interativa: http://localhost:8000/docs

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Verificação de saúde (monitoramento/deploy) |
| GET | `/buscar-imoveis/` | Lista imóveis comparáveis da localidade |
| GET | `/estimar-valor/` | Estima o valor de um imóvel específico |

### `/buscar-imoveis/`

| Parâmetro | Obrigatório | Descrição |
|---|---|---|
| `tipo` | sim | `apartamento` ou `casa` |
| `estado` | sim | UF (`SP`) ou nome (`São Paulo`); texto não reconhecido é aceito como digitado |
| `cidade` | sim | Nome da cidade |
| `bairro` | sim | Nome do bairro |
| `quantidade` | não | 1 a 50 (padrão 10) |

Exemplo: `/buscar-imoveis/?tipo=casa&estado=SP&cidade=Campinas&bairro=Cambuí`

Resposta: `total`, `preco_m2_medio`, `resultados[]` (mesmos campos da versão anterior + `preco_m2`) e `aviso`.

### `/estimar-valor/`

Mesmos parâmetros de localidade, mais `area_construida` (m²), `area_terreno` (m², obrigatória para casa) e `vagas` (padrão 1).

Exemplo: `/estimar-valor/?tipo=apartamento&estado=SP&cidade=São Paulo&bairro=Moema&area_construida=80&vagas=1`

Resposta: `valor_estimado`, `faixa.minimo` / `faixa.maximo` (quartis dos comparáveis), `preco_m2_referencia` e `amostras`.

## Configuração

| Variável | Padrão | Descrição |
|---|---|---|
| `CORS_ORIGINS` | `*` | Origens permitidas, separadas por vírgula (ex.: `https://meuapp.com`) |
| `PORT` | `8000` | Porta usada ao executar `python main.py` |

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```
