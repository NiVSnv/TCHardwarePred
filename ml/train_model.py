"""
Treina o modelo preditivo de FPS a partir dos dados armazenados no MySQL.

Features (X): pontuação da CPU (3DMark) e pontuação da GPU (3DMark)
Alvo (y):     FPS médio observado no jogo

Execução:
    python -m ml.train_model
    python -m ml.train_model --jogo "Counter-Strike 2" --algoritmo random_forest
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

sys.path.append(str(Path(__file__).resolve().parent.parent))
from database.db import get_training_dataset  # noqa: E402

MODEL_DIR = Path(__file__).resolve().parent / "modelos"
MODEL_DIR.mkdir(exist_ok=True)

ALGORITMOS = {
    "linear": LinearRegression,
    "random_forest": lambda: RandomForestRegressor(n_estimators=200, random_state=42),
}


def treinar(jogo: str, algoritmo: str = "linear", test_size: float = 0.2) -> dict:
    df = get_training_dataset(jogo=jogo)
    if len(df) < 5:
        raise ValueError(
            f"Poucos dados para treinar o modelo de '{jogo}' ({len(df)} amostras). "
            "Cadastre mais combinações CPU+GPU+FPS na tabela fps_benchmarks."
        )

    X = df[["cpu_score", "gpu_score"]]
    y = df["fps_medio"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42
    )

    modelo = ALGORITMOS[algoritmo]()
    modelo.fit(X_train, y_train)

    y_pred = modelo.predict(X_test)
    metricas = {
        "mae": mean_absolute_error(y_test, y_pred),
        "rmse": mean_squared_error(y_test, y_pred) ** 0.5,
        "r2": r2_score(y_test, y_pred),
        "n_treino": len(X_train),
        "n_teste": len(X_test),
        "algoritmo": algoritmo,
    }

    slug = jogo.lower().replace(" ", "_")
    caminho = MODEL_DIR / f"modelo_{slug}.pkl"
    joblib.dump(modelo, caminho)

    return {"caminho": str(caminho), **metricas}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Treina o modelo preditivo de FPS")
    parser.add_argument("--jogo", default="Counter-Strike 2")
    parser.add_argument("--algoritmo", default="linear", choices=list(ALGORITMOS))
    args = parser.parse_args()

    resultado = treinar(args.jogo, args.algoritmo)
    print(f"Modelo salvo em: {resultado['caminho']}")
    print(f"Amostras -> treino: {resultado['n_treino']} | teste: {resultado['n_teste']}")
    print(f"MAE: {resultado['mae']:.2f} FPS")
    print(f"RMSE: {resultado['rmse']:.2f} FPS")
    print(f"R²: {resultado['r2']:.3f}")
