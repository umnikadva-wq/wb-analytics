import os
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("WB_TOKEN")
BASE_URL = "https://advert-api.wildberries.ru"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

st.set_page_config(page_title="WB Analytics", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# Ваши активные кампании
DEFAULT_CAMPAIGNS = [
    24846474, 29515227, 27975527, 34162114, 30690165, 29515195, 29368340, 29933103,
    29910151, 29515261, 34943206, 30690197, 26169608, 35051547, 26089907, 26954257,
    26836193, 34162025, 30690119, 35535754, 35051159, 34162072, 29688363, 29515209,
    27989885, 26089256, 35051583, 30690086, 27799478, 27336950, 35051947, 29515170,
    35386043, 25557656, 35818167, 29681838, 26011817
]

def get_stats(campaign_ids, begin_date, end_date):
    url = f"{BASE_URL}/adv/v3/fullstats"
    params = {
        "ids": ",".join(map(str, campaign_ids)),
        "beginDate": begin_date,
        "endDate": end_date
    }
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            st.warning("⏱ Превышен лимит запросов. Подождите 20 секунд...")
            return None
        return None
    except Exception as e:
        st.error(f"Ошибка: {e}")
        return None

def prepare_dataframe(stats):
    rows = []
    for camp in (stats or []):
        camp_id = camp.get('advertId')
        rows.append({
            'Кампания': camp_id,
            'Показы': camp.get('views', 0) or 0,
            'Клики': camp.get('clicks', 0) or 0,
            'Расход': round(camp.get('sum', 0) or 0, 2),
            'Заказы': camp.get('orders', 0) or 0,
            'Выручка': round(camp.get('sum_price', 0) or 0, 2),
            'CTR': round(camp.get('ctr', 0) or 0, 2),
            'CPC': round(camp.get('cpc', 0) or 0, 2),
            'CR': round(camp.get('cr', 0) or 0, 2),
        })
    
    df = pd.DataFrame(rows)
    if len(df) > 0:
        df['ДРР'] = (df['Расход'] / df['Выручка'] * 100).where(df['Выручка'] > 0, 0).round(2)
        df['CPZ'] = (df['Расход'] / df['Заказы']).where(df['Заказы'] > 0, 0).round(2)
    return df

# UI
st.title("📊 Аналитика рекламы Wildberries")
st.markdown("### 🎯 Ваши активные кампании")

st.sidebar.header("⚙️ Настройки")

# Выбор кампаний
st.sidebar.subheader("📋 Кампании")
use_all = st.sidebar.checkbox("Все 37 кампаний", value=True)

if use_all:
    selected_ids = DEFAULT_CAMPAIGNS
    st.sidebar.success(f"✅ Выбрано {len(selected_ids)} кампаний")
else:
    # Разрешаем выбрать часть
    selected_ids = st.sidebar.multiselect(
        "Выберите кампании:",
        options=DEFAULT_CAMPAIGNS,
        default=DEFAULT_CAMPAIGNS[:10]
    )

# Период
st.sidebar.subheader("📅 Период")
col1, col2 = st.sidebar.columns(2)
with col1:
    days_back = st.slider("Дней", 1, 30, 7)
with col2:
    end_date = st.date_input("До", datetime.now())

begin_date = (end_date - timedelta(days=days_back)).strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Обновить данные", type="primary", use_container_width=True):
    st.session_state["refresh"] = True
    st.session_state.pop("data", None)

if not TOKEN:
    st.error("❌ Токен не найден! Проверьте файл .env")
    st.stop()

# Загрузка данных
if selected_ids and ("refresh" in st.session_state or "data" not in st.session_state):
    with st.spinner(f"⏳ Загружаем статистику по {len(selected_ids)} кампаниям..."):
        # Разбиваем на группы по 50 (лимит API)
        all_stats = []
        for i in range(0, len(selected_ids), 50):
            batch = selected_ids[i:i+50]
            stats = get_stats(batch, begin_date, end_date_str)
            if stats:
                all_stats.extend(stats)
            else:
                st.warning(f"⚠️ Не удалось загрузить данные для группы {i//50 + 1}")
        
        if all_stats:
            df = prepare_dataframe(all_stats)
            st.session_state["data"] = df
            st.session_state["period"] = f"{begin_date} - {end_date_str}"
            st.success(f"✅ Загружено {len(df)} кампаний")
        else:
            st.error("❌ Не удалось загрузить данные. Проверьте токен и период.")

# Отображение
df = st.session_state.get("data")

if df is not None and len(df) > 0:
    # Фильтр
    df_active = df[df['Показы'] > 0].copy()
    
    if len(df_active) == 0:
        st.warning("⚠️ Нет кампаний с показами за выбранный период")
        st.stop()
    
    # KPI
    st.subheader("📈 Общие показатели")
    
    total_views = df_active['Показы'].sum()
    total_clicks = df_active['Клики'].sum()
    total_cost = df_active['Расход'].sum()
    total_orders = df_active['Заказы'].sum()
    total_revenue = df_active['Выручка'].sum()
    
    avg_ctr = (total_clicks / total_views * 100) if total_views > 0 else 0
    avg_cpc = (total_cost / total_clicks) if total_clicks > 0 else 0
    avg_drp = (total_cost / total_revenue * 100) if total_revenue > 0 else 0
    avg_cpz = (total_cost / total_orders) if total_orders > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👁 Показы", f"{total_views:,}")
    col2.metric("🖱 Клики", f"{total_clicks:,}")
    col3.metric("💰 Расход", f"{total_cost:,.0f} ₽")
    col4.metric("🛒 Заказы", f"{total_orders:,}")
    
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("💵 Выручка", f"{total_revenue:,.0f} ₽")
    col6.metric("📊 CTR", f"{avg_ctr:.2f}%")
    col7.metric("💳 CPC", f"{avg_cpc:.2f} ₽")
    col8.metric("📉 ДРР", f"{avg_drp:.1f}%")
    
    st.markdown("---")
    
    # Графики
    col1, col2 = st.columns(2)
    
    with col1:
        top_cost = df_active.nlargest(15, 'Расход')
        fig_cost = px.bar(
            top_cost,
            x='Расход',
            y='Кампания',
            orientation='h',
            title='💰 Топ-15 кампаний по расходу',
            color='Расход',
            color_continuous_scale='Reds',
            hover_data=['Клики', 'Заказы', 'CTR']
        )
        fig_cost.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_cost, use_container_width=True)
    
    with col2:
        df_orders = df_active[df_active['Заказы'] > 0]
        if len(df_orders) > 0:
            top_orders = df_orders.nlargest(15, 'Заказы')
            fig_orders = px.bar(
                top_orders,
                x='Заказы',
                y='Кампания',
                orientation='h',
                title='🛒 Топ-15 кампаний по заказам',
                color='Заказы',
                color_continuous_scale='Blues',
                hover_data=['Расход', 'Выручка', 'ДРР']
            )
            fig_orders.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_orders, use_container_width=True)
        else:
            st.info("ℹ️ Нет заказов за период")
    
    # ДРР
    st.markdown("---")
    st.subheader("📊 Эффективность кампаний (ДРР)")
    
    df_with_orders = df_active[df_active['Заказы'] > 0].copy()
    if len(df_with_orders) > 0:
        fig_drp = px.scatter(
            df_with_orders,
            x='ДРР',
            y='Заказы',
            size='Расход',
            color='ДРР',
            hover_name='Кампания',
            title='ДРР vs Заказы (размер = расход)',
            color_continuous_scale='RdYlGn_r',
            range_color=[0, 30]
        )
        fig_drp.add_vline(x=20, line_dash="dash", line_color="green", annotation_text="Хорошо (<20%)")
        fig_drp.add_vline(x=30, line_dash="dash", line_color="red", annotation_text="Плохо (>30%)")
        st.plotly_chart(fig_drp, use_container_width=True)
    
    # Таблица
    st.markdown("---")
    st.subheader("📋 Все кампании")
    
    display_df = df_active.copy()
    display_df['CTR'] = display_df['CTR'].apply(lambda x: f"{x:.2f}%")
    display_df['CPC'] = display_df['CPC'].apply(lambda x: f"{x:.2f} ₽")
    display_df['ДРР'] = display_df['ДРР'].apply(lambda x: f"{x:.1f}%")
    display_df['CPZ'] = display_df['CPZ'].apply(lambda x: f"{x:.2f} ₽")
    display_df['Расход'] = display_df['Расход'].apply(lambda x: f"{x:,.0f} ₽")
    display_df['Выручка'] = display_df['Выручка'].apply(lambda x: f"{x:,.0f} ₽")
    
    st.dataframe(
        display_df.sort_values('Расход', ascending=False),
        use_container_width=True,
        height=400
    )
    
    # Экспорт
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            "📥 Скачать CSV",
            data=df_active.to_csv(index=False, sep=';'),
            file_name=f"wb_stats_{begin_date}_{end_date_str}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        csv_excel = df_active.to_csv(index=False)
        st.download_button(
            "📥 Скачать Excel (CSV)",
            data=csv_excel,
            file_name=f"wb_stats_{begin_date}_{end_date_str}.xlsx",
            mime="text/csv",
            use_container_width=True
        )
    
    # Инфо
    st.markdown("---")
    st.caption(f"📊 Период: {st.session_state.get('period', 'N/A')} | Кампаний: {len(df_active)} из {len(selected_ids)}")
    
else:
    st.info("👈 Нажмите '🔄 Обновить данные' для загрузки статистики")
    st.markdown("""
    ### 💡 Как использовать:
    1. **Выберите период** в меню слева (по умолчанию 7 дней)
    2. **Нажмите '🔄 Обновить данные'**
    3. **Анализируйте результаты** в дашборде
    4. **Скачайте отчет** в CSV/Excel
    """)

st.markdown("---")
st.caption("📊 WB Analytics Dashboard | Wildberries Advertising API v3")
