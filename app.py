"""
TCHardwarePred - Interface Streamlit
Previsão de FPS a partir de pontuações de benchmark de CPU e GPU.

Execução:
    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st
import re
import subprocess
import pandas as pd

from database.db import get_or_create_component, list_models
from integrations.api_3dmark import ManualScoreProvider
from integrations.busca_3dmark import buscar_e_pontuar
from ml.predictor import prever_fps

st.set_page_config(page_title="Predição de FPS", page_icon="🎮", layout="centered")

def detectar_hardware():

    cpu = subprocess.check_output(
        ["powershell", "-Command", "(Get-CimInstance Win32_Processor).Name"],
        text=True
    ).strip()

    gpu = subprocess.check_output(
        [
            "powershell",
            "-Command",
            "(Get-CimInstance Win32_VideoController | "
            "Where-Object {$_.Name -notlike '*Virtual*' "
            "-and $_.Name -notlike '*Parsec*'} | "
            "Select-Object -First 1 -ExpandProperty Name)"
        ],
        text=True
    ).strip()

    # Remove informações adicionais do nome da CPU
    cpu = re.sub(r"\(R\)|\(TM\)|\bCPU\b|@\s*[\d.]+\s*GHz", "", cpu)
    cpu = re.sub(r"\s+", " ", cpu).strip()

    return cpu, gpu


cpu_atual, gpu_atual = detectar_hardware()

def buscar_score_atual(tipo, nome):
    resultados = buscar_e_pontuar(tipo, nome)

    resultados_validos = [
        r for r in resultados
        if r.pontuacao is not None
    ]

    if not resultados_validos:
        return None

    return resultados_validos[0].pontuacao

st.markdown(
    f"""
    <div class="hardware-container">
        <h3>Configuração atual do PC</h3>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
            <div style="background-color: #b14623; padding: 10px; border-radius: 10px; display: grid">
                <span style="color: white">CPU</span>
                <span style="color: white">{cpu_atual}</span>
            </div>
            <div style="background-color: #b14623; padding: 10px; border-radius: 10px; display: grid">
                <span style="color: white">GPU</span>
                <span style="color: white">{gpu_atual}</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
    

# Jogos disponíveis no "banco" de escolhas. Por enquanto o sistema só
# tem dados suficientes para Counter-Strike 2 -- os demais aparecem na
# lista mas ficam desabilitados até haver dados de treino no MySQL.
JOGOS_DISPONIVEIS = ["Counter-Strike 2"]
JOGOS_PLANEJADOS = ["Valorant", "League of Legends", "Fortnite"]

st.title("Modelo preditivo de FPS")

st.caption(
    "Previsão de FPS a partir de pontuações de benchmark "
    "(CPU + GPU) usando Machine Learning."
)

with st.sidebar:
    st.header("Sobre")
    st.markdown(
        """      
            <div style="text-align: justify">
                O modelo é treinado com scikit-learn sobre uma base MySQL contendo
                pontuações de CPU/GPU (3DMark) e combinações de hardware com o FPS
                observado em jogo.
            </div>
        """, unsafe_allow_html=True
    )
    st.markdown(
            """      
                <div style="text-align: justify; background-color: #b14623; color: white; padding: 10px; border-radius: 10px; margin-top: 20px">
                    No momento, apenas Counter-Strike 2 possui dados suficientes para previsão.
                </div>
            """, unsafe_allow_html=True
        )
    
st.subheader("Selecione o jogo")
jogo = st.selectbox(
    "Jogos",
    options=JOGOS_DISPONIVEIS + JOGOS_PLANEJADOS,
    format_func=lambda j: j if j in JOGOS_DISPONIVEIS else f"{j} (em breve)",
)
jogo_habilitado = jogo in JOGOS_DISPONIVEIS
if not jogo_habilitado:
    st.warning(f"Ainda não há dados de treinamento para **{jogo}**. Selecione Counter-Strike 2.")


