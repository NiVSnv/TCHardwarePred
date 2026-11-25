"""
Busca automática de pontuação no 3DMark a partir do NOME digitado pelo
usuário (ex: "RTX 4070" ou "Ryzen 7 5800X"), sem ele precisar saber o
valor numérico de antemão.

Funciona em dois passos, encadeando dois endpoints públicos e sem
autenticação do site 3dmark.com/search:

    1) Busca por nome (autocomplete):
       https://www.3dmark.com/proxycon/ajax/search/gpuname?term=...
       https://www.3dmark.com/proxycon/ajax/search/cpuname?term=...
       -> retorna os componentes cujo nome bate com o termo digitado,
          cada um com seu ID interno no 3DMark.

    2) Pontuação média do componente encontrado:
       reaproveita o mesmo endpoint de comparação usado em
       coleta_3dmark.py (proxycon/ajax/newsearch), mas consultando só
       o ID da CPU OU só o da GPU (o outro campo fica vazio), para
       pegar a média de todos os resultados públicos que usaram aquele
       componente, independente do par.

ATENÇÃO: nenhum desses dois endpoints é documentado oficialmente pela UL
Solutions -- foram descobertos por engenharia reversa do próprio site de
busca pública (e por scripts da comunidade). Podem mudar de formato sem
aviso. Se `buscar_nomes()` parar de encontrar resultados, rode este
arquivo diretamente (`python -m integrations.busca_3dmark "RTX 4070"
gpu`) para inspecionar o JSON bruto retornado e ajustar o parsing.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

import requests

HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "referer": "https://www.3dmark.com/search",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "x-requested-with": "XMLHttpRequest",
}

URL_BUSCA_NOME = "https://www.3dmark.com/proxycon/ajax/search/{tipo}name"
URL_PONTUACAO = "https://www.3dmark.com/proxycon/ajax/newsearch"

_TIPO_PARAM = {"CPU": "cpu", "GPU": "gpu"}


@dataclass
class Candidato:
    tipo: str
    id: int
    nome: str
    pontuacao: float | None = None   # preenchida por pontuacao_media()
    amostras: int = 0


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def buscar_nomes(tipo: str, termo: str, session: requests.Session | None = None) -> list[Candidato]:
    """
    Busca componentes cujo nome contém `termo` (autocomplete do 3DMark).
    tipo: "CPU" ou "GPU"
    """
    tipo = tipo.upper()
    if tipo not in _TIPO_PARAM:
        raise ValueError("tipo deve ser 'CPU' ou 'GPU'")

    session = session or _session()
    url = URL_BUSCA_NOME.format(tipo=_TIPO_PARAM[tipo])
    resposta = session.get(url, params={"term": termo}, timeout=15)
    resposta.raise_for_status()
    dados = resposta.json()

    candidatos: list[Candidato] = []
    # O formato exato deste endpoint não é documentado; tentamos as
    # variações mais comuns de autocomplete. Se nada bater, devolvemos
    # vazio e quem chamou pode inspecionar `dados` para ajustar aqui.
    itens = dados if isinstance(dados, list) else dados.get("results", dados.get("data", []))
    for item in itens:
        if isinstance(item, str):
            # autocomplete simples: lista de nomes, sem id -- não dá pra
            # consultar pontuação sem id, então pula.
            continue
        item_id = item.get("id") or item.get("Id") or item.get("value")
        item_nome = item.get("name") or item.get("Name") or item.get("label") or item.get("text")
        if item_id is not None and item_nome:
            candidatos.append(Candidato(tipo=tipo, id=int(item_id), nome=str(item_nome)))

    return candidatos


def _montar_url_pontuacao(tipo: str, componente_id: int) -> str:
    cpu_id = componente_id if tipo == "CPU" else ""
    gpu_id = componente_id if tipo == "GPU" else ""
    return (
        f"{URL_PONTUACAO}?test=spy%20P&cpuId={cpu_id}&gpuId={gpu_id}&gpuCount=1"
        "&gpuType=ALL&deviceType=ALL&storageModel=ALL&modelId=&showRamDisks=false"
        "&memoryChannels=0&country=&scoreType=overallScore&hofMode=false"
        "&showInvalidResults=false&freeParams=&minGpuCoreClock=&maxGpuCoreClock="
        "&minGpuMemClock=&maxGpuMemClock=&minCpuClock=&maxCpuClock="
    )


def pontuacao_media(candidato: Candidato, session: requests.Session | None = None) -> Candidato:
    """
    Preenche `pontuacao` e `amostras` do candidato consultando a média
    dos resultados públicos que usaram aquele componente (com qualquer
    parceiro de CPU/GPU).
    """
    session = session or _session()
    url = _montar_url_pontuacao(candidato.tipo, candidato.id)
    resposta = session.get(url, timeout=15)
    resposta.raise_for_status()
    dados = resposta.json()
    resultados = dados.get("results", [])

    if not resultados:
        candidato.pontuacao = None
        candidato.amostras = 0
        return candidato

    campo = "physicsScore" if candidato.tipo == "CPU" else "graphicsScore"
    valores = [r[campo] for r in resultados if campo in r]
    candidato.pontuacao = round(sum(valores) / len(valores), 2) if valores else None
    candidato.amostras = len(valores)
    return candidato


def buscar_e_pontuar(tipo: str, termo: str, max_candidatos: int = 5) -> list[Candidato]:
    """
    Função principal: busca o nome digitado, pega até `max_candidatos`
    correspondências e retorna cada uma já com a pontuação média
    calculada -- pronta para exibir numa lista de opções ao usuário.
    """
    session = _session()
    candidatos = buscar_nomes(tipo, termo, session=session)[:max_candidatos]
    for c in candidatos:
        pontuacao_media(c, session=session)
    # prioriza quem tem mais amostras (pontuação mais confiável)
    candidatos.sort(key=lambda c: c.amostras, reverse=True)
    return candidatos


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python -m integrations.busca_3dmark \"<termo>\" <CPU|GPU>")
        sys.exit(1)

    termo_cli, tipo_cli = sys.argv[1], sys.argv[2]
    resultados = buscar_e_pontuar(tipo_cli, termo_cli)
    if not resultados:
        print("Nada encontrado. Rode buscar_nomes() isoladamente e inspecione o JSON bruto retornado.")
    for c in resultados:
        print(f"[{c.id}] {c.nome} — pontuação média: {c.pontuacao} ({c.amostras} amostras)")
