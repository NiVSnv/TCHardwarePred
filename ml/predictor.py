"""
Carrega o modelo treinado (.pkl) e gera previsões de FPS para uma
combinação de pontuações de CPU e GPU informada pelo usuário.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from ml.train_model import treinar, MODEL_DIR


def _caminho_modelo(jogo: str) -> Path:
    slug = jogo.lower().replace(" ", "_")
    return MODEL_DIR / f"modelo_{slug}.pkl"


def prever_fps(cpu_score: int, gpu_score: int, jogo: str, treinar_se_ausente: bool = True) -> float:
    """
    Retorna o FPS estimado para a combinação de hardware informada.
    Se ainda não existir um modelo salvo para o jogo, treina um na hora
    (útil na primeira execução / após novos dados serem cadastrados).
    """
    caminho = _caminho_modelo(jogo)
    if not caminho.exists():
        if not treinar_se_ausente:
            raise FileNotFoundError(f"Nenhum modelo treinado encontrado para '{jogo}'.")
        treinar(jogo)

    modelo = joblib.load(caminho)
    entrada = pd.DataFrame([{"cpu_score": cpu_score, "gpu_score": gpu_score}])
    previsao = modelo.predict(entrada)[0]
    return max(0.0, float(previsao))
