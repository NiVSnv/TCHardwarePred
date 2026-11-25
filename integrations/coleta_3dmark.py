"""
Coleta de pontuações reais do 3DMark via busca pública.

Usa o mesmo endpoint que a própria página https://www.3dmark.com/search
chama por trás dos panos (proxycon/ajax/newsearch) para comparar
resultados por combinação de GPU + CPU. Não exige autenticação/API key --
é público, mas não documentado oficialmente, então pode mudar sem aviso.

Isso substitui, na prática, o "stub" de API oficial descrito em
api_3dmark.py para o propósito de CONSTRUIR o dataset de treino em lote
(equivalente ao objetivo do script original ColetaGPUCPU.py). Continua
não sendo uma forma de consultar a pontuação de um usuário específico
qualquer -- é uma busca pública por combinações de hardware já testadas
por outros usuários do 3DMark.

Uso:
    python -m integrations.coleta_3dmark
    python -m integrations.coleta_3dmark --salvar-no-banco
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://www.3dmark.com/proxycon/ajax/newsearch"

HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "referer": "https://www.3dmark.com/search",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "x-requested-with": "XMLHttpRequest",
}


@dataclass
class ResultadoCombo:
    gpu_nome: str
    gpu_id: int
    cpu_nome: str
    cpu_id: int
    graphics_score: float   # pontuação média da GPU (Graphics Score) nesse par
    cpu_score: float        # pontuação média da CPU (physicsScore / CPU Score) nesse par
    overall_score: float
    amostras: int


def _montar_url(gpu_id: int, cpu_id: int) -> str:
    return (
        f"{BASE_URL}?test=spy%20P&cpuId={cpu_id}&gpuId={gpu_id}&gpuCount=1"
        "&gpuType=ALL&deviceType=ALL&storageModel=ALL&modelId=&showRamDisks=false"
        "&memoryChannels=0&country=&scoreType=overallScore&hofMode=false"
        "&showInvalidResults=false&freeParams=&minGpuCoreClock=&maxGpuCoreClock="
        "&minGpuMemClock=&maxGpuMemClock=&minCpuClock=&maxCpuClock="
    )


def consultar_combo(session: requests.Session, gpu: dict, cpu: dict) -> ResultadoCombo:
    """Consulta a busca pública para uma combinação específica de GPU e CPU."""
    url = _montar_url(gpu["id"], cpu["id"])
    resposta = session.get(url, timeout=15)
    resposta.raise_for_status()
    dados = resposta.json()
    resultados = dados.get("results", [])

    if not resultados:
        return ResultadoCombo(gpu["nome"], gpu["id"], cpu["nome"], cpu["id"], 0.0, 0.0, 0.0, 0)

    df = pd.DataFrame(resultados)
    return ResultadoCombo(
        gpu_nome=gpu["nome"],
        gpu_id=gpu["id"],
        cpu_nome=cpu["nome"],
        cpu_id=cpu["id"],
        graphics_score=round(float(df["graphicsScore"].mean()), 2),
        cpu_score=round(float(df["physicsScore"].mean()), 2),
        overall_score=round(float(df["overallScore"].mean()), 2),
        amostras=len(df),
    )


def coletar(gpus: list[dict], cpus: list[dict], pausa_segundos: float = 0.5) -> list[ResultadoCombo]:
    """
    Percorre todas as combinações de GPUs x CPUs informadas.
    `pausa_segundos` evita bombardear o endpoint público com requisições
    em sequência muito rápida (boa prática de scraping educado).
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    resultados: list[ResultadoCombo] = []
    for gpu in gpus:
        for cpu in cpus:
            combo = consultar_combo(session, gpu, cpu)
            resultados.append(combo)
            if combo.amostras == 0:
                print(f"Sem resultados: {gpu['nome']} + {cpu['nome']}")
            else:
                print(
                    f"{gpu['nome']} + {cpu['nome']}: {combo.amostras} amostras "
                    f"(GPU {combo.graphics_score} | CPU {combo.cpu_score})"
                )
            time.sleep(pausa_segundos)
    return resultados


def salvar_csv(resultados: list[ResultadoCombo], caminho: str = "coleta_3dmark.csv") -> None:
    df = pd.DataFrame([r.__dict__ for r in resultados])
    existe = Path(caminho).exists()
    df.to_csv(caminho, mode="a" if existe else "w", index=False, header=not existe)


def salvar_no_banco(resultados: list[ResultadoCombo]) -> None:
    """
    Grava as pontuações coletadas em hardware_scores (CPU e GPU).
    O FPS observado em jogo continua precisando ser medido/coletado à
    parte (o 3DMark não mede FPS de jogos reais) e inserido depois via
    database.db.add_fps_sample().
    """
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from database.db import get_or_create_component  # import tardio evita ciclo

    for r in resultados:
        if r.amostras == 0:
            continue
        fabricante_cpu, modelo_cpu = (r.cpu_nome.split(" ", 1) + [""])[:2]
        fabricante_gpu, modelo_gpu = (r.gpu_nome.split(" ", 1) + [""])[:2]
        get_or_create_component("CPU", fabricante_cpu, modelo_cpu or r.cpu_nome, int(r.cpu_score), fonte="3dmark_public_search")
        get_or_create_component("GPU", fabricante_gpu, modelo_gpu or r.gpu_nome, int(r.graphics_score), fonte="3dmark_public_search")


# ----------------------------------------------------------------------
# Listas de exemplo (mesmo formato do script original: id interno do
# 3DMark + nome de exibição). Edite/expanda conforme os componentes que
# quiser coletar.
# ----------------------------------------------------------------------
GPUS_EXEMPLO = [
    {"id": 1414, "nome": "AMD Radeon RX 6600"},
    {"id": 1406, "nome": "AMD Radeon RX 6600 XT"},
    {"id": 1353, "nome": "AMD Radeon RX 6900 XT"},
]

CPUS_EXEMPLO = [
    {"id": 2762, "nome": "AMD Ryzen 5 4600G"},
    {"id": 2408, "nome": "AMD Ryzen 5 PRO 2600"},
    {"id": 2482, "nome": "AMD Ryzen 5 3400G"},
]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta pontuações públicas do 3DMark por combinação CPU+GPU")
    parser.add_argument("--csv", default="coleta_3dmark.csv", help="Caminho do CSV de saída")
    parser.add_argument("--salvar-no-banco", action="store_true", help="Também grava em hardware_scores (MySQL)")
    parser.add_argument("--pausa", type=float, default=0.5, help="Segundos de espera entre requisições")
    args = parser.parse_args()

    resultados = coletar(GPUS_EXEMPLO, CPUS_EXEMPLO, pausa_segundos=args.pausa)
    salvar_csv(resultados, args.csv)
    print(f"\nCSV salvo em: {args.csv}")

    if args.salvar_no_banco:
        salvar_no_banco(resultados)
        print("Pontuações gravadas em hardware_scores (MySQL).")
