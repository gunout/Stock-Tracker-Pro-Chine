import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
import pytz
import warnings
warnings.filterwarnings('ignore')

# Configuration de la page
st.set_page_config(
    page_title="Tracker Bourse Chine - yfinance",
    page_icon="🏮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration du fuseau horaire
USER_TIMEZONE = pytz.timezone('Europe/Paris')  # UTC+2 (heure d'été)
CHINA_TIMEZONE = pytz.timezone('Asia/Shanghai')
HK_TIMEZONE = pytz.timezone('Asia/Hong_Kong')

# Style CSS personnalisé
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #c41e3a;
        text-align: center;
        margin-bottom: 2rem;
        font-family: 'SimHei', 'Microsoft YaHei', sans-serif;
    }
    .stock-price {
        font-size: 2.5rem;
        font-weight: bold;
        color: #c41e3a;
        text-align: center;
    }
    .stock-change-positive {
        color: #00cc96;
        font-size: 1.2rem;
        font-weight: bold;
    }
    .stock-change-negative {
        color: #ef553b;
        font-size: 1.2rem;
        font-weight: bold;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .alert-box {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .alert-success {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .alert-warning {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
    }
    .chinese-market-note {
        background-color: #fff0f0;
        border-left: 4px solid #c41e3a;
        padding: 1rem;
        margin: 1rem 0;
    }
    .timezone-badge {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
        padding: 0.5rem 1rem;
        margin: 1rem 0;
        font-size: 0.9rem;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Initialisation des variables de session
if 'price_alerts' not in st.session_state:
    st.session_state.price_alerts = []

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}

if 'watchlist' not in st.session_state:
    st.session_state.watchlist = [
        '000858.SZ',  # Wuliangye
        '600519.SS',  # Kweichow Moutai
        '000333.SZ',  # Midea Group
        '601318.SS',  # Ping An Insurance
        '0700.HK',    # Tencent
        '9988.HK',    # Alibaba
        'BABA',       # Alibaba US
        'JD',         # JD.com US
        'BIDU',       # Baidu US
        'NTES'        # NetEase US
    ]

if 'notifications' not in st.session_state:
    st.session_state.notifications = []

if 'email_config' not in st.session_state:
    st.session_state.email_config = {
        'enabled': False,
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'email': '',
        'password': ''
    }

# Mapping des marchés chinois
CHINESE_EXCHANGES = {
    '.SS': 'Shanghai',
    '.SZ': 'Shenzhen',
    '.HK': 'Hong Kong',
    '': 'US Listed'
}

# Titre principal
st.markdown("<h1 class='main-header'>🏮 Tracker Bourse Chine - Analyse en Temps Réel</h1>", unsafe_allow_html=True)

# Bannière de fuseau horaire
current_time_utc2 = datetime.now(USER_TIMEZONE)
current_time_china = datetime.now(CHINA_TIMEZONE)

st.markdown(f"""
<div class='timezone-badge'>
    <b>🕐 Fuseaux horaires :</b><br>
    🇪🇺 Votre heure : {current_time_utc2.strftime('%H:%M:%S')} (UTC+2)<br>
    🇨🇳 Heure Chine : {current_time_china.strftime('%H:%M:%S')} (UTC+8)<br>
    📍 Décalage : {int((current_time_china.utcoffset().total_seconds() - current_time_utc2.utcoffset().total_seconds())/3600)} heures
</div>
""", unsafe_allow_html=True)

# Sidebar pour la navigation
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/china.png", width=80)
    st.title("Navigation")
    
    menu = st.radio(
        "Choisir une section",
        ["📈 Tableau de bord", 
         "💰 Portefeuille virtuel", 
         "🔔 Alertes de prix",
         "📧 Notifications email",
         "📤 Export des données",
         "🤖 Prédictions ML",
         "🏢 Indices Chine"]
    )
    
    st.markdown("---")
    
    # Configuration commune
    st.subheader("⚙️ Configuration")
    
    # Affichage du fuseau horaire
    st.caption(f"🕐 Fuseau : UTC+2 (Heure locale)")
    
    # Liste des symboles
    default_symbols = ["600519.SS", "000858.SZ", "0700.HK", "9988.HK", "BABA", "JD"]
    
    # Sélection du symbole principal
    symbol = st.selectbox(
        "Symbole principal",
        options=st.session_state.watchlist + ["Autre..."],
        index=0
    )
    
    if symbol == "Autre...":
        symbol = st.text_input("Entrer un symbole", value="600519.SS").upper()
        if symbol and symbol not in st.session_state.watchlist:
            st.session_state.watchlist.append(symbol)
    
    # Note sur les suffixes
    st.caption("""
    📍 Suffixes:
    - .SS: Shanghai
    - .SZ: Shenzhen
    - .HK: Hong Kong
    """)
    
    # Période et intervalle
    col1, col2 = st.columns(2)
    with col1:
        period = st.selectbox(
            "Période",
            options=["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"],
            index=2
        )
    
    with col2:
        interval_map = {
            "1m": "1 minute", "2m": "2 minutes", "5m": "5 minutes",
            "15m": "15 minutes", "30m": "30 minutes", "1h": "1 heure",
            "1d": "1 jour", "1wk": "1 semaine", "1mo": "1 mois"
        }
        interval = st.selectbox(
            "Intervalle",
            options=list(interval_map.keys()),
            format_func=lambda x: interval_map[x],
            index=4 if period == "1d" else 6
        )
    
    # Auto-refresh
    auto_refresh = st.checkbox("Actualisation automatique", value=False)
    if auto_refresh:
        refresh_rate = st.slider(
            "Fréquence (secondes)",
            min_value=5,
            max_value=60,
            value=30,
            step=5
        )

def convert_to_local_time(china_time):
    """Convertit l'heure de Chine en heure locale (UTC+2)"""
    if china_time.tzinfo is None:
        china_time = CHINA_TIMEZONE.localize(china_time)
    return china_time.astimezone(USER_TIMEZONE)

def format_time_for_display(dt):
    """Formate l'heure pour l'affichage avec indication du fuseau"""
    local_time = dt.astimezone(USER_TIMEZONE)
    return f"{local_time.strftime('%H:%M:%S')} (UTC+2)"

# Fonctions utilitaires
@st.cache_data(ttl=300)
def load_stock_data(symbol, period, interval):
    """Charge les données boursières"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)
        info = ticker.info
        
        # Convertir l'index en timezone-aware et ajuster à UTC+2
        if not hist.empty:
            hist.index = hist.index.tz_localize('UTC').tz_convert(USER_TIMEZONE)
        
        return hist, info
    except Exception as e:
        st.error(f"Erreur: {e}")
        return None, None

def get_exchange(symbol):
    """Détermine l'échange pour un symbole"""
    if symbol.endswith('.SS'):
        return 'Shanghai'
    elif symbol.endswith('.SZ'):
        return 'Shenzhen'
    elif symbol.endswith('.HK'):
        return 'Hong Kong'
    else:
        return 'US Listed'

def send_email_alert(subject, body, to_email):
    """Envoie une notification par email"""
    if not st.session_state.email_config['enabled']:
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = st.session_state.email_config['email']
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(
            st.session_state.email_config['smtp_server'], 
            st.session_state.email_config['smtp_port']
        )
        server.starttls()
        server.login(
            st.session_state.email_config['email'],
            st.session_state.email_config['password']
        )
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erreur d'envoi: {e}")
        return False

def check_price_alerts(current_price, symbol):
    """Vérifie les alertes de prix"""
    triggered = []
    for alert in st.session_state.price_alerts:
        if alert['symbol'] == symbol:
            if alert['condition'] == 'above' and current_price >= alert['price']:
                triggered.append(alert)
            elif alert['condition'] == 'below' and current_price <= alert['price']:
                triggered.append(alert)
    
    return triggered

def format_large_number(num):
    """Formate les grands nombres (pour la capitalisation en RMB/USD)"""
    if num > 1e12:
        return f"{num/1e12:.2f} T"
    elif num > 1e9:
        return f"{num/1e9:.2f} B"
    elif num > 1e6:
        return f"{num/1e6:.2f} M"
    else:
        return f"{num:.2f}"

def get_market_status():
    """Détermine le statut des marchés chinois en heure locale"""
    china_now = datetime.now(CHINA_TIMEZONE)
    china_hour = china_now.hour
    china_minute = china_now.minute
    china_weekday = china_now.weekday()
    
    # Weekend
    if china_weekday >= 5:
        return "Fermé (weekend)", "🔴"
    
    # Horaires de trading
    # Matin: 09:30 - 11:30
    # Après-midi: 13:00 - 15:00
    if (9 <= china_hour < 11) or (china_hour == 11 and china_minute <= 30):
        return "Ouvert (session matin)", "🟢"
    elif (13 <= china_hour < 15):
        return "Ouvert (session après-midi)", "🟢"
    elif (11 < china_hour < 13) or (china_hour == 11 and china_minute > 30) or (china_hour == 13 and china_minute == 0):
        return "Pause déjeuner", "🟡"
    else:
        return "Fermé", "🔴"

def format_currency(value, symbol):
    """Formate la monnaie selon le symbole"""
    if symbol.endswith('.HK'):
        return f"HK${value:.2f}"
    elif symbol.endswith(('.SS', '.SZ')):
        return f"¥{value:.2f}"
    else:
        return f"${value:.2f}"

# Chargement des données
hist, info = load_stock_data(symbol, period, interval)

if hist is not None and not hist.empty:
    current_price = hist['Close'].iloc[-1]
    
    # Vérification des alertes
    triggered_alerts = check_price_alerts(current_price, symbol)
    for alert in triggered_alerts:
        st.balloons()
        st.success(f"🎯 Alerte déclenchée pour {symbol} à {format_currency(current_price, symbol)}")
        
        # Notification email
        if st.session_state.email_config['enabled']:
            subject = f"🚨 Alerte prix - {symbol}"
            body = f"""
            <h2>Alerte de prix déclenchée</h2>
            <p><b>Symbole:</b> {symbol}</p>
            <p><b>Prix actuel:</b> {format_currency(current_price, symbol)}</p>
            <p><b>Condition:</b> {alert['condition']} {format_currency(alert['price'], symbol)}</p>
            <p><b>Date (UTC+2):</b> {datetime.now(USER_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}</p>
            """
            send_email_alert(subject, body, st.session_state.email_config['email'])
        
        # Retirer l'alerte si elle est à usage unique
        if alert.get('one_time', False):
            st.session_state.price_alerts.remove(alert)

# ============================================================================
# SECTION 1: TABLEAU DE BORD
# ============================================================================
if menu == "📈 Tableau de bord":
    # Note sur les marchés chinois
    st.markdown("""
    <div class='chinese-market-note'>
        <b>🏮 Marchés chinois :</b> Les données incluent les actions A (Shanghai/Shenzhen), 
        actions H (Hong Kong) et ADRs (US). Les horaires sont affichés en UTC+2.
    </div>
    """, unsafe_allow_html=True)
    
    # Statut du marché
    market_status, market_icon = get_market_status()
    st.info(f"{market_icon} Marché {symbol}: {market_status}")
    
    # Métriques principales
    exchange = get_exchange(symbol)
    st.subheader(f"📊 Aperçu en temps réel - {symbol} ({exchange})")
    
    col1, col2, col3, col4 = st.columns(4)
    
    previous_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
    change = current_price - previous_close
    change_pct = (change / previous_close) * 100
    
    with col1:
        st.metric(
            label="Prix actuel",
            value=format_currency(current_price, symbol),
            delta=f"{change:.2f} ({change_pct:.2f}%)"
        )
    
    with col2:
        day_high = hist['High'].iloc[-1]
        st.metric("Plus haut", format_currency(day_high, symbol))
    
    with col3:
        day_low = hist['Low'].iloc[-1]
        st.metric("Plus bas", format_currency(day_low, symbol))
    
    with col4:
        volume = hist['Volume'].iloc[-1]
        volume_formatted = f"{volume/1e6:.1f}M" if volume > 1e6 else f"{volume/1e3:.1f}K"
        st.metric("Volume", volume_formatted)
    
    # Dernière mise à jour avec fuseau horaire
    st.caption(f"Dernière mise à jour: {hist.index[-1].strftime('%Y-%m-%d %H:%M:%S')} UTC+2")
    
    # Graphique principal
    st.subheader("📉 Évolution du prix")
    
    fig = go.Figure()
    
    # Chandeliers ou ligne selon l'intervalle
    if interval in ["1m", "2m", "5m", "15m", "30m", "1h"]:
        fig.add_trace(go.Candlestick(
            x=hist.index,
            open=hist['Open'],
            high=hist['High'],
            low=hist['Low'],
            close=hist['Close'],
            name='Prix',
            increasing_line_color='#00cc96',
            decreasing_line_color='#ef553b'
        ))
    else:
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist['Close'],
            mode='lines',
            name='Prix',
            line=dict(color='#c41e3a', width=2)
        ))
    
    # Ajouter les moyennes mobiles
    ma_20 = hist['Close'].rolling(window=20).mean()
    ma_50 = hist['Close'].rolling(window=50).mean()
    
    fig.add_trace(go.Scatter(
        x=hist.index,
        y=ma_20,
        mode='lines',
        name='MA 20',
        line=dict(color='orange', width=1, dash='dash')
    ))
    
    fig.add_trace(go.Scatter(
        x=hist.index,
        y=ma_50,
        mode='lines',
        name='MA 50',
        line=dict(color='purple', width=1, dash='dash')
    ))
    
    # Volume
    fig.add_trace(go.Bar(
        x=hist.index,
        y=hist['Volume'],
        name='Volume',
        yaxis='y2',
        marker=dict(color='lightgray', opacity=0.3)
    ))
    
    # Ajouter des lignes verticales pour les heures de trading
    if interval in ["1m", "5m", "15m", "30m", "1h"]:
        # Convertir les heures de trading chinoises en UTC+2
        trading_morning_start = CHINA_TIMEZONE.localize(datetime.now().replace(hour=9, minute=30)).astimezone(USER_TIMEZONE)
        trading_morning_end = CHINA_TIMEZONE.localize(datetime.now().replace(hour=11, minute=30)).astimezone(USER_TIMEZONE)
        trading_afternoon_start = CHINA_TIMEZONE.localize(datetime.now().replace(hour=13, minute=0)).astimezone(USER_TIMEZONE)
        trading_afternoon_end = CHINA_TIMEZONE.localize(datetime.now().replace(hour=15, minute=0)).astimezone(USER_TIMEZONE)
        
        # Ajouter des annotations pour les périodes de trading
        fig.add_vrect(
            x0=trading_morning_start,
            x1=trading_morning_end,
            fillcolor="green",
            opacity=0.1,
            layer="below",
            line_width=0,
            annotation_text="Session matin"
        )
        fig.add_vrect(
            x0=trading_afternoon_start,
            x1=trading_afternoon_end,
            fillcolor="green",
            opacity=0.1,
            layer="below",
            line_width=0,
            annotation_text="Session après-midi"
        )
    
    fig.update_layout(
        title=f"{symbol} - {period} - {exchange} (heures UTC+2)",
        yaxis_title="Prix",
        yaxis2=dict(
            title="Volume",
            overlaying='y',
            side='right',
            showgrid=False
        ),
        xaxis_title="Date (UTC+2)",
        height=600,
        hovermode='x unified',
        template='plotly_white'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Informations sur l'entreprise
    with st.expander("ℹ️ Informations sur l'entreprise"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Nom :** {info.get('longName', 'N/A')}")
            st.write(f"**Secteur :** {info.get('sector', 'N/A')}")
            st.write(f"**Industrie :** {info.get('industry', 'N/A')}")
            st.write(f"**Site web :** {info.get('website', 'N/A')}")
            
            # Informations spécifiques Chine
            st.write(f"**Place de cotation :** {exchange}")
            if 'currency' in info:
                st.write(f"**Devise :** {info.get('currency', 'N/A')}")
        
        with col2:
            market_cap = info.get('marketCap', 0)
            if market_cap > 0:
                st.write(f"**Capitalisation :** {format_large_number(market_cap)}")
            else:
                st.write("**Capitalisation :** N/A")
            
            st.write(f"**P/E :** {info.get('trailingPE', 'N/A')}")
            st.write(f"**Dividende :** {info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "**Dividende :** N/A")
            st.write(f"**Beta :** {info.get('beta', 'N/A')}")

# ============================================================================
# SECTION 2: PORTEFEUILLE VIRTUEL
# ============================================================================
elif menu == "💰 Portefeuille virtuel":
    st.subheader("💰 Gestion de portefeuille virtuel - Actions Chine")
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.markdown("### ➕ Ajouter une position")
        with st.form("add_position"):
            symbol_pf = st.text_input("Symbole", value="600519.SS").upper()
            
            # Aide sur les suffixes
            st.caption("""
            Suffixes valides:
            - .SS (Shanghai)
            - .SZ (Shenzhen) 
            - .HK (Hong Kong)
            """)
            
            shares = st.number_input("Nombre d'actions", min_value=0.01, step=0.01)
            buy_price = st.number_input("Prix d'achat", min_value=0.01, step=0.01)
            
            if st.form_submit_button("Ajouter au portefeuille"):
                if symbol_pf and shares > 0:
                    if symbol_pf not in st.session_state.portfolio:
                        st.session_state.portfolio[symbol_pf] = []
                    
                    st.session_state.portfolio[symbol_pf].append({
                        'shares': shares,
                        'buy_price': buy_price,
                        'date': datetime.now(USER_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
                    })
                    st.success(f"✅ {shares} actions {symbol_pf} ajoutées")
    
    with col1:
        st.markdown("### 📊 Performance du portefeuille")
        
        if st.session_state.portfolio:
            portfolio_data = []
            total_value = 0
            total_cost = 0
            
            for symbol_pf, positions in st.session_state.portfolio.items():
                try:
                    ticker = yf.Ticker(symbol_pf)
                    current = ticker.history(period='1d')['Close'].iloc[-1]
                    exchange = get_exchange(symbol_pf)
                    
                    for pos in positions:
                        shares = pos['shares']
                        buy_price = pos['buy_price']
                        cost = shares * buy_price
                        value = shares * current
                        profit = value - cost
                        profit_pct = (profit / cost) * 100
                        
                        total_cost += cost
                        total_value += value
                        
                        # Formater selon la devise
                        if symbol_pf.endswith('.HK'):
                            currency = 'HK$'
                        elif symbol_pf.endswith(('.SS', '.SZ')):
                            currency = '¥'
                        else:
                            currency = '$'
                        
                        portfolio_data.append({
                            'Symbole': symbol_pf,
                            'Marché': exchange,
                            'Actions': shares,
                            "Prix d'achat": f"{currency}{buy_price:.2f}",
                            'Prix actuel': f"{currency}{current:.2f}",
                            'Valeur': f"{currency}{value:,.2f}",
                            'Profit': f"{currency}{profit:,.2f}",
                            'Profit %': f"{profit_pct:.1f}%"
                        })
                except:
                    st.warning(f"Impossible de charger {symbol_pf}")
            
            # Métriques globales
            total_profit = total_value - total_cost
            total_profit_pct = (total_profit / total_cost) * 100 if total_cost > 0 else 0
            
            col1_1, col1_2, col1_3 = st.columns(3)
            col1_1.metric("Valeur totale", f"${total_value:,.2f}")
            col1_2.metric("Coût total", f"${total_cost:,.2f}")
            col1_3.metric(
                "Profit total",
                f"${total_profit:,.2f}",
                delta=f"{total_profit_pct:.1f}%"
            )
            
            # Tableau des positions
            st.markdown("### 📋 Positions détaillées")
            df_portfolio = pd.DataFrame(portfolio_data)
            st.dataframe(df_portfolio, use_container_width=True)
            
            # Graphique de répartition
            fig_pie = px.pie(
                names=[p['Symbole'] for p in portfolio_data],
                values=[float(p['Valeur'].split('$')[-1].replace(',', '')) if '$' in p['Valeur'] 
                        else float(p['Valeur'].split('¥')[-1].replace(',', '')) for p in portfolio_data],
                title="Répartition du portefeuille"
            )
            st.plotly_chart(fig_pie)
            
            # Répartition par marché
            st.markdown("### 🏢 Répartition par marché")
            market_dist = {}
            for p in portfolio_data:
                market = p['Marché']
                value = float(p['Valeur'].split('$')[-1].replace(',', '')) if '$' in p['Valeur'] \
                        else float(p['Valeur'].split('¥')[-1].replace(',', ''))
                market_dist[market] = market_dist.get(market, 0) + value
            
            fig_market = px.bar(
                x=list(market_dist.keys()),
                y=list(market_dist.values()),
                title="Valeur par marché",
                labels={'x': 'Marché', 'y': 'Valeur (USD)'}
            )
            st.plotly_chart(fig_market)
            
            # Bouton pour vider le portefeuille
            if st.button("🗑️ Vider le portefeuille"):
                st.session_state.portfolio = {}
                st.rerun()
        else:
            st.info("Aucune position dans le portefeuille. Ajoutez des actions chinoises pour commencer !")

# ============================================================================
# SECTION 3: ALERTES DE PRIX
# ============================================================================
elif menu == "🔔 Alertes de prix":
    st.subheader("🔔 Gestion des alertes de prix")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### ➕ Créer une nouvelle alerte")
        with st.form("new_alert"):
            alert_symbol = st.text_input("Symbole", value=symbol).upper()
            exchange = get_exchange(alert_symbol)
            st.caption(f"Marché: {exchange}")
            
            alert_price = st.number_input(
                f"Prix cible ({format_currency(0, alert_symbol).split('0')[0]})", 
                min_value=0.01, 
                step=0.01, 
                value=float(current_price * 1.05)
            )
            
            col_cond, col_type = st.columns(2)
            with col_cond:
                condition = st.selectbox("Condition", ["above", "below"])
            with col_type:
                alert_type = st.selectbox("Type", ["Permanent", "Une fois"])
            
            one_time = alert_type == "Une fois"
            
            if st.form_submit_button("Créer l'alerte"):
                st.session_state.price_alerts.append({
                    'symbol': alert_symbol,
                    'price': alert_price,
                    'condition': condition,
                    'one_time': one_time,
                    'created': datetime.now(USER_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
                })
                st.success(f"✅ Alerte créée pour {alert_symbol} à {format_currency(alert_price, alert_symbol)}")
    
    with col2:
        st.markdown("### 📋 Alertes actives")
        if st.session_state.price_alerts:
            for i, alert in enumerate(st.session_state.price_alerts):
                with st.container():
                    st.markdown(f"""
                    <div class='alert-box alert-warning'>
                        <b>{alert['symbol']}</b> - {alert['condition']} {format_currency(alert['price'], alert['symbol'])}<br>
                        <small>Créée: {alert['created']} (UTC+2) | {('Usage unique' if alert['one_time'] else 'Permanent')}</small>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"Supprimer", key=f"del_alert_{i}"):
                        st.session_state.price_alerts.pop(i)
                        st.rerun()
        else:
            st.info("Aucune alerte active")

# ============================================================================
# SECTION 4: NOTIFICATIONS EMAIL
# ============================================================================
elif menu == "📧 Notifications email":
    st.subheader("📧 Configuration des notifications email")
    
    with st.form("email_config"):
        enabled = st.checkbox("Activer les notifications email", value=st.session_state.email_config['enabled'])
        
        col1, col2 = st.columns(2)
        with col1:
            smtp_server = st.text_input("Serveur SMTP", value=st.session_state.email_config['smtp_server'])
            smtp_port = st.number_input("Port SMTP", value=st.session_state.email_config['smtp_port'])
        
        with col2:
            email = st.text_input("Adresse email", value=st.session_state.email_config['email'])
            password = st.text_input("Mot de passe", type="password", value=st.session_state.email_config['password'])
        
        test_email = st.text_input("Email de test (optionnel)")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.form_submit_button("💾 Sauvegarder"):
                st.session_state.email_config = {
                    'enabled': enabled,
                    'smtp_server': smtp_server,
                    'smtp_port': smtp_port,
                    'email': email,
                    'password': password
                }
                st.success("Configuration sauvegardée !")
        
        with col_btn2:
            if st.form_submit_button("📨 Tester"):
                if test_email:
                    if send_email_alert(
                        "Test de notification",
                        f"<h2>Ceci est un test</h2><p>Votre configuration email fonctionne correctement !</p><p>Heure d'envoi (UTC+2): {datetime.now(USER_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}</p>",
                        test_email
                    ):
                        st.success("Email de test envoyé !")
                    else:
                        st.error("Échec de l'envoi")
    
    # Aperçu de la configuration
    with st.expander("📋 Aperçu de la configuration"):
        st.json(st.session_state.email_config)

# ============================================================================
# SECTION 5: EXPORT DES DONNÉES
# ============================================================================
elif menu == "📤 Export des données":
    st.subheader("📤 Export des données")
    
    if hist is not None:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Données historiques")
            # Afficher avec fuseau horaire
            display_hist = hist.copy()
            display_hist.index = display_hist.index.strftime('%Y-%m-%d %H:%M:%S (UTC+2)')
            st.dataframe(display_hist.tail(20))
            
            # Export CSV
            csv = hist.to_csv()
            st.download_button(
                label="📥 Télécharger en CSV",
                data=csv,
                file_name=f"{symbol}_data_{datetime.now(USER_TIMEZONE).strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        with col2:
            st.markdown("### 📈 Rapport PDF")
            st.info("Génération de rapport PDF (simulée)")
            
            # Statistiques
            st.markdown("**Statistiques:**")
            stats = {
                'Moyenne': hist['Close'].mean(),
                'Écart-type': hist['Close'].std(),
                'Min': hist['Close'].min(),
                'Max': hist['Close'].max(),
                'Variation totale': f"{(hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100:.2f}%"
            }
            
            for key, value in stats.items():
                if isinstance(value, float):
                    st.write(f"{key}: {format_currency(value, symbol)}")
                else:
                    st.write(f"{key}: {value}")
            
            # Export JSON
            json_data = {
                'symbol': symbol,
                'exchange': get_exchange(symbol),
                'last_update': datetime.now(USER_TIMEZONE).isoformat(),
                'timezone': 'UTC+2',
                'current_price': current_price,
                'currency': 'HKD' if symbol.endswith('.HK') else 'CNY' if symbol.endswith(('.SS', '.SZ')) else 'USD',
                'statistics': {k: (float(v) if isinstance(v, float) else v) for k, v in stats.items()},
                'data': hist.reset_index().to_dict(orient='records')
            }
            
            st.download_button(
                label="📥 Télécharger en JSON",
                data=json.dumps(json_data, indent=2, default=str),
                file_name=f"{symbol}_data_{datetime.now(USER_TIMEZONE).strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    else:
        st.warning("Aucune donnée à exporter")

# ============================================================================
# SECTION 6: PRÉDICTIONS ML
# ============================================================================
elif menu == "🤖 Prédictions ML":
    st.subheader("🤖 Prédictions avec Machine Learning - Actions Chine")
    
    if hist is not None and len(hist) > 30:
        st.markdown("### Modèle de prédiction (Régression polynomiale)")
        
        # Note sur les marchés chinois
        st.info("""
        ⚠️ Les prédictions pour les actions chinoises doivent tenir compte des spécificités du marché:
        - Vacances chinoises (Nouvel An, Fête nationale, etc.)
        - Régulations gouvernementales
        - Volatilité des marchés émergents
        - Décalage horaire (UTC+2 vs UTC+8)
        """)
        
        # Préparation des données
        df_pred = hist[['Close']].reset_index()
        df_pred['Days'] = (df_pred['Date'] - df_pred['Date'].min()).dt.days
        
        X = df_pred['Days'].values.reshape(-1, 1)
        y = df_pred['Close'].values
        
        # Configuration de la prédiction
        col1, col2 = st.columns(2)
        
        with col1:
            days_to_predict = st.slider("Jours à prédire", min_value=1, max_value=30, value=7)
            degree = st.slider("Degré du polynôme", min_value=1, max_value=5, value=2)
        
        with col2:
            st.markdown("### Options")
            show_confidence = st.checkbox("Afficher l'intervalle de confiance", value=True)
        
        # Entraînement du modèle
        model = make_pipeline(
            PolynomialFeatures(degree=degree),
            LinearRegression()
        )
        model.fit(X, y)
        
        # Prédictions
        last_day = X[-1][0]
        future_days = np.arange(last_day + 1, last_day + days_to_predict + 1).reshape(-1, 1)
        predictions = model.predict(future_days)
        
        # Dates futures (en UTC+2)
        last_date = df_pred['Date'].iloc[-1]
        future_dates = [last_date + timedelta(days=i+1) for i in range(days_to_predict)]
        
        # Visualisation
        fig_pred = go.Figure()
        
        # Données historiques
        fig_pred.add_trace(go.Scatter(
            x=df_pred['Date'],
            y=y,
            mode='lines',
            name='Historique',
            line=dict(color='blue')
        ))
        
        # Prédictions
        fig_pred.add_trace(go.Scatter(
            x=future_dates,
            y=predictions,
            mode='lines+markers',
            name='Prédictions',
            line=dict(color='red', dash='dash'),
            marker=dict(size=8)
        ))
        
        # Intervalle de confiance (simulé)
        if show_confidence:
            residuals = y - model.predict(X)
            std_residuals = np.std(residuals)
            
            upper_bound = predictions + 2 * std_residuals
            lower_bound = predictions - 2 * std_residuals
            
            fig_pred.add_trace(go.Scatter(
                x=future_dates + future_dates[::-1],
                y=np.concatenate([upper_bound, lower_bound[::-1]]),
                fill='toself',
                fillcolor='rgba(255,0,0,0.2)',
                line=dict(color='rgba(255,0,0,0)'),
                name='Intervalle de confiance (95%)'
            ))
        
        fig_pred.update_layout(
            title=f"Prédictions pour {symbol} - {days_to_predict} jours (UTC+2)",
            xaxis_title="Date (UTC+2)",
            yaxis_title="Prix",
            hovermode='x unified',
            template='plotly_white'
        )
        
        st.plotly_chart(fig_pred, use_container_width=True)
        
        # Tableau des prédictions
        st.markdown("### 📋 Prédictions détaillées")
        pred_df = pd.DataFrame({
            'Date (UTC+2)': [d.strftime('%Y-%m-%d') for d in future_dates],
            'Prix prédit': [format_currency(p, symbol) for p in predictions],
            'Variation %': [f"{(p/current_price - 1)*100:.2f}%" for p in predictions]
        })
        st.dataframe(pred_df, use_container_width=True)
        
        # Métriques de performance
        st.markdown("### 📊 Performance du modèle")
        mse = np.mean(residuals**2)
        rmse = np.sqrt(mse)
        mae = np.mean(np.abs(residuals))
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("RMSE", f"{format_currency(rmse, symbol)}")
        col_m2.metric("MAE", f"{format_currency(mae, symbol)}")
        col_m3.metric("R²", f"{model.score(X, y):.3f}")
        
        # Analyse des tendances
        st.markdown("### 📈 Analyse des tendances")
        last_price = current_price
        last_pred = predictions[-1]
        trend = "HAUSSIÈRE 📈" if last_pred > last_price else "BAISSIÈRE 📉" if last_pred < last_price else "NEUTRE ➡️"
        
        if last_pred > last_price * 1.05:
            strength = "Forte tendance haussière 🚀"
        elif last_pred > last_price:
            strength = "Légère tendance haussière 📈"
        elif last_pred < last_price * 0.95:
            strength = "Forte tendance baissière 🔻"
        elif last_pred < last_price:
            strength = "Légère tendance baissière 📉"
        else:
            strength = "Tendance latérale ⏸️"
        
        st.info(f"**Tendance prévue:** {trend} - {strength}")
        
        # Facteurs spécifiques Chine
        with st.expander("🇨🇳 Facteurs influençant les marchés chinois"):
            st.markdown("""
            **Facteurs macroéconomiques:**
            - Politique monétaire de la PBOC
            - Régulations gouvernementales (technologie, éducation, immobilier)
            - Tensions commerciales US-Chine
            - Données économiques (PIB, PMI, exportations)
            
            **Calendrier des résultats:**
            - Saison des résultats: avril, août, octobre
            - Vacances chinoises importantes
            - Congrès du Parti (tous les 5 ans)
            """)
        
    else:
        st.warning("Pas assez de données historiques pour faire des prédictions (minimum 30 points)")

# ============================================================================
# SECTION 7: INDICES CHINE
# ============================================================================
elif menu == "🏢 Indices Chine":
    st.subheader("🏢 Indices boursiers chinois")
    
    # Liste des indices chinois
    chinese_indices = {
        '^SSEC': 'Shanghai Composite (SSE)',
        '^SZSI': 'Shenzhen Composite (SZSE)',
        '^HSI': 'Hang Seng Index (Hong Kong)',
        '^HSCE': 'Hang Seng China Enterprises (H-shares)',
        '^FTXIN9': 'FTSE China A50',
        '000300.SS': 'CSI 300',
        '000905.SS': 'CSI 500',
        '399006.SZ': 'ChiNext (Startups)',
        'BABA': 'Alibaba (référence)',
        '0700.HK': 'Tencent (référence)'
    }
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.markdown("### 🇨🇳 Sélection d'indice")
        selected_index = st.selectbox(
            "Choisir un indice",
            options=list(chinese_indices.keys()),
            format_func=lambda x: f"{chinese_indices[x]} ({x})",
            index=0
        )
        
        st.markdown("### 📊 Performance des indices")
        
        # Période de comparaison
        perf_period = st.selectbox(
            "Période de comparaison",
            options=["1d", "5d", "1mo", "3mo", "6mo", "1y"],
            index=0
        )
    
    with col1:
        # Charger et afficher l'indice sélectionné
        try:
            index_ticker = yf.Ticker(selected_index)
            index_hist = index_ticker.history(period=perf_period)
            
            if not index_hist.empty:
                # Convertir en UTC+2
                index_hist.index = index_hist.index.tz_localize('UTC').tz_convert(USER_TIMEZONE)
                
                current_index = index_hist['Close'].iloc[-1]
                prev_index = index_hist['Close'].iloc[-2] if len(index_hist) > 1 else current_index
                index_change = current_index - prev_index
                index_change_pct = (index_change / prev_index) * 100
                
                st.markdown(f"### {chinese_indices[selected_index]}")
                
                col_i1, col_i2, col_i3 = st.columns(3)
                col_i1.metric("Valeur", f"{current_index:.2f}")
                col_i2.metric("Variation", f"{index_change:.2f}")
                col_i3.metric("Variation %", f"{index_change_pct:.2f}%", delta=f"{index_change_pct:.2f}%")
                
                st.caption(f"Dernière mise à jour: {index_hist.index[-1].strftime('%Y-%m-%d %H:%M:%S')} UTC+2")
                
                # Graphique de l'indice
                fig_index = go.Figure()
                fig_index.add_trace(go.Scatter(
                    x=index_hist.index,
                    y=index_hist['Close'],
                    mode='lines',
                    name=chinese_indices[selected_index],
                    line=dict(color='#c41e3a', width=2)
                ))
                
                fig_index.update_layout(
                    title=f"Évolution - {perf_period} (heures UTC+2)",
                    xaxis_title="Date (UTC+2)",
                    yaxis_title="Points",
                    height=400,
                    template='plotly_white'
                )
                
                st.plotly_chart(fig_index, use_container_width=True)
                
                # Statistiques de l'indice
                st.markdown("### 📈 Statistiques")
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                col_s1.metric("Plus haut", f"{index_hist['High'].max():.2f}")
                col_s2.metric("Plus bas", f"{index_hist['Low'].min():.2f}")
                col_s3.metric("Moyenne", f"{index_hist['Close'].mean():.2f}")
                col_s4.metric("Volatilité", f"{index_hist['Close'].pct_change().std()*100:.2f}%")
                
        except Exception as e:
            st.error(f"Erreur lors du chargement de l'indice: {e}")
    
    # Tableau de comparaison des indices
    st.markdown("### 📊 Comparaison des indices")
    
    comparison_data = []
    for idx, name in list(chinese_indices.items())[:6]:  # Limiter à 6 indices pour la performance
        try:
            ticker = yf.Ticker(idx)
            hist = ticker.history(period="5d")
            if not hist.empty:
                current = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[0]
                change_pct = ((current - prev) / prev) * 100
                
                comparison_data.append({
                    'Indice': name,
                    'Symbole': idx,
                    'Valeur': f"{current:.2f}",
                    'Variation 5j': f"{change_pct:.2f}%",
                    'Direction': '📈' if change_pct > 0 else '📉' if change_pct < 0 else '➡️'
                })
        except:
            pass
    
    if comparison_data:
        df_comparison = pd.DataFrame(comparison_data)
        st.dataframe(df_comparison, use_container_width=True)
    
    # Notes sur les indices chinois
    with st.expander("ℹ️ À propos des indices chinois"):
        st.markdown("""
        **Principaux indices chinois:**
        
        - **Shanghai Composite (SSE)** : Toutes les actions A de la bourse de Shanghai
        - **Shenzhen Composite (SZSE)** : Toutes les actions A de la bourse de Shenzhen
        - **Hang Seng Index (HSI)** : Principales actions de Hong Kong
        - **CSI 300** : 300 plus grandes actions A (Shanghai et Shenzhen)
        - **ChiNext** : Actions de croissance et startups à Shenzhen
        - **HSCE** (H-shares) : Entreprises chinoises cotées à Hong Kong
        
        **Horaires de trading (heure locale Chine - UTC+8):**
        - Shanghai/Shenzhen: 09:30-11:30, 13:00-15:00
        - Hong Kong: 09:30-12:00, 13:00-16:00
        
        **Correspondance avec UTC+2:**
        - Session matin: 03:30-05:30
        - Session après-midi: 07:00-09:00
        """)

# ============================================================================
# WATCHLIST ET DERNIÈRE MISE À JOUR
# ============================================================================
st.markdown("---")
col_w1, col_w2 = st.columns([3, 1])

with col_w1:
    st.subheader("📋 Watchlist Chine")
    
    # Organiser la watchlist par marché
    shanghai = [s for s in st.session_state.watchlist if s.endswith('.SS')]
    shenzhen = [s for s in st.session_state.watchlist if s.endswith('.SZ')]
    hongkong = [s for s in st.session_state.watchlist if s.endswith('.HK')]
    uslisted = [s for s in st.session_state.watchlist if not any(s.endswith(x) for x in ['.SS', '.SZ', '.HK'])]
    
    tabs = st.tabs(["Shanghai", "Shenzhen", "Hong Kong", "US Listed"])
    
    with tabs[0]:
        if shanghai:
            cols = st.columns(min(len(shanghai), 4))
            for i, sym in enumerate(shanghai):
                with cols[i % 4]:
                    try:
                        ticker = yf.Ticker(sym)
                        price = ticker.history(period='1d')['Close'].iloc[-1]
                        st.metric(sym, f"¥{price:.2f}")
                    except:
                        st.metric(sym, "N/A")
        else:
            st.info("Aucune action Shanghai")
    
    with tabs[1]:
        if shenzhen:
            cols = st.columns(min(len(shenzhen), 4))
            for i, sym in enumerate(shenzhen):
                with cols[i % 4]:
                    try:
                        ticker = yf.Ticker(sym)
                        price = ticker.history(period='1d')['Close'].iloc[-1]
                        st.metric(sym, f"¥{price:.2f}")
                    except:
                        st.metric(sym, "N/A")
        else:
            st.info("Aucune action Shenzhen")
    
    with tabs[2]:
        if hongkong:
            cols = st.columns(min(len(hongkong), 4))
            for i, sym in enumerate(hongkong):
                with cols[i % 4]:
                    try:
                        ticker = yf.Ticker(sym)
                        price = ticker.history(period='1d')['Close'].iloc[-1]
                        st.metric(sym, f"HK${price:.2f}")
                    except:
                        st.metric(sym, "N/A")
        else:
            st.info("Aucune action Hong Kong")
    
    with tabs[3]:
        if uslisted:
            cols = st.columns(min(len(uslisted), 4))
            for i, sym in enumerate(uslisted):
                with cols[i % 4]:
                    try:
                        ticker = yf.Ticker(sym)
                        price = ticker.history(period='1d')['Close'].iloc[-1]
                        st.metric(sym, f"${price:.2f}")
                    except:
                        st.metric(sym, "N/A")
        else:
            st.info("Aucune action US Listed")

with col_w2:
    # Heures actuelles
    utc2_time = datetime.now(USER_TIMEZONE)
    china_time = datetime.now(CHINA_TIMEZONE)
    
    st.caption(f"🕐 UTC+2: {utc2_time.strftime('%H:%M:%S')}")
    st.caption(f"🇨🇳 Chine: {china_time.strftime('%H:%M:%S')}")
    
    # Statut des marchés
    market_status, market_icon = get_market_status()
    st.caption(f"{market_icon} Marché: {market_status}")
    
    if auto_refresh:
        time.sleep(refresh_rate)
        st.rerun()

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray; font-size: 0.8rem;'>"
    "🏮 Tracker Bourse Chine - Données fournies par yfinance | "
    "⚠️ Données avec délai possible | 🇨🇳 Marchés: Shanghai, Shenzhen, Hong Kong | "
    "🕐 Tous les horaires en UTC+2 (heure de Paris/Bruxelles/Amsterdam)"
    "</p>",
    unsafe_allow_html=True
)
