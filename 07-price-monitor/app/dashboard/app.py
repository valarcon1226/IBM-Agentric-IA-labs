"""Streamlit dashboard for E-Commerce Price Monitor.

Visualizes price trends, target price thresholds, and triggered alerts.
"""

import os
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# Configure page
st.set_page_config(
    page_title="Price Monitor Dashboard",
    page_icon="📈",
    layout="wide",
)

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8007")
API_TOKEN = os.environ.get("API_TOKEN", "change_me_api_token")

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}


def api_get(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    try:
        url = f"{API_BASE_URL.rstrip('/')}{endpoint}"
        resp = requests.get(url, headers=HEADERS, params=params, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        st.error(f"API Error ({resp.status_code}): {resp.text}")
    except Exception as exc:
        st.error(f"Failed to connect to API at {API_BASE_URL}: {exc}")
    return None


def api_post(endpoint: str, json_data: dict[str, Any] | None = None) -> Any:
    try:
        url = f"{API_BASE_URL.rstrip('/')}{endpoint}"
        resp = requests.post(url, headers=HEADERS, json=json_data, timeout=15)
        if resp.status_code in (200, 201):
            return resp.json()
        st.error(f"API Error ({resp.status_code}): {resp.text}")
    except Exception as exc:
        st.error(f"Failed to connect to API at {API_BASE_URL}: {exc}")
    return None


# Sidebar
st.sidebar.title("🏷️ Price Monitor")
st.sidebar.caption("Polite E-Commerce Scraping & Trend Tracker")

# Health check
health = api_get("/health")
if health and health.get("status") == "healthy":
    st.sidebar.success("API: Connected (Healthy)")
else:
    st.sidebar.warning("API: Unavailable or Initializing...")

# Product selection
products = api_get("/api/v1/products/") or []
product_names = {p["name"]: p for p in products}

selected_name = st.sidebar.selectbox(
    "Select Monitored Product",
    options=list(product_names.keys()) if product_names else ["No products registered"],
)

if product_names and selected_name in product_names:
    selected_product = product_names[selected_name]
    product_id = selected_product["id"]

    if st.sidebar.button("🔄 Scrape Product Now"):
        with st.spinner("Scraping price..."):
            res = api_post(f"/api/v1/products/{product_id}/scrape")
            if res and res.get("status") == "SUCCESS":
                st.sidebar.success(f"Scraped! Price: {res.get('new_price')}")
                st.rerun()
            else:
                st.sidebar.error(f"Scrape result: {res}")

    # Add Product Form in expander
    with st.sidebar.expander("➕ Register New Product"):
        with st.form("new_product_form"):
            new_name = st.text_input("Product Name", placeholder="e.g. Ergonomic Mouse")
            new_url = st.text_input(
                "Product URL", placeholder="http://demo-store/products/mouse.html"
            )
            new_domain = st.text_input("Domain", value="demo-store")
            new_target = st.number_input("Target Price ($)", min_value=0.0, value=50.0, step=1.0)
            new_threshold = st.number_input(
                "Alert Threshold (%)", min_value=1.0, value=5.0, step=0.5
            )
            submitted = st.form_submit_button("Add Product")

            if submitted and new_name and new_url:
                payload = {
                    "name": new_name,
                    "url": new_url,
                    "site_domain": new_domain,
                    "target_price": new_target if new_target > 0 else None,
                    "alert_threshold_pct": new_threshold,
                    "currency": "USD",
                    "check_interval_hours": 6,
                    "requires_js": False,
                    "is_active": True,
                }
                res = api_post("/api/v1/products/", json_data=payload)
                if res:
                    st.sidebar.success("Product registered!")
                    st.rerun()

    # Main Dashboard
    st.header(f"Product: {selected_product['name']}")
    st.markdown(
        f"**URL:** [{selected_product['url']}]({selected_product['url']}) | **Domain:** `{selected_product['site_domain']}`"
    )

    # Fetch History
    history = api_get(f"/api/v1/products/{product_id}/history") or []
    alerts = api_get(f"/api/v1/products/{product_id}/alerts") or []

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)

    target_price = (
        float(selected_product["target_price"]) if selected_product.get("target_price") else None
    )
    latest_price = float(history[-1]["price"]) if history else None
    prev_price = float(history[-2]["price"]) if len(history) > 1 else None

    with col1:
        st.metric(
            label="Current Price",
            value=f"${latest_price:.2f}" if latest_price is not None else "N/A",
            delta=f"{latest_price - prev_price:+.2f}" if latest_price and prev_price else None,
            delta_color="inverse",
        )

    with col2:
        st.metric(
            label="Target Price",
            value=f"${target_price:.2f}" if target_price is not None else "None",
        )

    with col3:
        if latest_price and target_price:
            diff = latest_price - target_price
            status_text = "Target Met! 🎉" if diff <= 0 else f"${diff:.2f} above target"
        else:
            status_text = "N/A"
        st.metric(label="Target Status", value=status_text)

    with col4:
        st.metric(label="Total Scrapes", value=len(history))

    # Plotly Price Curve
    st.subheader("Price History Trend")
    if history:
        df = pd.DataFrame(history)
        df["scraped_at"] = pd.to_datetime(df["scraped_at"])
        df["price"] = df["price"].astype(float)
        df = df.sort_values("scraped_at")

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df["scraped_at"],
                y=df["price"],
                mode="lines+markers",
                name="Recorded Price",
                line={"color": "#1f77b4", "width": 3},
                marker={"size": 8},
                hovertemplate="Date: %{x|%Y-%m-%d %H:%M}<br>Price: $%{y:.2f}<extra></extra>",
            )
        )

        if target_price:
            fig.add_hline(
                y=target_price,
                line_dash="dash",
                line_color="#2ca02c",
                annotation_text=f"Target: ${target_price:.2f}",
                annotation_position="bottom right",
            )

        fig.update_layout(
            xaxis_title="Time",
            yaxis_title=f"Price ({selected_product.get('currency', 'USD')})",
            margin={"l": 40, "r": 40, "t": 20, "b": 40},
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

        # History Data Table
        with st.expander("📋 View Price Log Table", expanded=False):
            st.dataframe(
                df[["scraped_at", "price", "currency", "availability"]].rename(
                    columns={
                        "scraped_at": "Timestamp",
                        "price": "Price",
                        "currency": "Currency",
                        "availability": "Available",
                    }
                ),
                use_container_width=True,
            )
    else:
        st.info(
            "No price points recorded yet. Click 'Scrape Product Now' in the sidebar to fetch initial price."
        )

    # Alerts Section
    st.subheader("Triggered Alerts")
    if alerts:
        alert_df = pd.DataFrame(alerts)
        alert_df["sent_at"] = pd.to_datetime(alert_df["sent_at"])
        st.dataframe(
            alert_df[["sent_at", "alert_type", "old_price", "new_price", "status"]].rename(
                columns={
                    "sent_at": "Alert Timestamp",
                    "alert_type": "Type",
                    "old_price": "Old Price",
                    "new_price": "New Price",
                    "status": "Webhook Delivery",
                }
            ),
            use_container_width=True,
        )
    else:
        st.caption("No alerts triggered for this product.")

else:
    st.header("Welcome to E-Commerce Price Monitor")
    st.info("No products currently monitored. Register a product in the sidebar to get started.")