def bloco_entrada_hardware(tipo: str, fabricante_padrao: str):
    """
    Renderiza o bloco de entrada de CPU ou GPU com 3 modos:
      - Selecionar da base já cadastrada no MySQL
      - Buscar automaticamente no 3DMark pelo nome (via busca_3dmark.py)
      - Digitar a pontuação manualmente (fallback, se a busca falhar)
    Retorna (pontuacao, nome_exibicao) ou (None, None) se nada foi informado.
    """
    componentes_cadastrados = list_models(tipo)
    modo = st.radio(
        "Como deseja informar?",
        ["Selecionar da base", "Buscar automaticamente no 3DMark", "Digitar pontuação manualmente"],
        horizontal=True,
        key=f"modo_{tipo}",
    )

    if modo == "Selecionar da base":
        if componentes_cadastrados.empty:
            st.caption("Nenhum componente cadastrado ainda -- use outro modo.")
            return None, None
        opcao = st.selectbox(
            f"Modelo de {tipo}",
            componentes_cadastrados.itertuples(),
            format_func=lambda r: f"{r.fabricante} {r.modelo} — {r.pontuacao_3dmark} pts",
            key=f"select_{tipo}",
        )
        return opcao.pontuacao_3dmark, f"{opcao.fabricante} {opcao.modelo}"

    if modo == "Buscar automaticamente no 3DMark":
        col_busca, col_botao = st.columns([4, 1])
        termo = col_busca.text_input(
            f"Nome da {tipo} (ex: {'RTX 4070' if tipo == 'GPU' else 'Ryzen 7 5800X'})",
            key=f"termo_{tipo}",
        )
        buscar = col_botao.button("🔍 Buscar", key=f"buscar_{tipo}")

        if buscar and termo:
            with st.spinner(f"Buscando '{termo}' no 3DMark..."):
                try:
                    resultados = buscar_e_pontuar(tipo, termo)
                except Exception as e:
                    st.error(
                        f"Não foi possível consultar o 3DMark agora ({e}). "
                        "Use o modo 'Digitar pontuação manualmente'."
                    )
                    resultados = []
                st.session_state[f"resultados_{tipo}"] = resultados

        resultados = st.session_state.get(f"resultados_{tipo}", [])
        resultados_validos = [c for c in resultados if c.pontuacao is not None]

        if buscar and not resultados_validos:
            st.warning(
                f"Nenhum resultado público encontrado para '{termo}'. "
                "Verifique a grafia ou use o modo manual."
            )

        if resultados_validos:
            escolha = st.selectbox(
                "Resultado encontrado",
                resultados_validos,
                format_func=lambda c: f"{c.nome} — {c.pontuacao:.0f} pts (média de {c.amostras} amostras)",
                key=f"escolha_{tipo}",
            )
            return int(escolha.pontuacao), escolha.nome
        return None, None

    # Modo manual (fallback)
    col1, col2, col3 = st.columns([2, 2, 2])
    fabricante = col1.text_input("Fabricante", fabricante_padrao, key=f"fab_{tipo}")
    modelo = col2.text_input("Modelo", key=f"mod_{tipo}")
    pontuacao = col3.number_input(
        "CPU Score" if tipo == "CPU" else "Graphics Score", min_value=0, step=100, key=f"pt_{tipo}"
    )
    if modelo and pontuacao:
        provider = ManualScoreProvider()
        resultado = provider.get_score(tipo, modelo, int(pontuacao))
        return resultado.pontuacao, f"{fabricante} {modelo}"
    return None, None


st.subheader("Selecione o modelo da CPU")
cpu_score, cpu_nome = bloco_entrada_hardware("CPU", "Intel")

st.subheader("Selecione o modelo da GPU")
gpu_score, gpu_nome = bloco_entrada_hardware("GPU", "NVIDIA")

st.divider()

if st.button("Prever FPS", type="primary", disabled=not jogo_habilitado):
    if cpu_score is None or gpu_score is None:
        st.error("Informe a CPU e a GPU antes de prever.")
    else:
        with st.spinner("Consultando modelo e calculando previsão..."):
            # Persiste no banco qualquer componente que ainda não estava
            # cadastrado (veio de busca automática ou digitação manual),
            # para enriquecer a base de conhecimento ao longo do uso.
            if " " in cpu_nome:
                fab_cpu, mod_cpu = cpu_nome.split(" ", 1)
                get_or_create_component("CPU", fab_cpu, mod_cpu, cpu_score)
            if " " in gpu_nome:
                fab_gpu, mod_gpu = gpu_nome.split(" ", 1)
                get_or_create_component("GPU", fab_gpu, mod_gpu, gpu_score)

            cpu_atual_score = buscar_score_atual(
                "CPU",
                cpu_atual
            )

            gpu_atual_score = buscar_score_atual(
                "GPU",
                gpu_atual
            )

            fps_previsto = prever_fps(cpu_score, gpu_score, jogo)
            
            if cpu_atual_score is not None and gpu_atual_score is not None:
    
                fps_atual = prever_fps(
                    cpu_atual_score,
                    gpu_atual_score,
                    jogo
                )

            else:

                fps_atual = None

        st.success(f"Configuração: **{cpu_nome}** + **{gpu_nome}** rodando **{jogo}**")
        
        col1, col2, col3 = st.columns(3)
        #Cria colunas para representar os dados horizontalmente

        col1.metric("FPS atual", f"{fps_atual:.0f}")
        #adiciona a métrica FPS atual à primeira coluna
        col2.metric("FPS previsto", f"{fps_previsto:.0f}")
        #adiciona a métrica FPS previsto à primeira coluna

        porcentagem = ((fps_previsto - fps_atual) / fps_atual) * 100
        #calcula a porcentagem com base no fps atual

        col3.metric(
            "Variação",
            f"{porcentagem:+.0f}%",
            delta=f"{fps_previsto - fps_atual:+.0f} FPS"
            #adiciona a métrica de variação à coluna 3, mostrando com delta se houve melhora ou piora
        )
        
        
        if fps_atual is not None:
    
            dados_comparacao = pd.DataFrame({
                "Configuração": [
                    "PC atual",
                    "Previsão"
                ],
                "FPS": [
                    fps_atual,
                    fps_previsto
                ]
            })

            st.subheader("Comparação de desempenho")

            st.bar_chart(
                dados_comparacao,
                x="Configuração",
                y="FPS",
                horizontal=True
                #cria o gráfico para demonstrar a comparação entre o FPS atual e o previsto
            )

        if fps_previsto >= 240:
            st.caption("Desempenho excelente para jogos competitivos em alta taxa de atualização.")
        elif fps_previsto >= 120:
            st.caption("Desempenho muito bom, ideal para monitores de 144Hz.")
        elif fps_previsto >= 60:
            st.caption("Desempenho estável para a maioria dos jogadores.")
        else:
            st.caption("Desempenho abaixo do ideal — considere atualizar CPU e/ou GPU.")
        
        
