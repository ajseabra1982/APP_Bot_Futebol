import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import requests

st.set_page_config(page_title="Ultra Predictor Bot + Telegram", layout="wide")

# --- CONFIGURAÇÃO TELEGRAM (SUBSTITUA PELOS SEUS DADOS) ---
TELEGRAM_TOKEN = "7016880606:AAHaJyvVopaNw9UY5CpM0LBBEP4MuPl7A-g"
TELEGRAM_CHAT_ID = "1619752606"

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Erro ao enviar sinal: {e}")

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
        "HT05": 1 - (poisson.pmf(0, exp_h_ht * 0.45) * poisson.pmf(0, exp_a_ht * 0.45)),
        "exp_h": exp_h,
        "exp_a": exp_a
    }

# --- INTERFACE ---
st.title("⚽ Bot de Sinais Automáticos")

if st.button("🔔 Testar Conexão Telegram"):
    enviar_telegram("✅ Conexão estabelecida! O seu Bot de Futebol agora está integrado ao Telegram.")
    st.success("Mensagem de teste enviada!")

with st.expander("📖 MANUAL RÁPIDO"):
    st.write("1. Escolha os times. 2. Insira as Odds da sua casa na barra lateral. 3. Analise o EV Verde.")

liga_sel = st.sidebar.selectbox("Liga", list(LIGAS.keys()))
df_liga = carregar_dados(LIGAS[liga_sel])

if not df_liga.empty:
    st.write(f"✅ Dados da liga **{liga_sel}** carregados com sucesso.")
    
    # --- SEÇÃO 1: SCANNER DE SINAIS (TELEGRAM) ---
    st.header("📡 Scanner de Elite")
    if st.button("🚀 ESCANEAR LIGA E ENVIAR SINAIS (TELEGRAM)"):
        times_lista = sorted(df_liga['HomeTeam'].unique())
        encontrados = 0
        progresso = st.progress(0)
        total_combinacoes = len(times_lista) * (len(times_lista) - 1)
        passo = 0

        st.write("🔎 Buscando tendências de Over 0.5 HT, 1.5 e 2.5 FT...")
        
        # O scanner percorre todos os jogos possíveis da rodada
        for t1_scan in times_lista:
            for t2_scan in times_lista:
                if t1_scan != t2_scan:
                    passo += 1
                    progresso.progress(passo / total_combinacoes)
                    
                    res = analisar_partida(df_liga, t1_scan, t2_scan)
                    
                    # --- FILTROS DE ESTRATÉGIA ---
                    sinal = None
                    
                    # 1. Filtro Over 0.5 HT (Golo no 1º Tempo)
                    if res['HT05'] > 0.78:
                        sinal = {
                            "mercado": "Over 0.5 HT",
                            "prob": res['HT05'],
                            "odd_min": 1/res['HT05']
                        }
                    
                    # 2. Filtro Over 1.5 FT (Mínimo 2 golos no jogo)
                    elif res['O15'] > 0.82:
                        sinal = {
                            "mercado": "Over 1.5 FT",
                            "prob": res['O15'],
                            "odd_min": 1/res['O15']
                        }
                    
                    # 3. Filtro Over 2.5 FT (Mínimo 3 golos no jogo)
                    elif res['O25'] > 0.65:
                        sinal = {
                            "mercado": "Over 2.5 FT",
                            "prob": res['O25'],
                            "odd_min": 1/res['O25']
                        }

                    # Se algum critério for atingido, envia para o Telegram
                    if sinal:
                        msg = (f"🎯 *SINAL DE GOLS DETECTADO*\n\n"
                               f"🏟️ Jogo: {t1_scan} x {t2_scan}\n"
                               f"📈 Mercado: *{sinal['mercado']}*\n"
                               f"📊 Probabilidade: `{sinal['prob']:.1%}`\n"
                               f"💰 **ODD MÍNIMA SUGERIDA:** `{sinal['odd_min']:.2f}`\n\n"
                               f"🚀 *Compare com a odd da sua casa!*")
                        enviar_telegram(msg)
                        encontrados += 1
        
        st.success(f"✅ Scanner concluído! {encontrados} oportunidades enviadas ao Telegram.")

    st.divider()

    # --- SEÇÃO 2: ANÁLISE INDIVIDUAL DETALHADA ---
    st.header("🔎 Análise Detalhada de Jogo")
    
    # Seleção de times
    times = sorted(df_liga['HomeTeam'].unique())
    col1, col2 = st.columns(2)
    t1 = col1.selectbox("Mandante", times, index=0)
    t2 = col2.selectbox("Visitante", times, index=1)
    
    # Sidebar para inserção de Odds (Aproveitado do seu script anterior)
    st.sidebar.header("💰 Odds da sua Casa")
    o_h = st.sidebar.number_input("Odd Casa (1)", 1.0, step=0.01)
    o_d = st.sidebar.number_input("Odd Empate (X)", 1.0, step=0.01)
    o_a = st.sidebar.number_input("Odd Fora (2)", 1.0, step=0.01)
    st.sidebar.divider()
    o_ht = st.sidebar.number_input("Odd Over 0.5 HT", 1.0, step=0.01)
    o_15 = st.sidebar.number_input("Odd Over 1.5 FT", 1.0, step=0.01)
    o_25 = st.sidebar.number_input("Odd Over 2.5 FT", 1.0, step=0.01)

    if st.button("📊 GERAR ANÁLISE COMPLETA"):
        res = analisar_partida(df_liga, t1, t2)
        
        # 1. Info de Expectativa de Gols
        st.info(f"⚽ **Expectativa de Gols:** {t1} {res['exp_h']:.2f} x {res['exp_a']:.2f} {t2}")
        
        # 2. Tabela de Valor (EV) - Lógica de cores restaurada
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

        # 3. Histórico H2H (Restaurado e Limpo)
        st.divider()
        st.subheader("⚔️ Confrontos Diretos Recentes (H2H)")
        h2h = df_liga[((df_liga['HomeTeam'] == t1) & (df_liga['AwayTeam'] == t2)) | 
                     ((df_liga['HomeTeam'] == t2) & (df_liga['AwayTeam'] == t1))].tail(5)
        
        if not h2h.empty:
            h2h_view = h2h[['HomeTeam', 'FTHG', 'FTAG', 'AwayTeam']].copy()
            h2h_view.columns = ['Mandante', 'Gols Casa', 'Gols Fora', 'Visitante']
            st.table(h2h_view)
        else:
            st.warning("Sem histórico recente para este confronto na base de dados.")