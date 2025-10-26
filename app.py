# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime


st.set_page_config(page_title="Performance Dashboard", layout="wide", initial_sidebar_state="collapsed")

# -------- Helpers --------
@st.cache_data
def load_data(path="Copy of finalProj_df.xlsx"):
    df = pd.read_excel(path)
    # try to ensure order_date is datetime
    if "order_date" in df.columns:
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    # fill missing category
    if "category" not in df.columns:
        df["category"] = "Unknown"
    df["sales_value"] = df["after_discount"].fillna(0)
    # ensure cogs numeric
    df["cogs"] = pd.to_numeric(df["cogs"].fillna(0))
    df["net_profit"] = df["sales_value"] - df["cogs"]
    return df

def compute_summary(df, start_date=None, end_date=None, selected_categories=None):
    d = df.copy()
    if start_date:
        d = d[d["order_date"] >= start_date]
    if end_date:
        d = d[d["order_date"] <= end_date]
    if selected_categories and len(selected_categories) > 0:
        d = d[d["category"].isin(selected_categories)]
    summary = d.groupby("category").agg(
        sales_value = ("sales_value", "sum"),
        net_profit = ("net_profit", "sum"),
        transactions = ("id", "count")
    ).reset_index().sort_values("sales_value", ascending=False)
    summary["AOV"] = np.where(summary["transactions"]>0, summary["sales_value"] / summary["transactions"], 0)
    totals = {
        "total_sales": summary["sales_value"].sum(),
        "total_profit": summary["net_profit"].sum(),
        "avg_aov": summary["AOV"].mean() if len(summary)>0 else 0,
        "transactions": summary["transactions"].sum()
    }
    return summary, totals

# -------- Load data --------
st.sidebar.header("Data & Filters")
DATA_PATH = "Copy of finalProj_df.xlsx"
try:
    df = load_data(DATA_PATH)
except FileNotFoundError:
    st.sidebar.error(f"File not found: {DATA_PATH}. Upload dataset or place it next to app.py.")
    st.stop()

# ---------- Sidebar Filters ----------
min_date = df["order_date"].min() if df["order_date"].notna().any() else pd.to_datetime("2020-01-01")
max_date = df["order_date"].max() if df["order_date"].notna().any() else pd.to_datetime("2023-12-31")

start_date, end_date = st.sidebar.date_input("Order date range", [min_date.date(), max_date.date()])
if isinstance(start_date, list) or isinstance(start_date, tuple):
    start_date, end_date = start_date[0], start_date[1]

# categories multiselect
all_categories = sorted(df["category"].fillna("Unknown").unique().tolist())
selected_categories = st.sidebar.multiselect("Category (select to filter)", all_categories, default=all_categories)

# quick top-n selector
top_n = st.sidebar.slider("Show top N categories by Sales", min_value=3, max_value=30, value=12, step=1)

# --------- Compute summary based on filters ----------
summary, totals = compute_summary(df, pd.to_datetime(start_date), pd.to_datetime(end_date), selected_categories)

# Limit to top_n
summary = summary.nlargest(top_n, "sales_value")

# --------- Header / Title ----------
st.markdown("<h1 style='margin-bottom:0.2rem'>📊 Campaign Performance Dashboard</h1>", unsafe_allow_html=True)
st.markdown(f"<div style='color:gray;margin-top:0;padding-bottom:0.5rem'>Date range: <b>{pd.to_datetime(start_date).date()}</b> — <b>{pd.to_datetime(end_date).date()}</b></div>", unsafe_allow_html=True)
st.write("---")

# --------- KPI Cards ----------
kpi1, kpi2, kpi3, kpi4 = st.columns([2,2,2,2])
kpi1.metric("Total Sales", f"Rp {totals['total_sales']:,.0f}")
kpi2.metric("Total Net Profit", f"Rp {totals['total_profit']:,.0f}")
kpi3.metric("Average AOV (per category)", f"Rp {totals['avg_aov']:,.0f}")
kpi4.metric("Transactions", f"{totals['transactions']:,}")

st.write("")

# --------- Main layout: left (chart) / right (table & details) ----------
left_col, right_col = st.columns((2.2, 1))

with left_col:
    st.subheader("Sales & Profit by Category")
    if summary.empty:
        st.info("No data for the selected filters.")
    else:
        # Create combined bar + line with plotly
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=summary["category"],
            y=summary["sales_value"],
            name="Sales Value",
            marker_line_width=0,
            hovertemplate="Category: %{x}<br>Sales: Rp %{y:,.0f}<extra></extra>"
        ))
        fig.add_trace(go.Bar(
            x=summary["category"],
            y=summary["net_profit"],
            name="Net Profit",
            opacity=0.7,
            hovertemplate="Category: %{x}<br>Profit: Rp %{y:,.0f}<extra></extra>"
        ))
        fig.add_trace(go.Scatter(
            x=summary["category"],
            y=summary["AOV"],
            name="AOV",
            mode="lines+markers",
            marker=dict(size=8),
            yaxis="y2",
            hovertemplate="Category: %{x}<br>AOV: Rp %{y:,.0f}<extra></extra>"
        ))

        # layout with secondary y-axis
        fig.update_layout(
            barmode="group",
            xaxis_tickangle=-45,
            margin=dict(l=40, r=10, t=50, b=120),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="Rp (Sales / Profit)"),
            yaxis2=dict(title="Rp (AOV)", overlaying="y", side="right", showgrid=False),
            height=520
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Trend (Monthly)")
    # Monthly time-series aggregated
    ts = df.copy()
    ts = ts[(ts["order_date"] >= pd.to_datetime(start_date)) & (ts["order_date"] <= pd.to_datetime(end_date))]
    if selected_categories:
        ts = ts[ts["category"].isin(selected_categories)]
    if not ts.empty and "order_date" in ts.columns:
        monthly = ts.set_index("order_date").resample("M").agg({"sales_value":"sum", "net_profit":"sum"})
        monthly = monthly.reset_index()
        px_fig = px.line(monthly, x="order_date", y=["sales_value","net_profit"], labels={"value":"Rp", "order_date":"Month"}, markers=True)
        px_fig.update_layout(height=300, legend=dict(orientation="h", y=1.1))
        st.plotly_chart(px_fig, use_container_width=True)
    else:
        st.info("No time-series data to show for selected filters.")

with right_col:
    st.subheader("Summary Table (by Category)")
    st.dataframe(summary.style.format({
        "sales_value":"{0:,.0f}",
        "net_profit":"{0:,.0f}",
        "AOV":"{0:,.0f}",
        "transactions":"{0:,}"
    }), height=520)

    st.write("---")
    st.subheader("Top Products (by Sales)")
    # Top products table
    prod = df.copy()
    if selected_categories:
        prod = prod[prod["category"].isin(selected_categories)]
    prod = prod.groupby(["sku_id", "sku_name"]).agg(
        sales_value=("sales_value","sum"),
        transactions=("id","count")
    ).reset_index().sort_values("sales_value", ascending=False).head(10)
    st.table(prod.assign(sales_value=prod["sales_value"].map("{:,.0f}".format)))

# --------- Footer / notes ----------
st.write("---")
st.markdown("**Notes:** Sales = `after_discount`. Net profit = `after_discount - cogs`. If you want additional visuals (heatmap, drilldown, export CSV), request and I'll add.")
