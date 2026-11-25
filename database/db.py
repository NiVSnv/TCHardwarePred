"""
Camada de acesso ao banco de dados MySQL.

Todas as consultas usadas pela interface Streamlit e pelo pipeline de
treinamento do scikit-learn passam por este módulo.

Configuração via variáveis de ambiente (veja .env.example):
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _build_engine() -> Engine:
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "root")
    name = os.getenv("DB_NAME", "tchardwarepred")

    url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{name}"
    # pool_pre_ping evita erros de conexão "caída" quando o Streamlit
    # fica muitos minutos parado entre uma ação do usuário e outra.
    return create_engine(url, pool_pre_ping=True)


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


@contextmanager
def get_connection() -> Iterator:
    engine = get_engine()
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()


# ------------------------------------------------------------------
# Consultas usadas pela aplicação
# ------------------------------------------------------------------

def list_models(tipo: str) -> pd.DataFrame:
    """Lista os modelos de CPU ou GPU já cadastrados na tabela hardware_scores."""
    query = text(
        """
        SELECT id, fabricante, modelo, pontuacao_3dmark
        FROM hardware_scores
        WHERE tipo = :tipo
        ORDER BY fabricante, modelo
        """
    )
    with get_connection() as conn:
        return pd.read_sql(query, conn, params={"tipo": tipo})


def get_or_create_component(tipo: str, fabricante: str, modelo: str, pontuacao: int, fonte: str = "manual") -> int:
    """
    Insere (ou atualiza a pontuação de) um componente e retorna o id.
    Usado tanto para cadastro manual quanto para dados vindos do 3DMark.
    """
    upsert = text(
        """
        INSERT INTO hardware_scores (tipo, fabricante, modelo, pontuacao_3dmark, fonte)
        VALUES (:tipo, :fabricante, :modelo, :pontuacao, :fonte)
        ON DUPLICATE KEY UPDATE
            pontuacao_3dmark = VALUES(pontuacao_3dmark),
            fonte = VALUES(fonte)
        """
    )
    select_id = text(
        "SELECT id FROM hardware_scores WHERE tipo = :tipo AND modelo = :modelo"
    )
    with get_connection() as conn:
        conn.execute(
            upsert,
            {"tipo": tipo, "fabricante": fabricante, "modelo": modelo, "pontuacao": pontuacao, "fonte": fonte},
        )
        conn.commit()
        result = conn.execute(select_id, {"tipo": tipo, "modelo": modelo}).first()
        return int(result[0])


def get_training_dataset(jogo: str | None = None) -> pd.DataFrame:
    """
    Retorna o dataset rotulado (features + alvo) usado para treinar o modelo:
    pontuação da CPU, pontuação da GPU, jogo e FPS observado.
    """
    query = """
        SELECT
            fb.id,
            cpu.pontuacao_3dmark AS cpu_score,
            gpu.pontuacao_3dmark AS gpu_score,
            fb.jogo,
            fb.resolucao,
            fb.fps_medio
        FROM fps_benchmarks fb
        JOIN hardware_scores cpu ON cpu.id = fb.cpu_id AND cpu.tipo = 'CPU'
        JOIN hardware_scores gpu ON gpu.id = fb.gpu_id AND gpu.tipo = 'GPU'
    """
    params = {}
    if jogo:
        query += " WHERE fb.jogo = :jogo"
        params["jogo"] = jogo
    with get_connection() as conn:
        return pd.read_sql(text(query), conn, params=params)


def add_fps_sample(cpu_id: int, gpu_id: int, jogo: str, fps_medio: float, resolucao: str = "1080p") -> None:
    """Adiciona uma nova amostra rotulada (retreinamento contínuo)."""
    insert = text(
        """
        INSERT INTO fps_benchmarks (cpu_id, gpu_id, jogo, resolucao, fps_medio)
        VALUES (:cpu_id, :gpu_id, :jogo, :resolucao, :fps_medio)
        """
    )
    with get_connection() as conn:
        conn.execute(insert, {
            "cpu_id": cpu_id, "gpu_id": gpu_id, "jogo": jogo,
            "resolucao": resolucao, "fps_medio": fps_medio,
        })
        conn.commit()


def list_games() -> list[str]:
    """Jogos com dados suficientes cadastrados no banco."""
    query = text("SELECT DISTINCT jogo FROM fps_benchmarks ORDER BY jogo")
    with get_connection() as conn:
        rows = conn.execute(query).fetchall()
    return [r[0] for r in rows]
