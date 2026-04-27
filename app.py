import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="FHH AI Stock Optimizer",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stMetric { background: white; border-radius: 10px; padding: 15px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
    .block-container { padding-top: 2rem; }
    h1 { color: #1a1a2e; font-weight: 700; }
    h2 { color: #16213e; font-weight: 600; }
    h3 { color: #0f3460; }
    .alert-red    { background: #fff0f0; border-left: 4px solid #e53935; padding: 12px 16px; border-radius: 4px; margin: 6px 0; }
    .alert-orange { background: #fffde7; border-left: 4px solid #fdd835; padding: 12px 16px; border-radius: 4px; margin: 6px 0; }
    .alert-yellow { background: #fffde7; border-left: 4px solid #fdd835; padding: 12px 16px; border-radius: 4px; margin: 6px 0; }
    .alert-green  { background: #f0fff4; border-left: 4px solid #43a047; padding: 12px 16px; border-radius: 4px; margin: 6px 0; }
    .card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin-bottom: 16px; }
    .badge-red    { background:#e53935; color:white; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600; }
    .badge-orange { background:#fdd835; color:#5f4200; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600; }
    .badge-green  { background:#43a047; color:white; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600; }
    .fhh-header { background: linear-gradient(135deg, #0f3460, #16213e); color:white; padding:20px 28px; border-radius:12px; margin-bottom:24px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────
@st.cache_data
def load_data():
    sales = pd.read_csv("data/fhh_sales_history.csv", parse_dates=["date"])
    products = pd.read_csv("data/fhh_products.csv")
    return sales, products

sales_df, products_df = load_data()

# ─────────────────────────────────────────────
# FORECASTING ENGINE
# ─────────────────────────────────────────────
def forecast_product(sku, months_ahead=4):
    """Simple but effective seasonal + trend forecasting."""
    data = sales_df[sales_df["sku"] == sku].copy()
    data = data.sort_values("date")
    data["month"] = data["date"].dt.month

    # Monthly seasonal index — convert to dict (pandas 2.x safe)
    seasonal_avg = data.groupby("month")["units_sold"].mean()
    overall_avg  = float(data["units_sold"].mean())
    seasonal_idx = (seasonal_avg / overall_avg).to_dict()

    # Linear trend using numpy arrays directly
    t = np.arange(len(data))
    if len(data) > 2:
        coeffs = np.polyfit(t, data["units_sold"].values, 1)
        trend_slope = float(coeffs[0])
    else:
        trend_slope = 0.0

    last_date = data["date"].iloc[-1]
    last_val  = float(data["units_sold"].iloc[-3:].mean())

    forecasts = []
    for i in range(1, months_ahead + 1):
        # Build future date safely without DateOffset arithmetic
        future_month = ((last_date.month - 1 + i) % 12) + 1
        future_year  = last_date.year + ((last_date.month - 1 + i) // 12)
        future_date  = pd.Timestamp(year=future_year, month=future_month, day=1)

        base      = last_val + trend_slope * i
        s_idx     = seasonal_idx.get(future_month, 1.0)
        predicted = max(int(base * s_idx), 0)
        lower     = int(predicted * 0.88)
        upper     = int(predicted * 1.12)
        forecasts.append({
            "date":     future_date,
            "forecast": predicted,
            "lower":    lower,
            "upper":    upper,
        })
    return pd.DataFrame(forecasts)

# ─────────────────────────────────────────────
# STOCK STATUS CALCULATOR
# ─────────────────────────────────────────────
def get_stock_status(product, forecast_df):
    current_stock  = product["current_stock"]
    reorder_point  = product["reorder_point"]
    max_stock      = product["max_stock"]
    lead_time      = product["lead_time_days"]

    avg_monthly_demand = forecast_df["forecast"].mean()
    avg_daily_demand   = avg_monthly_demand / 30
    days_of_stock      = current_stock / avg_daily_demand if avg_daily_demand > 0 else 999

    # Recommended order quantity
    next_month_demand  = forecast_df["forecast"].iloc[0]
    order_qty          = max(0, int(next_month_demand * 1.15) - current_stock)

    if days_of_stock < lead_time + 7:
        status = "STOCKOUT RISK"
        color  = "red"
    elif current_stock > max_stock * 0.85:
        status = "OVERSTOCK"
        color  = "orange"
    elif current_stock < reorder_point:
        status = "ORDER NOW"
        color  = "orange"
    else:
        status = "HEALTHY"
        color  = "green"

    return {
        "status":            status,
        "color":             color,
        "days_of_stock":     round(days_of_stock, 1),
        "avg_daily_demand":  round(avg_daily_demand, 1),
        "recommended_order": order_qty,
        "next_month_demand": next_month_demand,
    }

# ─────────────────────────────────────────────
# PRE-COMPUTE ALL FORECASTS
# ─────────────────────────────────────────────
@st.cache_data
def compute_all():
    results = {}
    for _, p in products_df.iterrows():
        fc     = forecast_product(p["sku"])
        status = get_stock_status(p, fc)
        results[p["sku"]] = {"product": p, "forecast": fc, "status": status}
    return results

all_results = compute_all()

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.image("assets/fhh_logo.webp", width=180)
    st.markdown("---")
    st.markdown("### Navigation")
    page = st.radio("Navigation", ["📊 Dashboard", "📈 Demand Forecast", "📦 Order Recommendations", "🚨 Alerts"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### Filters")
    categories   = ["All"] + list(products_df["category"].unique())
    selected_cat = st.selectbox("Category", categories)
    st.markdown("---")
    st.caption("FHH AI Optimizer v1.0 | Built by Malia Group")

# Filter products
if selected_cat == "All":
    filtered_skus = products_df["sku"].tolist()
else:
    filtered_skus = products_df[products_df["category"] == selected_cat]["sku"].tolist()

filtered_results = {k: v for k, v in all_results.items() if k in filtered_skus}

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.markdown("""
<div class="fhh-header">
  <h2 style="color:white;margin:0;font-size:22px;">📦 Fine Hygienic Holding — AI Demand & Stock Optimizer</h2>
  <p style="color:#a8c4e0;margin:6px 0 0;">Powered by AI · Real-time forecasting · Overstock & stockout prevention</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# PAGE 1: DASHBOARD
# ─────────────────────────────────────────────
if page == "📊 Dashboard":

    # KPI row
    total_products  = len(filtered_results)
    stockout_risk   = sum(1 for r in filtered_results.values() if r["status"]["color"] == "red")
    overstock_count = sum(1 for r in filtered_results.values() if r["status"]["status"] == "OVERSTOCK")
    healthy_count   = sum(1 for r in filtered_results.values() if r["status"]["color"] == "green")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Products",    total_products)
    c2.metric("🔴 Stockout Risk",  stockout_risk,   delta=f"Needs immediate action" if stockout_risk else "None")
    c3.metric("🟡 Overstock",      overstock_count, delta=f"Review orders" if overstock_count else "None")
    c4.metric("🟢 Healthy Stock",  healthy_count)

    st.markdown("---")
    st.markdown("### Product Stock Status")

    # Product cards
    for sku, res in filtered_results.items():
        p      = res["product"]
        status = res["status"]
        fc     = res["forecast"]

        color_map = {"red": "#e53935", "orange": "#fdd835", "green": "#43a047"}
        clr       = color_map[status["color"]]
        pct_stock = min(int(p["current_stock"] / p["max_stock"] * 100), 100)

        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
            with col1:
                st.markdown(f"**{p['name']}**")
                st.caption(f"SKU: {p['sku']} · {p['category']}")
            with col2:
                st.metric("Current Stock", f"{int(p['current_stock']):,} {p['unit']}")
            with col3:
                st.metric("Days of Stock", f"{status['days_of_stock']} days")
            with col4:
                st.metric("Next Month Forecast", f"{status['next_month_demand']:,}")
            with col5:
                badge_class = f"badge-{status['color']}"
                st.markdown(f"<br><span class='{badge_class}'>{status['status']}</span>", unsafe_allow_html=True)

            # Mini progress bar
            st.progress(pct_stock / 100, text=f"Stock level: {pct_stock}% of max capacity")
            st.markdown("---")

    # Stock overview chart
    st.markdown("### Stock Levels vs. Reorder Points")
    names         = [res["product"]["name"].split("(")[0].strip() for res in filtered_results.values()]
    current_stock = [res["product"]["current_stock"] for res in filtered_results.values()]
    reorder_pts   = [res["product"]["reorder_point"] for res in filtered_results.values()]
    colors        = [{"red":"#e53935","orange":"#fdd835","green":"#43a047"}[res["status"]["color"]] for res in filtered_results.values()]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Current Stock", x=names, y=current_stock, marker_color=colors, opacity=0.85))
    fig.add_trace(go.Scatter(name="Reorder Point", x=names, y=reorder_pts,
                             mode="lines+markers", line=dict(color="#e53935", dash="dash", width=2),
                             marker=dict(size=8)))
    fig.update_layout(height=380, plot_bgcolor="white", paper_bgcolor="white",
                      legend=dict(orientation="h", y=1.12),
                      xaxis=dict(tickangle=-25), yaxis_title="Units")
    st.plotly_chart(fig, width='stretch')

# ─────────────────────────────────────────────
# PAGE 2: DEMAND FORECAST
# ─────────────────────────────────────────────
elif page == "📈 Demand Forecast":

    st.markdown("### AI Demand Forecast — Next 4 Months")
    st.caption("Forecast uses seasonal patterns + growth trend from 24 months of historical data")

    selected_sku  = st.selectbox("Select Product", options=filtered_skus,
                                  format_func=lambda x: products_df[products_df["sku"]==x]["name"].values[0])

    if selected_sku:
        res       = all_results[selected_sku]
        fc        = res["forecast"]
        p         = res["product"]
        hist_data = sales_df[sales_df["sku"] == selected_sku].sort_values("date")

        col1, col2, col3 = st.columns(3)
        col1.metric("Avg Monthly Demand (hist.)", f"{int(hist_data['units_sold'].mean()):,}")
        col2.metric("Next Month Forecast",         f"{fc['forecast'].iloc[0]:,}")
        col3.metric("4-Month Total Forecast",      f"{fc['forecast'].sum():,}")

        # Forecast chart
        fig = go.Figure()

        # Historical
        fig.add_trace(go.Scatter(
            x=hist_data["date"], y=hist_data["units_sold"],
            name="Historical Sales", mode="lines+markers",
            line=dict(color="#1565c0", width=2),
            marker=dict(size=5)
        ))

        # Confidence band
        fig.add_trace(go.Scatter(
            x=pd.concat([fc["date"], fc["date"][::-1]]),
            y=pd.concat([fc["upper"], fc["lower"][::-1]]),
            fill="toself", fillcolor="rgba(67,160,71,0.15)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Confidence Range", showlegend=True
        ))

        # Forecast line
        fig.add_trace(go.Scatter(
            x=fc["date"], y=fc["forecast"],
            name="AI Forecast", mode="lines+markers",
            line=dict(color="#43a047", width=3, dash="dot"),
            marker=dict(size=10, symbol="diamond")
        ))

        # Vertical divider — add_vline broken in Plotly 6, use add_shape instead
        last_hist = hist_data["date"].max()
        fig.add_shape(
            type="line",
            x0=str(last_hist), x1=str(last_hist),
            y0=0, y1=1,
            xref="x", yref="paper",
            line=dict(dash="dash", color="gray", width=1.5)
        )
        fig.add_annotation(
            x=str(last_hist), y=1,
            xref="x", yref="paper",
            text="Forecast Start",
            showarrow=False,
            xanchor="left",
            font=dict(size=11, color="gray"),
            bgcolor="white"
        )

        fig.update_layout(
            height=420, plot_bgcolor="white", paper_bgcolor="white",
            xaxis_title="Month", yaxis_title=f"Units ({p['unit']})",
            legend=dict(orientation="h", y=1.12),
            hovermode="x unified"
        )
        st.plotly_chart(fig, width='stretch')

        # Forecast table
        st.markdown("#### Monthly Forecast Breakdown")
        fc_display = fc.copy()
        fc_display["Month"]     = fc_display["date"].dt.strftime("%B %Y")
        fc_display["Forecast"]  = fc_display["forecast"].apply(lambda x: f"{x:,}")
        fc_display["Low Est."]  = fc_display["lower"].apply(lambda x: f"{x:,}")
        fc_display["High Est."] = fc_display["upper"].apply(lambda x: f"{x:,}")
        st.dataframe(fc_display[["Month", "Low Est.", "Forecast", "High Est."]], width='stretch', hide_index=True)

        # Seasonal insight
        st.markdown("#### Seasonal Pattern")
        seasonal_data = hist_data.copy()
        seasonal_data["month_name"] = seasonal_data["date"].dt.strftime("%b")
        seasonal_data["month_num"]  = seasonal_data["date"].dt.month
        monthly_avg = seasonal_data.groupby(["month_num","month_name"])["units_sold"].mean().reset_index().sort_values("month_num")

        fig2 = px.bar(monthly_avg, x="month_name", y="units_sold",
                      color="units_sold", color_continuous_scale="Blues",
                      labels={"units_sold": "Avg Units Sold", "month_name": "Month"})
        fig2.update_layout(height=280, plot_bgcolor="white", paper_bgcolor="white", showlegend=False)
        st.plotly_chart(fig2, width='stretch')

# ─────────────────────────────────────────────
# PAGE 3: ORDER RECOMMENDATIONS
# ─────────────────────────────────────────────
elif page == "📦 Order Recommendations":

    st.markdown("### AI Order Recommendations")
    st.caption("Based on forecasted demand, current stock, reorder points, and lead times")

    rows = []
    for sku, res in filtered_results.items():
        p      = res["product"]
        status = res["status"]
        fc     = res["forecast"]

        urgency_map = {"STOCKOUT RISK": "🔴 Urgent", "ORDER NOW": "🟡 Soon", "OVERSTOCK": "⚪ Hold", "HEALTHY": "🟢 Monitor"}
        action_map  = {"STOCKOUT RISK": "Order Immediately", "ORDER NOW": "Place Order This Week",
                       "OVERSTOCK": "Pause Orders", "HEALTHY": "Order Next Month"}

        rows.append({
            "Product":          p["name"],
            "Category":         p["category"],
            "Current Stock":    f"{int(p['current_stock']):,}",
            "Days of Stock":    f"{status['days_of_stock']}d",
            "Next Mo. Forecast":f"{status['next_month_demand']:,}",
            "Rec. Order Qty":   f"{status['recommended_order']:,}" if status["recommended_order"] > 0 else "—",
            "Est. Cost (USD)":  f"${status['recommended_order'] * p['cost_per_unit']:,.0f}" if status["recommended_order"] > 0 else "—",
            "Lead Time":        f"{int(p['lead_time_days'])}d",
            "Action":           action_map[status["status"]],
            "Urgency":          urgency_map[status["status"]],
        })

    df_orders = pd.DataFrame(rows)
    st.dataframe(df_orders, width='stretch', hide_index=True)

    # Total cost summary
    total_cost = sum(
        res["status"]["recommended_order"] * res["product"]["cost_per_unit"]
        for res in filtered_results.values()
        if res["status"]["recommended_order"] > 0
    )

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("Products Needing Orders", sum(1 for r in filtered_results.values() if r["status"]["recommended_order"] > 0))
    col2.metric("Estimated Total Order Cost", f"${total_cost:,.0f} USD")
    col3.metric("Avg Lead Time", f"{int(products_df['lead_time_days'].mean())} days")

    # Cost breakdown chart
    st.markdown("### Order Cost by Product")
    chart_data = [(res["product"]["name"].split("(")[0].strip(),
                   res["status"]["recommended_order"] * res["product"]["cost_per_unit"])
                  for res in filtered_results.values() if res["status"]["recommended_order"] > 0]

    if chart_data:
        df_chart = pd.DataFrame(chart_data, columns=["Product", "Cost"])
        fig = px.bar(df_chart, x="Product", y="Cost", color="Cost",
                     color_continuous_scale="Blues",
                     labels={"Cost": "Estimated Cost (USD)"})
        fig.update_layout(height=320, plot_bgcolor="white", paper_bgcolor="white",
                          xaxis=dict(tickangle=-20), showlegend=False)
        st.plotly_chart(fig, width='stretch')

# ─────────────────────────────────────────────
# PAGE 4: ALERTS
# ─────────────────────────────────────────────
elif page == "🚨 Alerts":

    st.markdown("### Active Alerts")

    critical = [(sku, res) for sku, res in filtered_results.items() if res["status"]["color"] == "red"]
    warnings_ = [(sku, res) for sku, res in filtered_results.items() if res["status"]["color"] == "orange"]
    healthy  = [(sku, res) for sku, res in filtered_results.items() if res["status"]["color"] == "green"]

    if critical:
        st.markdown("#### 🔴 Critical — Immediate Action Required")
        for sku, res in critical:
            p      = res["product"]
            status = res["status"]
            st.markdown(f"""
            <div class="alert-red">
                <strong>{p['name']}</strong><br>
                ⚠️ Only <strong>{status['days_of_stock']} days</strong> of stock remaining · 
                Lead time: <strong>{int(p['lead_time_days'])} days</strong> · 
                Recommend ordering <strong>{status['recommended_order']:,} {p['unit']}</strong> immediately
            </div>""", unsafe_allow_html=True)

    if warnings_:
        st.markdown("#### 🟡 Warning — Action Needed Soon")
        for sku, res in warnings_:
            p      = res["product"]
            status = res["status"]
            msg = (f"Stock exceeds 85% of max capacity. Consider pausing orders."
                   if status["status"] == "OVERSTOCK"
                   else f"Stock below reorder point of {int(p['reorder_point']):,} {p['unit']}. Place order this week.")
            st.markdown(f"""
            <div class="alert-yellow">
                <strong>{p['name']}</strong> — {status['status']}<br>
                {msg}
            </div>""", unsafe_allow_html=True)

    if healthy:
        st.markdown("#### 🟢 Healthy — No Action Needed")
        for sku, res in healthy:
            p      = res["product"]
            status = res["status"]
            st.markdown(f"""
            <div class="alert-green">
                <strong>{p['name']}</strong> · {status['days_of_stock']} days of stock · Next order recommended in ~{max(0, int(status['days_of_stock'] - p['lead_time_days'] - 7))} days
            </div>""", unsafe_allow_html=True)

    # Summary donut
    st.markdown("---")
    st.markdown("### Stock Health Overview")
    labels = ["Stockout Risk", "Needs Attention", "Healthy"]
    values = [len(critical), len(warnings_), len(healthy)]
    colors = ["#e53935", "#fdd835", "#43a047"]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker_colors=colors,
        hole=0.55,
        textinfo="label+percent"
    ))
    fig.update_layout(height=340, paper_bgcolor="white",
                      annotations=[dict(text=f"{len(filtered_results)}<br>Products", x=0.5, y=0.5,
                                        font_size=16, showarrow=False)])
    st.plotly_chart(fig, width='stretch')

