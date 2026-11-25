"""
Integração com o 3DMark (UL Solutions).

IMPORTANTE (leia antes de usar):
A UL Solutions não disponibiliza uma API pública OFICIAL de autoatendimento
para consultar a pontuação de um usuário qualquer a partir do nome da
CPU/GPU. O que existe formalmente é um serviço B2B ("performance data for
retailers"), voltado a parceiros comerciais, mediante contrato.

Na prática, porém, o site www.3dmark.com/search usa um endpoint interno
(proxycon/ajax/newsearch) para a busca pública de resultados por
combinação de CPU+GPU, sem autenticação. Não é documentado nem
oficialmente suportado, mas funciona e é ótimo para COLETA EM LOTE do
dataset de treino -- veja `integrations/coleta_3dmark.py`. Esse módulo
aqui (`api_3dmark.py`) continua focado no fluxo em tempo real da
aplicação (o usuário informando a própria pontuação na tela).

Por isso este módulo foi desenhado como um ADAPTADOR com 3 estratégias,
para que o restante do sistema (Streamlit + scikit-learn) não precise
saber de onde veio a pontuação:

    1. ManualScoreProvider   -> usuário digita a pontuação (sempre funciona)
    2. LocalExportProvider   -> lê um arquivo de resultado exportado pelo
                                 próprio app 3DMark (XML/JSON), que o
                                 usuário salva localmente após rodar o
                                 benchmark Time Spy
    3. OfficialAPIProvider   -> stub pronto para plugar credenciais reais,
                                 caso vocês consigam acesso ao programa de
                                 parceiros da UL para o TCC

Use `get_provider()` para obter automaticamente o provider configurado via
variável de ambiente THREEDMARK_PROVIDER (manual | local_export | api).
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests


@dataclass
class HardwareScore:
    tipo: str          # "CPU" ou "GPU"
    modelo: str
    pontuacao: int
    fonte: str


class ThreeDMarkProviderError(Exception):
    """Erro genérico de obtenção de pontuação do 3DMark."""


# ------------------------------------------------------------------
# 1) Entrada manual - o usuário já sabe a pontuação (rodou o 3DMark
#    localmente e está olhando o resultado na tela). Este é o caminho
#    recomendado para o TCC, por não depender de acesso B2B.
# ------------------------------------------------------------------
class ManualScoreProvider:
    fonte = "manual"

    def get_score(self, tipo: str, modelo: str, pontuacao_informada: int) -> HardwareScore:
        return HardwareScore(tipo=tipo, modelo=modelo, pontuacao=pontuacao_informada, fonte=self.fonte)


# ------------------------------------------------------------------
# 2) Export local do 3DMark. O app Windows do 3DMark permite exportar
#    o resultado do Time Spy em XML. Se o usuário salvar esse arquivo
#    numa pasta conhecida, o sistema lê automaticamente CPU Score e
#    Graphics Score sem digitação manual.
# ------------------------------------------------------------------
class LocalExportProvider:
    fonte = "3dmark_export"

    def __init__(self, export_dir: str | None = None):
        self.export_dir = Path(export_dir or os.getenv("THREEDMARK_EXPORT_DIR", "./3dmark_exports"))

    def _latest_export(self) -> Optional[Path]:
        if not self.export_dir.exists():
            return None
        candidatos = sorted(
            list(self.export_dir.glob("*.xml")) + list(self.export_dir.glob("*.json")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidatos[0] if candidatos else None

    def get_scores(self) -> tuple[Optional[int], Optional[int]]:
        """Retorna (cpu_score, graphics_score) do export mais recente, se existir."""
        arquivo = self._latest_export()
        if arquivo is None:
            return None, None

        if arquivo.suffix == ".json":
            data = json.loads(arquivo.read_text(encoding="utf-8"))
            return data.get("cpuScore"), data.get("graphicsScore")

        # XML exportado pelo 3DMark (estrutura simplificada / adaptável)
        tree = ET.parse(arquivo)
        root = tree.getroot()
        cpu_score = root.findtext(".//CPUScore")
        graphics_score = root.findtext(".//GraphicsScore")
        return (
            int(cpu_score) if cpu_score else None,
            int(graphics_score) if graphics_score else None,
        )


# ------------------------------------------------------------------
# 3) Stub da API oficial da UL Solutions. Só funciona se a equipe
#    obtiver credenciais junto ao programa de parceiros da UL.
#    Endpoint/payload abaixo são ilustrativos -- ajuste conforme a
#    documentação recebida da UL ao firmar o acesso.
# ------------------------------------------------------------------
class OfficialAPIProvider:
    fonte = "3dmark_api"

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = base_url or os.getenv("THREEDMARK_API_BASE_URL", "")
        self.api_key = api_key or os.getenv("THREEDMARK_API_KEY", "")

    def get_score(self, tipo: str, modelo: str) -> HardwareScore:
        if not self.base_url or not self.api_key:
            raise ThreeDMarkProviderError(
                "Credenciais da API oficial do 3DMark não configuradas. "
                "Defina THREEDMARK_API_BASE_URL e THREEDMARK_API_KEY, ou "
                "use o provider 'manual'/'local_export'."
            )
        resp = requests.get(
            f"{self.base_url}/v1/components/score",
            params={"tipo": tipo, "modelo": modelo},
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
        return HardwareScore(tipo=tipo, modelo=modelo, pontuacao=payload["pontuacao"], fonte=self.fonte)


def get_provider():
    """Fábrica: escolhe o provider conforme a variável THREEDMARK_PROVIDER."""
    escolha = os.getenv("THREEDMARK_PROVIDER", "manual").lower()
    if escolha == "local_export":
        return LocalExportProvider()
    if escolha == "api":
        return OfficialAPIProvider()
    return ManualScoreProvider()
