"""
ABC Payments — Q4 2025 Dashboard
================================
An interactive, password-protected Streamlit dashboard built on the Q4 2025
slice of the ABC payments export (see prepare_data.py for the cleaning step).

Security
--------
Access is gated by a username + password checked with a constant-time
comparison (hmac.compare_digest) against credentials held in Streamlit
*secrets* — never in this file or the git repo. On Streamlit Community Cloud
the connection is served over HTTPS automatically.

Run locally:   streamlit run app.py
"""

import hmac

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

DATA_FILE = "data_q4_2025.csv"

# Colourblind-aware categorical palette (teal-led, Okabe–Ito inspired).
PALETTE = ["#0F766E", "#0072B2", "#E69F00", "#CC79A7",
           "#56B4E9", "#D55E00", "#117733", "#999933"]
TEAL_SCALE = [[0.0, "#E6F2EF"], [0.5, "#5FAE9E"], [1.0, "#0F766E"]]

# Nicer display names for a few ISO 3166-1 alpha-3 codes (pycountry fallback).
NAME_OVERRIDES = {
    "USA": "United States", "GBR": "United Kingdom", "RUS": "Russia",
    "KOR": "South Korea", "IRN": "Iran", "VEN": "Venezuela", "BOL": "Bolivia",
    "TZA": "Tanzania", "CZE": "Czechia", "MDA": "Moldova", "SYR": "Syria",
    "VNM": "Vietnam", "LAO": "Laos", "BRN": "Brunei", "ARE": "UAE",
}

st.set_page_config(
    page_title="ABC Payments — Q4 2025 Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------- #
# Styling
# --------------------------------------------------------------------------- #
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="st-"], .stApp, button, input, textarea, select {
    font-family: 'IBM Plex Sans', sans-serif;
}
h1, h2, h3, .app-title, .kpi-value {
    font-family: 'Fraunces', Georgia, serif !important;
    letter-spacing: -0.01em;
}
.block-container { padding-top: 2.0rem; max-width: 1320px; }

