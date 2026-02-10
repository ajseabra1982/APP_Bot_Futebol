import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson

st.set_page_config(page_title="Ultra Predictor Bot 2026", layout="wide")

# --- BANCO DE DADOS ---
LIGAS = {
    "Brasileirão Série A": "BRA",
    "Premier League (Inglaterra)": "E0",
    "La Liga (Espanha)": "SP1",
    "Bundesliga (Alemanha)": "D1",
    "Serie A (Itália)": "I1",
    "Ligue 1 (França)": "F1"
}

@st.cache_data(ttl=3600)
def carregar_dados(liga_code):
    url = f"https://www.football-data.co.uk/new/BRA.csv" if liga_code == "BRA" else f"https://www.football-data.co.uk/mmz4281/2526/{liga_code}.csv"
    try:
        df = pd.read_csv(url)
        # Padronização universal para o bot
        cols_map = {
            'Home': 'HomeTeam', 'Away': 'AwayTeam', 
            'HG': 'FTHG', 'AG': 'FTAG', 
            'HHG': 'HTHG', 'HAG': 'HTAG',
            'HTHG': 'HTHG', 'HTAG': 'HTAG'
        }
        df = df.rename(columns=cols_map)
        return df.dropna(subset=['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG'])
    except:
        return pd.DataFrame()

# --- MOTOR ESTATÍSTICO ---
def analisar_partida(df, t_casa, t_fora):
    avg_h = df['FTHG'].mean()
    avg_a = df['FTAG'].mean()
    
    # Expectativa Full-Time (FT)
    exp_h = (df[df['HomeTeam'] == t_casa]['FTHG'].mean() / avg_h) * (df[df['AwayTeam'] == t_fora]['FTHG'].mean() / avg_h) * avg_h
    exp_a = (df[df['AwayTeam'] == t_fora]['FTAG'].mean() / avg_a) * (df[df['HomeTeam'] == t_casa]['FTAG'].mean() / avg_a) * avg_a
    
    # Matriz Poisson FT
    p_h = [poisson.pmf(i, exp_h) for i in range(10)]
    p_a = [poisson.pmf(i, exp_a) for i in range(10)]
    m = np.outer(p_h, p_a)

    # Expectativa Half-Time (HT) - Estimada em 45% da média FT
    exp_h_ht = exp_h * 0.45
    exp_a_ht = exp_a * 0.45

    return {
        "H": np.sum(np.triu(m, 1).T),
        "D": np.sum(np.diag(m)),
        "A": np.sum(np.tril(m, -1).T),
        "O15": 1 - (m[0,0] + m[0,1] + m[1,0]),
        "O25": 1 - np.sum([m[i,j] for i in range(3) for j in range(3) if i+j <= 2]),
        "HT05": 1 - (poisson.pmf(0, exp_h_ht) * poisson.pmf(0, exp_a_ht)),
        "exp_h": exp_h,
        "exp_a": exp_a
    }

# --- INTERFACE ---
st.title("⚽ Ultra Predictor: Multi-Mercados & Histórico")

with st.expander("📖 MANUAL RÁPIDO"):
    st.write("1. Escolha os times. 2. Insira as Odds da sua casa na barra lateral. 3. Analise o EV Verde.")

liga_sel = st.sidebar.selectbox("Liga", list(LIGAS.keys()))
df_liga = carregar_dados(LIGAS[liga_sel])

if not df_liga.empty:
    times = sorted(df_liga['HomeTeam'].unique())
    col1, col2 = st.columns(2)
    t1 = col1.selectbox("Mandante", times, index=0)
    t2 = col2.selectbox("Visitante", times, index=1)
    
    st.sidebar.header("💰 Odds da Casa")
    o_h = st.sidebar.number_input("Odd Casa (1)", 1.0, step=0.01)
    o_d = st.sidebar.number_input("Odd Empate (X)", 1.0, step=0.01)
    o_a = st.sidebar.number_input("Odd Fora (2)", 1.0, step=0.01)
    st.sidebar.divider()
    o_ht = st.sidebar.number_input("Odd Over 0.5 HT", 1.0, step=0.01)
    o_15 = st.sidebar.number_input("Odd Over 1.5 FT", 1.0, step=0.01)
    o_25 = st.sidebar.number_input("Odd Over 2.5 FT", 1.0, step=0.01)

    if st.button("GERAR ANÁLISE COMPLETA"):
        res = analisar_partida(df_liga, t1, t2)
        
        # 1. Expectativa de Gols
        st.info(f"📊 **Expectativa de Gols:** {t1} {res['exp_h']:.2f} x {res['exp_a']:.2f} {t2}")
        
        # 2. Tabela de Valor (EV)
        st.subheader("🎯 Oportunidades de Mercado")
        odds_dict = {"H": o_h, "D": o_d, "A": o_a, "HT05": o_ht, "O15": o_15, "O25": o_25}
        labels = {"H": "Vitória Casa", "D": "Empate", "A": "Vitória Fora", "HT05": "Over 0.5 HT", "O15": "Over 1.5 FT", "O25": "Over 2.5 FT"}
        
        tabela_dados = []
        for chave, texto in labels.items():
            prob = res[chave]
            odd_m = round(1/prob, 2)
            ev = (prob * odds_dict[chave]) - 1
            tabela_dados.append([texto, f"{prob:.1%}", odd_m, odds_dict[chave], ev])
            
        df_final = pd.DataFrame(tabela_dados, columns=["Mercado", "Prob. Bot", "Odd Mínima", "Odd Casa", "EV (Valor)"])
        
        def style_ev(v):
            return f'color: {"green" if v > 0 else "red"}; font-weight: bold'
        
        st.table(df_final.style.applymap(style_ev, subset=['EV (Valor)']).format({"EV (Valor)": "{:.2%}"}))

        # 3. Histórico H2H (Restaurado)
        st.divider()
        st.subheader("⚔️ Confrontos Diretos Recentes (H2H)")
        h2h = df_liga[((df_liga['HomeTeam'] == t1) & (df_liga['AwayTeam'] == t2)) | 
                     ((df_liga['HomeTeam'] == t2) & (df_liga['AwayTeam'] == t1))].tail(5)
        
        if not h2h.empty:
            h2h_view = h2h[['HomeTeam', 'FTHG', 'FTAG', 'AwayTeam']].copy()
            h2h_view.columns = ['Mandante', 'Gols Casa', 'Gols Fora', 'Visitante']
            st.table(h2h_view)
        else:
            st.warning("Nenhum histórico recente encontrado para estes times nesta liga.")