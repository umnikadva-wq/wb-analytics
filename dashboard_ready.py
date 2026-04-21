import os
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import plotly.express as px
from dotenv import load_dotenv

# --- НАСТРОЙКИ ---
load_dotenv()
TOKEN = os.getenv("WB_TOKEN")
if not TOKEN:
    TOKEN = st.secrets.get("WB_TOKEN", "")

BASE_URL = "https://advert-api.wildberries.ru"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Ваши активные кампании (ID)
DEFAULT_CAMPAIGNS = [
    24846474, 29515227, 27975527, 34162114, 30690165, 29515195, 29368340, 29933103,
    29910151, 29515261, 34943206, 30690197, 26169608, 35051547, 26089907, 26954257,
    26836193, 34162025, 30690119, 35535754, 35051159, 34162072, 29688363, 29515209,
    27989885, 26089256, 35051583, 30690086, 27799478, 27336950, 35051947, 29515170,
    35386043, 25557656, 35818167, 29681838, 26011817
]

# --- ФУНКЦИИ ---

def get_campaign_names():
    """Получает словарь {ID: Название}"""
    url = f"{BASE_URL}/api/advert/v2/adverts"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            campaigns = resp.json().get('adverts', [])
            return {c['id']: c.get('settings', {}).get('name', f"ID {c['id']}") for c in campaigns}
    except:
        pass
    return {}

def get_stats_data(campaign_ids, begin_date, end_date):
    """Загружает статистику и возвращает DataFrame"""
    url = f"{BASE_URL}/adv/v3/fullstats"
    params = {
        "ids": ",".join(map(str, campaign_ids)),
        "beginDate": begin_date,
        "endDate": end_date
    }
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if not data: 
                return pd.DataFrame()
            
            rows = []
            for camp in data:
                rows.append({
                    'Кампания': camp.get('advertId'),
                    'Показы': camp.get('views', 0) or 0,
                    'Клики': camp.get('clicks', 0) or 0,
                    'Расход': camp.get('sum', 0) or 0,
                    'Заказы': camp.get('orders', 0) or 0,
                    'Выручка': camp.get('sum_price', 0) or 0,
                    'CTR': camp.get('ctr', 0) or 0,
                    'CPC': camp.get('cpc', 0) or 0,
                })
            return pd.DataFrame(rows)
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def process_data(df, names_dict):
    """Добавляет названия и считает метрики"""
    if df.empty: return df
    
    df['Название'] = df['Кампания'].map(names_dict).fillna(df['Кампания'])
    df['ДРР'] = (df['Расход'] / df['Выручка'] * 100).where(df['Выручка'] > 0, 0).round(2)
    df['CPZ'] = (df['Расход'] / df['Заказы']).where(df['Заказы'] > 0, 0).round(2)
    return df

def calculate_growth(curr, prev):
    """Считает % изменения"""
    if prev == 0: return 0 if curr == 0 else 100
    return ((curr - prev) / prev) * 100

# --- ИНТЕРФЕЙС ---

st.set_page_config(page_title="WB Analytics Pro", page_icon="🚀", layout="wide")
st.title("🚀 WB Analytics Pro")

# Боковая панель
st.sidebar.header("⚙️ Настройки")

# Период
days_back = st.sidebar.slider("Дней назад", 7, 30, 7)
end_date = st.sidebar.date_input("Дата окончания", datetime.now())

begin_date = (end_date - timedelta(days=days_back)).strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")

# Даты для сравнения (предыдущий период)
prev_end = end_date - timedelta(days=days_back)
prev_begin = prev_end - timedelta(days=days_back)
prev_begin_str = prev_begin.strftime("%Y-%m-%d")
prev_end_str = prev_end.strftime("%Y-%m-%d")

if st.sidebar.button("🔄 Обновить данные", type="primary", use_container_width=True):
    st.session_state["refresh"] = True
    # Если данные были пустыми, принудительно удаляем их, чтобы перезагрузить
    if "df_curr" in st.session_state and st.session_state["df_curr"].empty:
        del st.session_state["df_curr"]

# Загрузка данных
if TOKEN:
    needs_fetch = False
    
    # Логика: грузим, если данных нет ИЛИ нажали кнопку ИЛИ данные пустые
    if "df_curr" not in st.session_state:
        needs_fetch = True
    elif st.session_state.get("refresh"):
        needs_fetch = True
    elif st.session_state["df_curr"].empty:
        needs_fetch = True
    
    if needs_fetch:
        with st.spinner("🔍 Загружаем данные (это займет ~15 сек)..."):
            names_map = get_campaign_names()
            
            # 1. Текущий период
            df_raw_curr = get_stats_data(DEFAULT_CAMPAIGNS, begin_date, end_date_str)
            df_curr = process_data(df_raw_curr, names_map)
            
            # 2. Предыдущий период
            df_raw_prev = get_stats_data(DEFAULT_CAMPAIGNS, prev_begin_str, prev_end_str)
            df_prev = process_data(df_raw_prev, names_map)
            
            st.session_state["df_curr"] = df_curr
            st.session_state["df_prev"] = df_prev
            st.session_state["names"] = names_map
            
            # Убираем флаг обновления после загрузки
            if "refresh" in st.session_state:
                del st.session_state["refresh"]

