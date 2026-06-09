"""
IoT Cloud Telemetry Hub — Streamlit Dashboard
Real-time monitoring of edge device sensor streams.
"""

import time
import requests
import pandas as pd
import streamlit as st
import altair as alt
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="IoT Telemetry Hub",
    layout="wide",
    page_icon="🌡️",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background: #0f1117; border-right: 1px solid #1e2130; }
    [data-testid="stSidebar"] * { color: #c9d1d9 !important; }
    [data-testid="stMetric"] { background: #161b22; border: 1px solid #21262d; border-radius: 10px; padding: 16px 20px; }
    [data-testid="stMetricLabel"] { font-size: 0.75rem !important; text-transform: uppercase; letter-spacing: 0.08em; color: #8b949e !important; }
    [data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; font-size: 1.8rem !important; font-weight: 600 !important; }
    .alert-critical { background: rgba(248,81,73,0.15); border: 1px solid #f85149; border-radius: 8px; padding: 12px 16px; color: #f85149; font-weight: 600; margin-bottom: 12px; }
    .alert-warn { background: rgba(210,153,34,0.15); border: 1px solid #d29922; border-radius: 8px; padding: 12px 16px; color: #d29922; font-weight: 600; margin-bottom: 12px; }
    h3 { color: #e6edf3 !important; font-weight: 600 !important; }
    [data-testid="stDataFrame"] { border: 1px solid #21262d; border-radius: 8px; }
    hr { border-color: #21262d !important; }
</style>
""", unsafe_allow_html=True)

# ── Supabase config ───────────────────────────────────────────────────────────

SUPABASE_BASE = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

STATUS_COLORS = {
    "OK":             "#3fb950",
    "WARN_TEMP":      "#d29922",
    "WARN_HUMIDITY":  "#d29922",
    "WARN_DRY":       "#d29922",
    "CRITICAL_TEMP":  "#f85149",
}

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🌡️ IoT Telemetry Hub")
    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    record_limit = st.slider("Records to fetch", min_value=10, max_value=200, value=50, step=10)
    auto_refresh  = st.toggle("Auto-refresh (10s)", value=False)
    st.markdown("---")
    st.markdown("### 🔍 Filter")
    device_filter_placeholder = st.empty()
    st.markdown("---")
    st.markdown("### 📡 Connection")
    st.markdown(f"`{SUPABASE_BASE[:40]}...`")
    st.caption("Supabase REST API · RLS enabled")
    st.markdown("---")
    if st.button("🔄 Refresh Now", use_container_width=True):
        st.rerun()

if auto_refresh:
    time.sleep(10)
    st.rerun()

# ── Data fetch ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=8)
def fetch_telemetry(limit: int) -> pd.DataFrame:
    url = f"{SUPABASE_BASE}?order=created_at.desc&limit={limit}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        df = pd.DataFrame(r.json())
        if not df.empty:
            df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
        return df
    except Exception as exc:
        st.error(f"❌ Failed to fetch data: {exc}")
        return pd.DataFrame()

df = fetch_telemetry(record_limit)

# ── Header ────────────────────────────────────────────────────────────────────

col_title, col_ts = st.columns([3, 1])
with col_title:
    st.markdown("# 🌡️ IoT Cloud Telemetry Hub")
    st.caption("Real-time edge device monitoring pipeline")
with col_ts:
    st.markdown(f"<br><small style='color:#8b949e'>Last fetched: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}</small>", unsafe_allow_html=True)

st.markdown("---")

if df.empty:
    st.info("⏳ Waiting for device data… Start `app.py` to begin streaming.")
    st.stop()

all_devices = sorted(df["device_id"].unique().tolist())
with device_filter_placeholder:
    selected_devices = st.multiselect("Devices", options=all_devices, default=all_devices)

if selected_devices:
    df = df[df["device_id"].isin(selected_devices)]

# ── Alert banners ─────────────────────────────────────────────────────────────

critical_rows = df[df["status_code"] == "CRITICAL_TEMP"]
warn_rows     = df[df["status_code"].str.startswith("WARN")]

if not critical_rows.empty:
    st.markdown(f'<div class="alert-critical">🚨 CRITICAL: High temperature detected on {", ".join(critical_rows["device_id"].unique())} — check hardware immediately.</div>', unsafe_allow_html=True)
elif not warn_rows.empty:
    st.markdown(f'<div class="alert-warn">⚠️ WARNING: Anomalous readings on {", ".join(warn_rows["device_id"].unique())}.</div>', unsafe_allow_html=True)

# ── KPI metrics ───────────────────────────────────────────────────────────────

latest      = df.iloc[0]
prev        = df.iloc[1] if len(df) > 1 else latest
temp_delta  = round(latest["temperature"] - prev["temperature"], 2)
humid_delta = round(latest["humidity"]    - prev["humidity"],    2)
total_alerts = len(df[df["status_code"] != "OK"])

m1, m2, m3, m4 = st.columns(4)
with m1: st.metric("🌡️ Latest Temperature", f"{latest['temperature']} °C", delta=f"{temp_delta:+.2f} °C")
with m2: st.metric("💧 Latest Humidity",    f"{latest['humidity']} %",    delta=f"{humid_delta:+.2f} %")
with m3: st.metric("📡 Active Devices",     len(all_devices))
with m4: st.metric("🔔 Alerts (shown)",     total_alerts, delta=None if total_alerts == 0 else f"{total_alerts} non-OK", delta_color="inverse")

st.markdown("---")

# ── Charts ────────────────────────────────────────────────────────────────────

chart_df = df.sort_values("created_at").copy()

tab_temp, tab_humid, tab_both = st.tabs(["🌡️ Temperature", "💧 Humidity", "📊 Combined"])

def make_line_chart(data, y_col, title, y_label):
    return (
        alt.Chart(data).mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("created_at:T", title="Time", axis=alt.Axis(format="%H:%M:%S")),
            y=alt.Y(f"{y_col}:Q", title=y_label, scale=alt.Scale(zero=False)),
            color=alt.Color("device_id:N", title="Device", scale=alt.Scale(scheme="tableau10")),
            tooltip=["device_id", "created_at:T", f"{y_col}:Q", "status_code"],
        )
        .properties(title=title, height=300)
        .configure_view(strokeWidth=0)
        .configure_axis(grid=True, gridColor="#21262d", labelColor="#8b949e", titleColor="#8b949e")
        .configure_title(color="#e6edf3")
        .configure_legend(labelColor="#c9d1d9", titleColor="#8b949e")
    )

with tab_temp:
    st.altair_chart(make_line_chart(chart_df, "temperature", "Temperature Over Time", "°C"), use_container_width=True)
with tab_humid:
    st.altair_chart(make_line_chart(chart_df, "humidity", "Humidity Over Time", "%"), use_container_width=True)
with tab_both:
    combined = (
        alt.layer(
            alt.Chart(chart_df).mark_line(strokeWidth=2).encode(
                x=alt.X("created_at:T", title="Time", axis=alt.Axis(format="%H:%M:%S")),
                y=alt.Y("temperature:Q", title="Temperature (°C)", scale=alt.Scale(zero=False)),
                color=alt.value("#f97583"),
                tooltip=["device_id", "created_at:T", "temperature:Q"],
            ),
            alt.Chart(chart_df).mark_line(strokeWidth=2, strokeDash=[4, 2]).encode(
                x="created_at:T",
                y=alt.Y("humidity:Q", title="Humidity (%)", scale=alt.Scale(zero=False)),
                color=alt.value("#79c0ff"),
                tooltip=["device_id", "created_at:T", "humidity:Q"],
            )
        )
        .resolve_scale(y="independent")
        .properties(title="Temperature & Humidity (dual axis)", height=300)
        .configure_view(strokeWidth=0)
        .configure_axis(grid=True, gridColor="#21262d", labelColor="#8b949e", titleColor="#8b949e")
        .configure_title(color="#e6edf3")
    )
    st.altair_chart(combined, use_container_width=True)

st.markdown("---")

# ── Per-device summary cards ──────────────────────────────────────────────────

st.markdown("### 📟 Per-Device Snapshot")
cols = st.columns(len(all_devices))
for i, dev in enumerate(all_devices):
    dev_df     = df[df["device_id"] == dev]
    dev_latest = dev_df.iloc[0] if not dev_df.empty else None
    with cols[i]:
        if dev_latest is not None:
            status = dev_latest["status_code"]
            color  = STATUS_COLORS.get(status, "#8b949e")
            st.markdown(f"""
                <div style='background:#161b22;border:1px solid #21262d;border-radius:10px;padding:16px;'>
                    <div style='font-size:0.7rem;color:#8b949e;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;'>{dev}</div>
                    <div style='font-family:JetBrains Mono,monospace;font-size:1.5rem;font-weight:600;'>{dev_latest['temperature']} °C</div>
                    <div style='font-family:JetBrains Mono,monospace;color:#8b949e;font-size:1rem;'>{dev_latest['humidity']} %</div>
                    <div style='margin-top:10px;font-size:0.78rem;font-weight:600;color:{color};'>{status}</div>
                    <div style='font-size:0.7rem;color:#8b949e;margin-top:4px;'>{dev_df.shape[0]} readings loaded</div>
                </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── Raw data ledger ───────────────────────────────────────────────────────────

st.markdown("### 🗄️ Ingestion Ledger")
display_df = df[["id", "created_at", "device_id", "temperature", "humidity", "status_code"]].copy()
display_df["created_at"] = display_df["created_at"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
display_df = display_df.rename(columns={"id": "ID", "created_at": "Timestamp", "device_id": "Device", "temperature": "Temp (°C)", "humidity": "Humidity (%)", "status_code": "Status"})
st.dataframe(display_df, use_container_width=True, hide_index=True,
    column_config={
        "Status": st.column_config.TextColumn("Status"),
        "Temp (°C)": st.column_config.NumberColumn("Temp (°C)", format="%.2f °C"),
        "Humidity (%)": st.column_config.NumberColumn("Humidity (%)", format="%.2f %%"),
    })
st.caption(f"Showing {len(display_df)} records · Supabase REST API · Auto-refresh: {'ON (10s)' if auto_refresh else 'OFF'}")