.app-title { font-size: 2.15rem; font-weight: 700; color: #0F2A26; margin: 0; }
.app-sub   { color: #5B6660; margin: .15rem 0 0 0; font-size: .96rem; }

.kpi-card {
    background: #FFFFFF; border: 1px solid #E7E9E8; border-radius: 14px;
    padding: 1.0rem 1.1rem; height: 100%;
    box-shadow: 0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06);
}
.kpi-label { font-size: .70rem; text-transform: uppercase; letter-spacing: .09em;
             color: #6B7280; font-weight: 600; margin: 0 0 .35rem 0; }
.kpi-value { font-size: 1.7rem; line-height: 1.1; font-weight: 700; color: #111827;
             font-variant-numeric: tabular-nums; }
.kpi-sub   { font-size: .78rem; color: #6B7280; margin-top: .35rem; }
.pos { color: #0F766E; font-weight: 600; }
.neg { color: #B42318; font-weight: 600; }

.insight {
    background: #FFFFFF; border: 1px solid #E7E9E8; border-left: 4px solid #0F766E;
    border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: .9rem;
    box-shadow: 0 1px 2px rgba(16,24,40,.04);
}
.insight h4 { margin: 0 0 .4rem 0; font-family: 'Fraunces', serif; color: #0F2A26;
              font-size: 1.05rem; }
.insight p  { margin: 0; color: #374151; font-size: .94rem; line-height: 1.5; }
.insight .big { color: #0F766E; font-weight: 700; }
hr { margin: .4rem 0 1.1rem 0; border-color: #E7E9E8; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Authentication (constant-time check against Streamlit secrets)
# --------------------------------------------------------------------------- #
def _secret_credentials():
    try:
        return (st.secrets["credentials"]["username"],
                st.secrets["credentials"]["password"])
    except Exception:
        return None, None


def _verify_login():
    user, pwd = _secret_credentials()
    given_u = st.session_state.get("login_user", "")
    given_p = st.session_state.get("login_pass", "")
    ok = (
        user is not None
        and hmac.compare_digest(given_u.encode("utf-8"), user.encode("utf-8"))
        and hmac.compare_digest(given_p.encode("utf-8"), pwd.encode("utf-8"))
    )
    st.session_state["auth_ok"] = bool(ok)
    if ok:  # never keep the raw password around after a successful login
        try:
            del st.session_state["login_pass"]
        except Exception:
            pass


def require_login():
    if st.session_state.get("auth_ok"):
        return
    user, _ = _secret_credentials()
    st.markdown(
        '<div class="app-title">ABC Payments — Q4 2025 Dashboard</div>'
        '<p class="app-sub">Please sign in to continue.</p>',
        unsafe_allow_html=True,
    )
    st.write("")
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        with st.form("login_form"):
            st.text_input("Username", key="login_user")
            st.text_input("Password", type="password", key="login_pass")
            submitted = st.form_submit_button("Log in", on_click=_verify_login)
        if user is None:
            st.error("Credentials are not configured yet. Add them under the "
                     "app's **Settings → Secrets** (see README).")
        elif submitted and st.session_state.get("auth_ok") is False:
            st.error("Incorrect username or password.")
    st.stop()


require_login()


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
def _iso3_to_name(code: str) -> str:
    if code in NAME_OVERRIDES:
        return NAME_OVERRIDES[code]
    try:
        import pycountry
        c = pycountry.countries.get(alpha_3=code)
        return c.name if c else code
    except Exception:
        return code


@st.cache_data(show_spinner="Loading data…")
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_FILE, parse_dates=["date"])
    names = {c: _iso3_to_name(c) for c in df["country_iso3"].unique()}
    df["country_name"] = df["country_iso3"].map(names)
    return df


df = load_data()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def fmt_usd(x: float) -> str:
    a, sign = abs(x), ("-" if x < 0 else "")
    if a >= 1e6:
        return f"{sign}${a/1e6:,.2f}M"
    if a >= 1e3:
        return f"{sign}${a/1e3:,.1f}K"
    return f"{sign}${a:,.0f}"


def fmt_int(x) -> str:
    return f"{int(x):,}"


def kpi_card(col, label, value, sub_html=None):
    html = (f'<div class="kpi-card"><p class="kpi-label">{label}</p>'
            f'<div class="kpi-value">{value}</div>')
    if sub_html:
        html += f'<div class="kpi-sub">{sub_html}</div>'
    col.markdown(html + "</div>", unsafe_allow_html=True)


def style_fig(fig, title=""):
    fig.update_layout(
        template="plotly_white",
        title=dict(text=title, x=0, xanchor="left",
                   font=dict(family="Fraunces, serif", size=17, color="#0F2A26")),
        font=dict(family="IBM Plex Sans, sans-serif", size=13, color="#171A1F"),
        margin=dict(l=8, r=8, t=48 if title else 10, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, x=0),
        hoverlabel=dict(font_size=12),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#EEF1F0", zeroline=False)
    return fig


def pchart(fig):
    """Version-robust wrapper: width='stretch' (2025+) with a fallback."""
    try:
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    except TypeError:
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})


def show_df(frame):
    try:
        st.dataframe(frame, width="stretch", hide_index=True)
    except TypeError:
        st.dataframe(frame, use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# Sidebar — filters
# --------------------------------------------------------------------------- #
def multiselect_all(label, series, default_all=True):
    opts = sorted(series.dropna().unique().tolist())
    default = opts if default_all else []
    return st.sidebar.multiselect(label, opts, default=default)


st.sidebar.markdown("### Filters")
months_order = (df.sort_values("date")["month_label"].unique().tolist())
sel_months = st.sidebar.multiselect("Period (month)", months_order,
                                    default=months_order)
sel_type = multiselect_all("Order type", df["order_payment_type"])
sel_pm = multiselect_all("Payment method", df["payment_method"])
sel_brand = multiselect_all("Card brand", df["card_brand"])
sel_prov = multiselect_all("Provider", df["provider"])
sel_offer = multiselect_all("Offer", df["offer"])
sel_gender = multiselect_all("Gender", df["gender"])

country_opts = (df.groupby("country_name")["total_payout_usd"].sum()
                .sort_values(ascending=False).index.tolist())
sel_country = st.sidebar.multiselect(
    "Country (leave empty = all)", country_opts, default=[])

st.sidebar.markdown("---")
if st.sidebar.button("Sign out"):
    st.session_state["auth_ok"] = False
    st.rerun()

# Apply filters
mask = (
    df["month_label"].isin(sel_months)
    & df["order_payment_type"].isin(sel_type)
    & df["payment_method"].isin(sel_pm)
    & df["card_brand"].isin(sel_brand)
    & df["provider"].isin(sel_prov)
    & df["offer"].isin(sel_offer)
    & df["gender"].isin(sel_gender)
)
if sel_country:
    mask &= df["country_name"].isin(sel_country)
dff = df[mask].copy()


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.markdown(
    '<div class="app-title">ABC Payments — Q4 2025 Dashboard</div>'
    '<p class="app-sub">Interactive view of orders and net payout '
    '(USD) for Oct–Dec 2025. Use the sidebar to filter by period, market, '
    'provider, payment method and customer attributes.</p>',
    unsafe_allow_html=True,
)
st.markdown("<hr>", unsafe_allow_html=True)

if dff.empty:
    st.warning("No data matches the current filters. Widen your selection in "
               "the sidebar.")
    st.stop()


# --------------------------------------------------------------------------- #
# KPI row
# --------------------------------------------------------------------------- #
net = dff["total_payout_usd"].sum()
orders = dff["orders_count"].sum()
avg_order = net / orders if orders else 0
n_countries = dff["country_iso3"].nunique()

monthly = (dff.groupby(["date", "month_label"], as_index=False)
           .agg(net=("total_payout_usd", "sum"),
                orders=("orders_count", "sum"))
           .sort_values("date"))
if len(monthly) >= 2:
    prev, last = monthly["net"].iloc[-2], monthly["net"].iloc[-1]
    mom = (last - prev) / prev * 100 if prev else 0
    cls = "pos" if mom >= 0 else "neg"
    mom_val = f'<span class="{cls}">{mom:+.1f}%</span>'
    mom_sub = (f'{monthly["month_label"].iloc[-1]} vs '
               f'{monthly["month_label"].iloc[-2]}')
else:
    mom_val, mom_sub = "—", "Select ≥ 2 months"

c1, c2, c3, c4, c5 = st.columns(5)
kpi_card(c1, "Net payout (USD)", fmt_usd(net))
kpi_card(c2, "Total orders", fmt_int(orders))
kpi_card(c3, "Avg payout / order", f"${avg_order:,.2f}")
kpi_card(c4, "MoM payout growth", mom_val, mom_sub)
kpi_card(c5, "Active markets", fmt_int(n_countries), "countries")

st.write("")

# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
tab_over, tab_geo, tab_pay, tab_ins = st.tabs(
    ["📈 Overview", "🌍 Geography", "💳 Payments & customers", "💡 Insights"])

# ---- Overview -------------------------------------------------------------- #
with tab_over:
    left, right = st.columns([1.4, 1])

    with left:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_bar(x=monthly["month_label"], y=monthly["net"],
                    name="Net payout", marker_color="#0F766E")
        fig.add_scatter(x=monthly["month_label"], y=monthly["orders"],
                        name="Orders", mode="lines+markers",
                        line=dict(color="#E69F00", width=3), secondary_y=True)
        fig.update_xaxes(categoryorder="array",
                         categoryarray=monthly["month_label"].tolist())
        fig.update_yaxes(title_text="Net payout (USD)", secondary_y=False)
        fig.update_yaxes(title_text="Orders", secondary_y=True, showgrid=False)
        style_fig(fig, "Monthly net payout & orders")
        pchart(fig)

    with right:
        t = (dff.groupby("order_payment_type", as_index=False)
             .agg(net=("total_payout_usd", "sum")))
        fig = px.pie(t, names="order_payment_type", values="net", hole=0.58,
                     color_discrete_sequence=PALETTE)
        fig.update_traces(textposition="outside",
                          texttemplate="%{label}<br>%{percent}")
        style_fig(fig, "Revenue mix by order type")
        pchart(fig)

    left2, right2 = st.columns(2)
    with left2:
        t = (dff.groupby("order_payment_type", as_index=False)
             .agg(net=("total_payout_usd", "sum"),
                  orders=("orders_count", "sum")))
        t["avg"] = t["net"] / t["orders"]
        t = t.sort_values("avg")
        fig = px.bar(t, x="avg", y="order_payment_type", orientation="h",
                     color="order_payment_type", color_discrete_sequence=PALETTE,
                     text=t["avg"].map(lambda v: f"${v:,.0f}"))
        fig.update_traces(showlegend=False, textposition="outside")
        fig.update_xaxes(title_text="Avg payout / order (USD)")
        fig.update_yaxes(title_text="")
        style_fig(fig, "Avg payout per order, by type")
        pchart(fig)

    with right2:
        t = (dff.groupby("provider", as_index=False)
             .agg(net=("total_payout_usd", "sum")).sort_values("net"))
        fig = px.bar(t, x="net", y="provider", orientation="h",
                     color_discrete_sequence=["#0F766E"])
        fig.update_xaxes(title_text="Net payout (USD)")
        fig.update_yaxes(title_text="")
        style_fig(fig, "Net payout by provider")
        pchart(fig)

# ---- Geography ------------------------------------------------------------- #
with tab_geo:
    geo = (dff.groupby(["country_iso3", "country_name"], as_index=False)
           .agg(net=("total_payout_usd", "sum"),
                orders=("orders_count", "sum")))

    fig = px.choropleth(
        geo, locations="country_iso3", locationmode="ISO-3", color="net",
        hover_name="country_name",
        hover_data={"country_iso3": False, "net": ":,.0f", "orders": ":,"},
        color_continuous_scale=TEAL_SCALE)
    fig.update_geos(showframe=False, showcoastlines=False,
                    projection_type="natural earth",
                    bgcolor="rgba(0,0,0,0)", landcolor="#EDEFEE")
    fig.update_coloraxes(colorbar_title="Net payout")
    style_fig(fig, "Net payout by country")
    fig.update_layout(height=430)
    pchart(fig)

    top = geo.sort_values("net", ascending=False).head(15).sort_values("net")
    fig = px.bar(top, x="net", y="country_name", orientation="h",
                 color_discrete_sequence=["#0F766E"],
                 text=top["net"].map(fmt_usd))
    fig.update_traces(textposition="outside")
    fig.update_xaxes(title_text="Net payout (USD)")
    fig.update_yaxes(title_text="")
    style_fig(fig, "Top 15 markets")
    fig.update_layout(height=470)
    pchart(fig)

# ---- Payments & customers -------------------------------------------------- #
with tab_pay:
    a, b = st.columns(2)
    with a:
        t = (dff.groupby("payment_method", as_index=False)
             .agg(net=("total_payout_usd", "sum")).sort_values("net"))
        fig = px.bar(t, x="net", y="payment_method", orientation="h",
                     color="payment_method", color_discrete_sequence=PALETTE,
                     text=t["net"].map(fmt_usd))
        fig.update_traces(showlegend=False, textposition="outside")
        fig.update_xaxes(title_text="Net payout (USD)")
        fig.update_yaxes(title_text="")
        style_fig(fig, "Net payout by payment method")
        pchart(fig)
    with b:
        t = (dff.groupby("card_brand", as_index=False)
             .agg(net=("total_payout_usd", "sum")).sort_values("net"))
        fig = px.bar(t, x="net", y="card_brand", orientation="h",
                     color_discrete_sequence=["#0072B2"],
                     text=t["net"].map(fmt_usd))
        fig.update_traces(textposition="outside")
        fig.update_xaxes(title_text="Net payout (USD)")
        fig.update_yaxes(title_text="")
        style_fig(fig, "Net payout by card brand  (Unknown = non-card / APM)")
        pchart(fig)

    c, d = st.columns([1, 1.4])
    with c:
        t = (dff.groupby("gender", as_index=False)
             .agg(orders=("orders_count", "sum")))
        fig = px.pie(t, names="gender", values="orders", hole=0.58,
                     color_discrete_sequence=PALETTE)
        fig.update_traces(textposition="outside",
                          texttemplate="%{label}<br>%{percent}")
        style_fig(fig, "Orders by gender")
        pchart(fig)
    with d:
        tbl = (dff.groupby(["month_label", "order_payment_type"], as_index=False)
               .agg(Orders=("orders_count", "sum"),
                    Net_payout_USD=("total_payout_usd", "sum")))
        tbl["Net_payout_USD"] = tbl["Net_payout_USD"].round(2)
        st.markdown("**Filtered summary**")
        show_df(tbl)
        st.download_button(
            "⬇ Download filtered data (CSV)",
            dff.to_csv(index=False).encode("utf-8"),
            "abc_filtered.csv", "text/csv")

# ---- Insights -------------------------------------------------------------- #
with tab_ins:
    # All figures below are computed from the full Q4 2025 dataset so the
    # statements stay constant regardless of the sidebar filters.
    total_net = df["total_payout_usd"].sum()
    total_orders = df["orders_count"].sum()
    by_type = df.groupby("order_payment_type").agg(
        net=("total_payout_usd", "sum"), orders=("orders_count", "sum"))
    rec_share = by_type.loc["recurring", "net"] / total_net * 100
    avg_first = by_type.loc["first", "net"] / by_type.loc["first", "orders"]
    avg_rec = by_type.loc["recurring", "net"] / by_type.loc["recurring", "orders"]
    avg_up = by_type.loc["upsell", "net"] / by_type.loc["upsell", "orders"]

    geo = df.groupby(["country_iso3"]).agg(net=("total_payout_usd", "sum"))
    usa_share = geo.loc["USA", "net"] / total_net * 100
    top10_share = geo["net"].sort_values(ascending=False).head(10).sum() / total_net * 100

    male_share = (df.loc[df["gender"] == "male", "orders_count"].sum()
                  / total_orders * 100)
    pm = df.groupby("payment_method").agg(net=("total_payout_usd", "sum"))["net"]
    pm = pm.sort_values(ascending=False)
    pm_top = pm.index[0]

    insights = [
        ("1 · The product launched in Q4 2025",
         "About <span class='big'>98.8%</span> of all orders in the raw export "
         "and 100% of positive revenue fall in Oct–Dec 2025. The earlier months "
         "(Mar–Sep) hold only a few hundred net-<i>negative</i> rows — refunds or "
         "pre-launch test activity — so the dashboard is built on Q4 only."),
        ("2 · Recurring revenue is the engine",
         f"Recurring orders generate <span class='big'>{rec_share:.0f}%</span> of "
         f"net payout and a higher value per order (<b>${avg_rec:,.2f}</b>) than "
         f"first-time orders (<b>${avg_first:,.2f}</b>). Upsells are the most "
         f"valuable at <b>${avg_up:,.2f}</b> / order — the business monetises "
         "existing subscribers far more than new ones."),
        ("3 · Revenue is geographically concentrated",
         f"The United States alone is <span class='big'>{usa_share:.0f}%</span> of "
         f"net payout, and the top 10 of 227 markets account for "
         f"<span class='big'>{top10_share:.0f}%</span>. Growth depends heavily on a "
         "short list of countries — a concentration risk worth watching."),
        ("4 · The customer base is overwhelmingly male",
         f"Around <span class='big'>{male_share:.0f}%</span> of orders come from "
         "male customers. That is a strong targeting signal — and a prompt to check "
         "whether the female / unknown segment is untapped demand or a tracking gap."),
        ("5 · Payments split three ways; 'missing' card brand is structural",
         f"Payments split almost evenly three ways: card, Apple Pay and APM each "
         f"carry roughly a third of net payout, with "
         f"<b>{pm_top.replace('_', ' ').title()}</b> marginally in front. The blank "
         "card brand is <i>not</i> dirty data — it maps almost 1:1 to APM (non-card) "
         "payments. Among cards, Visa leads Mastercard, with Amex third."),
    ]
    for title, body in insights:
        st.markdown(f'<div class="insight"><h4>{title}</h4><p>{body}</p></div>',
                    unsafe_allow_html=True)

    st.caption("Figures derived from the full Q4 2025 dataset "
               "(28,162 rows · 651,591 orders · $27.4M net payout).")
