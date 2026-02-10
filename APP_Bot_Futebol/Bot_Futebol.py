import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson

st.set_page_config(page_title="PRO Football Predictor 2026", layout="wide")

# --- DICIONÁRIO DE LIGAS ATUALIZADO ---
LIGAS = {
    "Brasileirão Série A (Brasil)": "BRA",
    "Premier League (Inglaterra)": "E0",
    "La Liga (Espanha)": "SP1",
    "Bundesliga (Alemanha)": "D1",
    "Serie A (Itália)": "I1",
    "Ligue 1 (França)": "F1"
}

@st.cache_data(ttl=3600)
def carregar_dados(liga_code):
    if liga_code == "BRA":
        # Fonte alternativa para o Brasileirão (Dados de 2025/2026)
        url = "https://www.football-data.co.uk/new/BRA.csv"
    else:
        url = f"https://www.football-data.co.uk/mmz4281/2526/{liga_code}.csv"
    
    try:
        df = pd.read_csv(url)
        # Padronização de colunas
        cols_map = {'Home': 'HomeTeam', 'Away': 'AwayTeam', 'HG': 'FTHG', 'AG': 'FTAG'}
        df = df.rename(columns=cols_map)
        return df.dropna(subset=['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG'])
    except:
        st.error(f"Erro ao carregar dados da liga {liga_code}")
        return pd.DataFrame()

def calcular_estatisticas(df, home_team, away_team):
    # Estatística Pura: Força Relativa
    avg_home_g = df['FTHG'].mean()
    avg_away_g = df['FTAG'].mean()

    # Força Mandante
    atq_h = df[df['HomeTeam'] == home_team]['FTHG'].mean() / avg_home_g
    def_h = df[df['HomeTeam'] == home_team]['FTAG'].mean() / avg_away_g

    # Força Visitante
    atq_a = df[df['AwayTeam'] == away_team]['FTAG'].mean() / avg_away_g
    def_a = df[df['AwayTeam'] == away_team]['FTHG'].mean() / avg_home_g

    # Expectativa de Gols (Poisson Lambda)
    exp_h = atq_h * def_a * avg_home_g
    exp_a = atq_a * def_h * avg_away_g

    # Probabilidades
    max_g = 10
    prob_h = [poisson.pmf(i, exp_h) for i in range(max_g)]
    prob_a = [poisson.pmf(i, exp_a) for i in range(max_g)]
    matriz = np.outer(prob_h, prob_a)

    return {
        "win_h": np.sum(np.triu(matriz, 1).T),
        "draw": np.sum(np.diag(matriz)),
        "win_a": np.sum(np.tril(matriz, -1).T),
        "exp_h": exp_h,
        "exp_a": exp_a,
        "over_15": 1 - (matriz[0,0] + matriz[0,1] + matriz[1,0]),
        "over_25": 1 - np.sum([matriz[i,j] for i in range(3) for j in range(3) if i+j <= 2])
    }

# --- INTERFACE ---
st.title("⚽ Predictor Bot: Global & Brasil")
st.markdown("Análise estatística baseada em **Distribuição de Poisson** e **Força Relativa**.")

# Sidebar
liga_nome = st.sidebar.selectbox("Selecione a Liga", list(LIGAS.keys()))
df_liga = carregar_dados(LIGAS[liga_nome])

if not df_liga.empty:
    # Filtro de Times
    times = sorted(df_liga['HomeTeam'].unique())
    col_t1, col_t2 = st.columns(2)
    with col_t1: t_casa = st.selectbox("Mandante", times, index=0)
    with col_t2: t_fora = st.selectbox("Visitante", times, index=1)

    if st.button("ANALISAR CONFRONTO"):
        res = calcular_estatisticas(df_liga, t_casa, t_fora)
        
        # 1. Resultados Principais
        st.subheader("🎯 Probabilidades Finais (FT)")
        m1, m2, m3 = st.columns(3)
        m1.metric(f"Vitória {t_casa}", f"{res['win_h']:.1%}")
        m2.metric("Empate", f"{res['draw']:.1%}")
        m3.metric(f"Vitória {t_fora}", f"{res['win_a']:.1%}")

        # 2. Gols e Expectativa
        st.divider()
        st.subheader("📊 Mercado de Gols")
        g1, g2, g3 = st.columns(3)
        g1.write(f"**Expectativa de Gols:**\n{t_casa} {res['exp_h']:.2f} x {res['exp_a']:.2f} {t_fora}")
        g2.metric("Over 1.5 Gols", f"{res['over_15']:.1%}")
        g3.metric("Over 2.5 Gols", f"{res['over_25']:.1%}")

        # 3. Análise de Confronto Direto (H2H) - Pura Estatística Histórica
        st.divider()
        st.subheader("⚔️ Histórico Recente (H2H)")
        h2h = df_liga[((df_liga['HomeTeam'] == t_casa) & (df_liga['AwayTeam'] == t_fora)) | 
                     ((df_liga['HomeTeam'] == t_fora) & (df_liga['AwayTeam'] == t_casa))].tail(5)
        
        if not h2h.empty:
            st.table(h2h[['HomeTeam', 'FTHG', 'FTAG', 'AwayTeam']])
        else:
            st.info("Sem confrontos diretos registrados nesta base de dados.")

        # 4. Verificação de Valor (Comparação com Odds)
        st.sidebar.header("Calculadora de Valor")
        odd_casa = st.sidebar.number_input("Odd Casa na Bet", value=1.90)
        ev = (res['win_h'] * odd_casa) - 1
        if ev > 0:
            st.sidebar.success(f"VALOR ENCONTRADO! EV: {ev:.2%}")
        else:
            st.sidebar.error(f"SEM VALOR. EV: {ev:.2%}")