df_curr = st.session_state.get("df_curr", pd.DataFrame())
df_prev = st.session_state.get("df_prev", pd.DataFrame())

if not df_curr.empty:
    # --- СРАВНЕНИЕ (MERGE) ---
    df_compare = df_curr.merge(
        df_prev[['Кампания', 'Показы', 'Клики', 'Расход', 'Заказы', 'Выручка']], 
        on='Кампания', 
        suffixes=('_curr', '_prev'), 
        how='left'
    ).fillna(0)

    # Считаем дельту
    df_compare['d_Views'] = calculate_growth(df_compare['Показы_curr'], df_compare['Показы_prev'])
    df_compare['d_Clicks'] = calculate_growth(df_compare['Клики_curr'], df_compare['Клики_prev'])
    df_compare['d_Cost'] = calculate_growth(df_compare['Расход_curr'], df_compare['Расход_prev'])
    df_compare['d_Orders'] = calculate_growth(df_compare['Заказы_curr'], df_compare['Заказы_prev'])
    df_compare['d_Revenue'] = calculate_growth(df_compare['Выручка_curr'], df_compare['Выручка_prev'])

    # --- KPI КАРТОЧКИ ---
    st.subheader("📊 Сводка за период")
    
    total_views = df_compare['Показы_curr'].sum()
    total_clicks = df_compare['Клики_curr'].sum()
    total_cost = df_compare['Расход_curr'].sum()
    total_orders = df_compare['Заказы_curr'].sum()
    total_revenue = df_compare['Выручка_curr'].sum()
    
    d_views = calculate_growth(total_views, df_compare['Показы_prev'].sum())
    d_clicks = calculate_growth(total_clicks, df_compare['Клики_prev'].sum())
    d_cost = calculate_growth(total_cost, df_compare['Расход_prev'].sum())
    d_orders = calculate_growth(total_orders, df_compare['Заказы_prev'].sum())
    d_revenue = calculate_growth(total_revenue, df_compare['Выручка_prev'].sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("👁 Показы", f"{total_views:,}", f"{d_views:.1f}%")
    c2.metric("🖱 Клики", f"{total_clicks:,}", f"{d_clicks:.1f}%")
    c3.metric("💰 Расход", f"{total_cost:,.0f} ₽", f"{d_cost:.1f}%")
    c4.metric("🛒 Заказы", f"{total_orders:,}", f"{d_orders:.1f}%")
    c5.metric("💵 Выручка", f"{total_revenue:,.0f} ₽", f"{d_revenue:.1f}%")

    st.markdown("---")
    
    # --- ТАБЛИЦА ---
    st.subheader("📋 Детализация по кампаниям")
    
    table = df_compare[['Название', 'Показы_curr', 'd_Views', 'Клики_curr', 'd_Clicks', 'Расход_curr', 'd_Cost', 'Заказы_curr', 'd_Orders', 'Выручка_curr', 'd_Revenue']].copy()
    table = table.rename(columns={
        'Название': 'Кампания',
        'Показы_curr': 'Показы', 'd_Views': 'Δ Показы %',
        'Клики_curr': 'Клики', 'd_Clicks': 'Δ Клики %',
        'Расход_curr': 'Расход', 'd_Cost': 'Δ Расход %',
        'Заказы_curr': 'Заказы', 'd_Orders': 'Δ Заказы %',
        'Выручка_curr': 'Выручка', 'd_Revenue': 'Δ Выручка %'
    })

    def color_delta(val):
        if pd.isnull(val): return ''
        color = 'green' if val > 0 else 'red'
        return f'color: {color}'

    st.dataframe(
        table.style.format({
            'Расход': '{:,.0f} ₽', 'Выручка': '{:,.0f} ₽',
            'Δ Показы %': '{:.1f}%', 'Δ Клики %': '{:.1f}%', 
            'Δ Расход %': '{:.1f}%', 'Δ Заказы %': '{:.1f}%', 'Δ Выручка %': '{:.1f}%'
        }).applymap(color_delta, subset=['Δ Показы %', 'Δ Клики %', 'Δ Расход %', 'Δ Заказы %', 'Δ Выручка %']),
        use_container_width=True,
        height=500
    )

else:
    if not TOKEN:
        st.error("❌ Ошибка: Токен не найден.")
    else:
        st.info("👈 Нажмите '🔄 Обновить данные' слева, чтобы загрузить статистику.")
