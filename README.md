# TCHardwarePred

Sistema de previsão de FPS a partir de pontuações de benchmark de hardware
(3DMark), inspirado no TCC "Sistema para Predição de Desempenho de Jogos a
partir de Benchmarks utilizando Machine Learning".

- **Interface:** Streamlit
- **Modelo:** scikit-learn (Regressão Linear por padrão; Random Forest opcional)
- **Persistência:** MySQL
- **Jogo suportado no momento:** Counter-Strike 2 (arquitetura já preparada
  para outros jogos assim que houver dados de treino)

## Arquitetura

```
tchardwarepred/
├── app.py                     # Interface Streamlit
├── database/
│   ├── schema.sql              # CREATE TABLE hardware_scores / fps_benchmarks
│   ├── seed_data.sql           # Dados de exemplo (CS2)
│   └── db.py                   # Acesso ao MySQL (SQLAlchemy)
├── integrations/
│   └── api_3dmark.py           # Adaptador de integração com o 3DMark
│   └── buscar_3dmark.py        # Buscar a pontuação a partir de entrada 
│   └── coleta_3dmark.py        # Coleta dados para alimentar a base
├── ml/
│   ├── train_model.py          # Treino/avaliação do modelo (scikit-learn)
│   └── predictor.py            # Carrega o modelo e gera previsões
└── requirements.txt
```

### Modelo de dados

- `hardware_scores`: pontuação individual de cada CPU/GPU (3DMark).
- `fps_benchmarks`: combinações CPU+GPU e o FPS observado em um jogo —
  é o dataset rotulado usado para treinar o modelo (features: `cpu_score`,
  `gpu_score`; alvo: `fps_medio`).

## Sobre a integração com o 3DMark

A UL Solutions (dona do 3DMark) **não oferece uma API pública oficial de
autoatendimento** para consultar a pontuação de qualquer usuário a partir
do nome da CPU/GPU. O que existe formalmente é um serviço B2B
("performance data for retailers"), voltado a parceiros comerciais
mediante contrato.

Na prática, existe um segundo caminho: o site `3dmark.com/search` usa um
endpoint interno (`proxycon/ajax/newsearch`) para comparar resultados
públicos por combinação de CPU+GPU, sem exigir autenticação. Não é
documentado nem suportado oficialmente pela UL (pode mudar sem aviso),
mas é real e funcional -- é o que `integrations/coleta_3dmark.py`
utiliza para popular `hardware_scores` em lote.

Duas frentes, portanto:

| Arquivo                              | Uso                                                                 | Como funciona |
|---------------------------------------|----------------------------------------------------------------------|---------------|
| `integrations/api_3dmark.py`          | Tempo real, dentro da interface Streamlit                            | `manual` (usuário digita a pontuação, padrão) · `local_export` (lê arquivo exportado do app 3DMark) · `api` (stub para a API B2B oficial da UL, se houver contrato) |
| `integrations/busca_3dmark.py`        | Tempo real, na interface -- usuário digita só o NOME do componente   | Encadeia busca por nome (`proxycon/ajax/search/{gpu,cpu}name`) + pontuação média (`proxycon/ajax/newsearch`) |
| `integrations/coleta_3dmark.py`       | Coleta em lote para construir/expandir o dataset de treino           | Busca pública `proxycon/ajax/newsearch` (sem autenticação) |

```bash
# Coleta pontuações reais de GPU/CPU pela busca pública e grava em hardware_scores
python -m integrations.coleta_3dmark --salvar-no-banco

# Testar a busca por nome isoladamente (imprime candidatos + pontuação média)
python -m integrations.busca_3dmark "RTX 4070" GPU
```

### Busca automática por nome (`busca_3dmark.py`)

Na interface Streamlit, ao escolher "Buscar automaticamente no 3DMark",
o usuário digita apenas o nome do componente (ex: "RTX 4070") e clica em
Buscar. O sistema:

1. Consulta o endpoint de autocomplete do 3DMark para achar os
   componentes cujo nome bate com o termo digitado;
2. Para cada correspondência, consulta a média de pontuação de todos os
   resultados públicos que usaram aquele componente (com qualquer
   parceiro de CPU/GPU);
3. Mostra até 5 opções ordenadas pela quantidade de amostras (mais
   amostras = pontuação mais confiável), para o usuário escolher a
   correta.

**Atenção:** assim como o endpoint de comparação, o endpoint de busca
por nome não é documentado oficialmente pela UL -- foi identificado por
engenharia reversa da página `3dmark.com/search`. O formato exato do
JSON retornado pode variar; se `buscar_nomes()` não encontrar nada,
rode `python -m integrations.busca_3dmark "<termo>" GPU` para inspecionar
a resposta bruta e ajustar o parsing em `busca_3dmark.py` se necessário.
Se a busca falhar, a interface sempre permite cair para o modo manual.

Para o TCC, vale registrar essa distinção na seção de metodologia: a
coleta em lote usa um endpoint público não documentado do site (o mesmo
que a própria ferramenta de busca do 3DMark usa), enquanto a consulta
"pontuação do meu PC agora" na interface segue dependendo de o usuário
informar o valor (já que não há um endpoint público para *identificar*
automaticamente o hardware de quem está rodando o Streamlit).

## Instalação

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env       # ajuste usuário/senha do MySQL
mysql -u root -p < database/schema.sql
mysql -u root -p < database/seed_data.sql
# Para VSCode com PowerShell
Get-Content database/schema.sql | mysql -u root -p
Get-Content database/seed_data.sql | mysql -u root -p
```

## Treinar o modelo

```bash
python -m ml.train_model --jogo "Counter-Strike 2" --algoritmo linear
```

Isso salva o modelo em `ml/modelos/modelo_counter-strike_2.pkl` e imprime
MAE, RMSE e R² sobre o conjunto de teste.

## Rodar a aplicação

```bash
streamlit run app.py
```

O `app.py` treina o modelo automaticamente na primeira previsão, caso ainda
não exista um `.pkl` salvo.

## Retreinamento contínuo

Toda combinação CPU/GPU digitada manualmente na interface é persistida em
`hardware_scores`. Para incorporar novas amostras de FPS validadas (e assim
ampliar a base de treino, como descrito no TCC), use:

```python
from database.db import add_fps_sample
add_fps_sample(cpu_id=1, gpu_id=3, jogo="Counter-Strike 2", fps_medio=345)
```

e rode `train_model.py` novamente para atualizar o `.pkl`.

## Próximos passos sugeridos

- Adicionar mais jogos ao "banco" (basta popular `fps_benchmarks` com o novo
  `jogo` e um número mínimo de amostras).
- Trocar o algoritmo para `random_forest` se a relação CPU/GPU → FPS não for
  bem capturada por uma reta.
- Se a equipe conseguir acesso ao programa de parceiros da UL, preencher
  `THREEDMARK_API_BASE_URL`/`THREEDMARK_API_KEY` e trocar
  `THREEDMARK_PROVIDER=api`.
