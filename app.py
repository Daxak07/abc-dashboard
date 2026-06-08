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

Visual identity uses the Zimran (zimran.io) brand palette — power-violet led.

Run locally:   streamlit run app.py
"""

import hmac

import pandas as pd
import plotly.express as px
import streamlit as st
from plotly.subplots import make_subplots

DATA_FILE = "data_q4_2025.csv"

# --------------------------------------------------------------------------- #
# Brand palette — Zimran design tokens (zimran.io)
# --------------------------------------------------------------------------- #
BRAND = "#5b42dc"        # power-violet  (primary)
BRAND_DARK = "#4f31ba"   # deep-violet
BRAND_SOFT = "#7367ff"   # periwinkle
HEADING = "#2a1a66"      # dark violet for serif titles
INK = "#101828"          # gray-900 (body text)
INK_SOFT = "#4a5565"     # gray-600 (secondary text)
MUTED = "#6a7282"        # gray-500
BORDER = "#e7e5f3"       # violet-tinted border
POS = "#00a544"          # green-600 (positive delta)
NEG = "#e40014"          # red-600   (negative delta)
BLUE = "#3080ff"         # zimran blue accent

# Categorical palette: brand-led, hue-diverse and colourblind-aware
# (alternates violet / green / blue / amber families for separability).
PALETTE = ["#5b42dc", "#00a544", "#3080ff", "#E69F00",
           "#ac4bff", "#e40014", "#6a7282", "#155dfc"]
# Single-hue violet scale for the choropleth (light → power-violet).
VIOLET_SCALE = [[0.0, "#f3e8ff"], [0.5, "#9d86ee"], [1.0, "#5b42dc"]]

# Low-cardinality string columns → category dtype (smaller + faster groupbys).
CAT_COLS = ["month_label", "provider", "country_iso3", "order_payment_type",
            "payment_method", "card_brand", "gender", "offer"]

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
# Branding
# --------------------------------------------------------------------------- #
def logo_svg(size: int = 40) -> str:
    """Inline SVG monogram: ascending bars on a violet tile (Zimran palette)."""
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 40 40" fill="none" '
        'xmlns="http://www.w3.org/2000/svg" role="img" '
        'aria-label="ABC Payments logo">'
        '<defs><linearGradient id="zg" x1="0" y1="0" x2="40" y2="40" '
        'gradientUnits="userSpaceOnUse">'
        '<stop stop-color="#7367ff"/><stop offset="1" stop-color="#5b42dc"/>'
        '</linearGradient></defs>'
        '<rect width="40" height="40" rx="11" fill="url(#zg)"/>'
        '<rect x="10.5" y="22" width="4.6" height="8.5" rx="2.3" fill="#fff" '
        'fill-opacity="0.85"/>'
        '<rect x="17.7" y="16" width="4.6" height="14.5" rx="2.3" fill="#fff" '
        'fill-opacity="0.92"/>'
        '<rect x="24.9" y="10.5" width="4.6" height="20" rx="2.3" fill="#fff"/>'
        '</svg>'
    )


# --------------------------------------------------------------------------- #
# Styling
# --------------------------------------------------------------------------- #
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="st-"], .stApp, button, input, textarea, select {{
    font-family: 'IBM Plex Sans', sans-serif;
}}
h1, h2, h3, .app-title, .kpi-value, .login-head {{
    font-family: 'Fraunces', Georgia, serif !important;
    letter-spacing: -0.01em;
}}
.block-container {{ padding-top: 2.0rem; max-width: 1320px; }}

/* Header / appbar */
.appbar {{ display: flex; align-items: center; gap: .85rem; }}
.app-title {{ font-size: 2.05rem; font-weight: 700; color: {HEADING}; margin: 0;
             line-height: 1.05; }}
.app-title .q {{ color: {BRAND}; font-weight: 600; }}
.app-sub   {{ color: {INK_SOFT}; margin: .15rem 0 0 0; font-size: .96rem;
             max-width: 70ch; }}

/* KPI cards */
.kpi-card {{
    background: #FFFFFF; border: 1px solid {BORDER}; border-radius: 16px;
    padding: 1.0rem 1.1rem; height: 100%;
    box-shadow: 0 1px 2px rgba(43,26,102,.05), 0 6px 16px rgba(43,26,102,.05);
}}
.kpi-label {{ font-size: .70rem; text-transform: uppercase; letter-spacing: .09em;
             color: {MUTED}; font-weight: 600; margin: 0 0 .35rem 0; }}
.kpi-value {{ font-size: 1.7rem; line-height: 1.1; font-weight: 700; color: {INK};
             font-variant-numeric: tabular-nums; }}
.kpi-sub   {{ font-size: .78rem; color: {MUTED}; margin-top: .4rem;
             min-height: 1.05rem; }}
.pos {{ color: {POS}; font-weight: 700; }}
.neg {{ color: {NEG}; font-weight: 700; }}

/* Insight cards */
.insight {{
    background: #FFFFFF; border: 1px solid {BORDER}; border-left: 4px solid {BRAND};
    border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: .9rem;
    box-shadow: 0 1px 2px rgba(43,26,102,.04);
}}
.insight h4 {{ margin: 0 0 .4rem 0; font-family: 'Fraunces', serif; color: {HEADING};
              font-size: 1.05rem; }}
.insight p  {{ margin: 0; color: #374151; font-size: .94rem; line-height: 1.5; }}
.insight .big {{ color: {BRAND}; font-weight: 700; }}
hr {{ margin: .4rem 0 1.1rem 0; border-color: {BORDER}; }}

/* Login screen */
.login-brand {{ display: flex; flex-direction: column; align-items: center;
               gap: .55rem; margin: 2.2rem 0 1.1rem 0; }}
.login-name {{ font-family: 'Fraunces', serif; font-weight: 600; font-size: 1.2rem;
              color: {HEADING}; letter-spacing: -0.01em; }}
.login-head {{ font-size: 1.55rem; font-weight: 700; color: {HEADING};
              margin: .1rem 0 0 0; }}
.login-sub  {{ color: {INK_SOFT}; margin: .15rem 0 .6rem 0; font-size: .92rem; }}
.login-foot {{ text-align: center; color: {MUTED}; font-size: .8rem;
              margin-top: .9rem; }}

/* Sidebar accent */
section[data-testid="stSidebar"] h3 {{ color: {HEADING}; }}
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
        for k in ("login_pass", "login_user"):
            st.session_state.pop(k, None)


def require_login():
    if st.session_state.get("auth_ok"):
        return
    user, _ = _secret_credentials()
    _, mid, _ = st.columns([1, 1.25, 1])
    with mid:
        st.markdown(
            f'<div class="login-brand">{logo_svg(56)}'
            '<div class="login-name">ABC Payments</div></div>',
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            st.markdown(
                '<div class="login-head">Sign in</div>'
                '<p class="login-sub">Q4 2025 payments dashboard</p>',
                unsafe_allow_html=True,
            )
            with st.form("login_form"):
                st.text_input("Username", key="login_user", placeholder="username")
                st.text_input("Password", type="password", key="login_pass",
                              placeholder="••••••••")
                submitted = st.form_submit_button(
                    "Log in", on_click=_verify_login, use_container_width=True)
            if user is None:
                st.error("Credentials are not configured yet. Add them under "
                         "**Settings → Secrets** (see README).")
            elif submitted and st.session_state.get("auth_ok") is False:
                st.error("Incorrect username or password.")
        st.markdown(
            '<p class="login-foot">🔒 Access is restricted · credentials are '
            'provided by your contact.</p>',
            unsafe_allow_html=True,
        )
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
    df = pd.read_csv(
        DATA_FILE,
        parse_dates=["date"],
        dtype={c: "category" for c in CAT_COLS},
    )
    df["orders_count"] = pd.to_numeric(df["orders_count"], downcast="integer")
    names = {c: _iso3_to_name(c) for c in df["country_iso3"].cat.categories}
    df["country_name"] = df["country_iso3"].map(names).astype("category")
    return df


df = load_data()


# --------------------------------------------------------------------------- #
# Insight metrics — computed once over the FULL dataset, then cached so they
# stay constant regardless of sidebar filters and never recompute on reruns.
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def insights_metrics() -> dict:
    d = load_data()
    total_net = float(d["total_payout_usd"].sum())
    total_orders = int(d["orders_count"].sum())

    bt = d.groupby("order_payment_type", observed=True).agg(
        net=("total_payout_usd", "sum"), orders=("orders_count", "sum"))
    bt_net, bt_ord = bt["net"], bt["orders"]

    def share(cat):
        return (bt_net.get(cat, 0) / total_net * 100) if total_net else 0

    def avg(cat):
        o = bt_ord.get(cat, 0)
        return (bt_net.get(cat, 0) / o) if o else 0

    geo_net = d.groupby("country_iso3", observed=True)["total_payout_usd"].sum()
    usa_share = (geo_net.get("USA", 0) / total_net * 100) if total_net else 0
    top10_share = (geo_net.sort_values(ascending=False).head(10).sum()
                   / total_net * 100) if total_net else 0
    n_markets = int(d["country_iso3"].nunique())

    male_orders = d.loc[d["gender"] == "male", "orders_count"].sum()
    male_share = (male_orders / total_orders * 100) if total_orders else 0

    pm = (d.groupby("payment_method", observed=True)["total_payout_usd"].sum()
          .sort_values(ascending=False))
    pm_top = str(pm.index[0]) if len(pm) else "—"

    # Card-brand ranking, excluding the non-card "Unknown" bucket (= APM).
    cb = d[~d["card_brand"].astype(str).str.lower().isin(["unknown", "nan", ""])]
    cbr = (cb.groupby("card_brand", observed=True)["total_payout_usd"].sum()
           .sort_values(ascending=False))
    card_rank = [str(x).title() for x in cbr.index.tolist()][:3]

    return dict(
        rec_share=share("recurring"), avg_first=avg("first"),
        avg_rec=avg("recurring"), avg_up=avg("upsell"),
        usa_share=usa_share, top10_share=top10_share, n_markets=n_markets,
        male_share=male_share, pm_top=pm_top, card_rank=card_rank,
        total_net=total_net, total_orders=total_orders,
    )


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


def kpi_card(col, label, value, sub_html="&nbsp;", aria=None):
    aria = aria or f"{label}: {value}"
    col.markdown(
        f'<div class="kpi-card" role="group" aria-label="{aria}">'
        f'<p class="kpi-label">{label}</p>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub_html}</div></div>',
        unsafe_allow_html=True,
    )


def style_fig(fig, title=""):
    fig.update_layout(
        template="plotly_white",
        title=dict(text=title, x=0, xanchor="left",
                   font=dict(family="Fraunces, serif", size=17, color=HEADING)),
        font=dict(family="IBM Plex Sans, sans-serif", size=13, color=INK),
        margin=dict(l=8, r=16, t=48 if title else 10, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, x=0),
        hoverlabel=dict(font_size=12),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#EDEAF7", zeroline=False)
    return fig


def money_xaxis(fig, title="Net payout (USD)"):
    fig.update_xaxes(title_text=title, tickprefix="$", tickformat="~s")
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
# Sidebar — filters (empty selection = all, so you can never dead-end)
# --------------------------------------------------------------------------- #
FILTER_KEYS = ["f_months", "f_type", "f_pm", "f_brand",
               "f_prov", "f_offer", "f_gender", "f_country"]


def reset_filters():
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


def sign_out():
    st.session_state["auth_ok"] = False


def opts_of(col):
    return sorted(df[col].dropna().astype(str).unique().tolist())


st.sidebar.markdown("### Filters")
st.sidebar.caption("Empty = all. Pick values to narrow the view.")

months_order = (df.sort_values("date")["month_label"].astype(str)
                .drop_duplicates().tolist())
sel_months = st.sidebar.multiselect("Period (month)", months_order,
                                    default=months_order, key="f_months")
sel_type = st.sidebar.multiselect("Order type", opts_of("order_payment_type"),
                                  default=opts_of("order_payment_type"),
                                  key="f_type")
sel_pm = st.sidebar.multiselect("Payment method", opts_of("payment_method"),
                                default=opts_of("payment_method"), key="f_pm")
sel_brand = st.sidebar.multiselect("Card brand", opts_of("card_brand"),
                                   default=opts_of("card_brand"), key="f_brand")
sel_prov = st.sidebar.multiselect("Provider", opts_of("provider"),
                                  default=opts_of("provider"), key="f_prov")
sel_offer = st.sidebar.multiselect("Offer", opts_of("offer"),
                                   default=opts_of("offer"), key="f_offer")
sel_gender = st.sidebar.multiselect("Gender", opts_of("gender"),
                                    default=opts_of("gender"), key="f_gender")

country_opts = (df.groupby("country_name", observed=True)["total_payout_usd"]
                .sum().sort_values(ascending=False).index.astype(str).tolist())
sel_country = st.sidebar.multiselect("Country", country_opts, default=[],
                                     key="f_country")

st.sidebar.markdown("---")
st.sidebar.button("↺ Reset filters", on_click=reset_filters,
                  use_container_width=True)
st.sidebar.button("Sign out", on_click=sign_out, use_container_width=True)


# Apply filters — empty selection means "no constraint" (show all).
def _apply(mask, col, sel):
    return (mask & df[col].astype(str).isin(sel)) if sel else mask


mask = pd.Series(True, index=df.index)
mask = _apply(mask, "month_label", sel_months)
mask = _apply(mask, "order_payment_type", sel_type)
mask = _apply(mask, "payment_method", sel_pm)
mask = _apply(mask, "card_brand", sel_brand)
mask = _apply(mask, "provider", sel_prov)
mask = _apply(mask, "offer", sel_offer)
mask = _apply(mask, "gender", sel_gender)
mask = _apply(mask, "country_name", sel_country)
dff = df[mask].copy()


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.markdown(
    '<div class="appbar">' + logo_svg(42) +
    '<div><div class="app-title">ABC Payments '
    '<span class="q">· Q4 2025</span></div>'
    '<p class="app-sub">Interactive view of orders and net payout (USD) for '
    'Oct–Dec 2025. Use the sidebar to filter by period, market, provider, '
    'payment method and customer attributes.</p></div></div>',
    unsafe_allow_html=True,
)
st.markdown("<hr>", unsafe_allow_html=True)

if dff.empty:
    st.warning("No data matches the current filters.")
    st.button("↺ Reset filters", on_click=reset_filters, key="reset_empty")
    st.stop()


# --------------------------------------------------------------------------- #
# KPI row
# --------------------------------------------------------------------------- #
net = dff["total_payout_usd"].sum()
orders = dff["orders_count"].sum()
avg_order = net / orders if orders else 0
n_countries = dff["country_iso3"].nunique()

monthly = (dff.groupby(["date", "month_label"], observed=True, as_index=False)
           .agg(net=("total_payout_usd", "sum"),
                orders=("orders_count", "sum"))
           .sort_values("date"))
if len(monthly) >= 2:
    prev, last = monthly["net"].iloc[-2], monthly["net"].iloc[-1]
    mom = (last - prev) / prev * 100 if prev else 0
    cls = "pos" if mom >= 0 else "neg"
    arrow = "▲" if mom >= 0 else "▼"
    mom_val = f'<span class="{cls}">{arrow} {mom:+.1f}%</span>'
    mom_plain = f"{mom:+.1f}%"
    mom_sub = (f'{monthly["month_label"].iloc[-1]} vs '
               f'{monthly["month_label"].iloc[-2]}')
else:
    mom_val, mom_plain, mom_sub = "—", "n/a", "select ≥ 2 months"

c1, c2, c3, c4, c5 = st.columns(5)
kpi_card(c1, "Net payout (USD)", fmt_usd(net), "Q4 2025 · Oct–Dec",
         aria=f"Net payout {fmt_usd(net)}")
kpi_card(c2, "Total orders", fmt_int(orders), "across the quarter")
kpi_card(c3, "Avg payout / order", f"${avg_order:,.2f}", "per paid order")
kpi_card(c4, "MoM payout growth", mom_val, mom_sub,
         aria=f"Month over month payout growth {mom_plain}")
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
                    name="Net payout", marker_color=BRAND)
        fig.add_scatter(x=monthly["month_label"], y=monthly["orders"],
                        name="Orders", mode="lines+markers",
                        line=dict(color="#E69F00", width=3), secondary_y=True)
        fig.update_xaxes(categoryorder="array",
                         categoryarray=monthly["month_label"].tolist())
        fig.update_yaxes(title_text="Net payout (USD)", secondary_y=False,
                         tickprefix="$", tickformat="~s")
        fig.update_yaxes(title_text="Orders", secondary_y=True, showgrid=False)
        style_fig(fig, "Monthly net payout & orders")
        pchart(fig)
        st.caption("Bars: net payout (left axis) · line: order volume (right).")

    with right:
        t = (dff.groupby("order_payment_type", observed=True, as_index=False)
             .agg(net=("total_payout_usd", "sum")))
        fig = px.pie(t, names="order_payment_type", values="net", hole=0.58,
                     color_discrete_sequence=PALETTE)
        fig.update_traces(textposition="auto",
                          texttemplate="%{label}<br>%{percent}")
        style_fig(fig, "Revenue mix by order type")
        pchart(fig)

    left2, right2 = st.columns(2)
    with left2:
        t = (dff.groupby("order_payment_type", observed=True, as_index=False)
             .agg(net=("total_payout_usd", "sum"),
                  orders=("orders_count", "sum")))
        t["avg"] = t["net"] / t["orders"]
        t = t.sort_values("avg")
        fig = px.bar(t, x="avg", y="order_payment_type", orientation="h",
                     color="order_payment_type", color_discrete_sequence=PALETTE,
                     text=t["avg"].map(lambda v: f"${v:,.0f}"))
        fig.update_traces(showlegend=False, textposition="auto")
        money_xaxis(fig, "Avg payout / order (USD)")
        fig.update_yaxes(title_text="")
        style_fig(fig, "Avg payout per order, by type")
        pchart(fig)

    with right2:
        t = (dff.groupby("provider", observed=True, as_index=False)
             .agg(net=("total_payout_usd", "sum")).sort_values("net"))
        fig = px.bar(t, x="net", y="provider", orientation="h",
                     color_discrete_sequence=[BRAND],
                     text=t["net"].map(fmt_usd))
        fig.update_traces(textposition="auto")
        money_xaxis(fig)
        fig.update_yaxes(title_text="")
        style_fig(fig, "Net payout by provider")
        pchart(fig)

# ---- Geography ------------------------------------------------------------- #
with tab_geo:
    geo = (dff.groupby(["country_iso3", "country_name"], observed=True,
                       as_index=False)
           .agg(net=("total_payout_usd", "sum"),
                orders=("orders_count", "sum")))

    fig = px.choropleth(
        geo, locations="country_iso3", locationmode="ISO-3", color="net",
        hover_name="country_name",
        hover_data={"country_iso3": False, "net": ":,.0f", "orders": ":,"},
        color_continuous_scale=VIOLET_SCALE)
    fig.update_geos(showframe=False, showcoastlines=False,
                    projection_type="natural earth",
                    bgcolor="rgba(0,0,0,0)", landcolor="#EEECF6")
    fig.update_coloraxes(colorbar_title="Net payout")
    style_fig(fig, "Net payout by country")
    fig.update_layout(height=430)
    pchart(fig)

    top = geo.sort_values("net", ascending=False).head(15).sort_values("net")
    fig = px.bar(top, x="net", y="country_name", orientation="h",
                 color_discrete_sequence=[BRAND],
                 text=top["net"].map(fmt_usd))
    fig.update_traces(textposition="auto")
    money_xaxis(fig)
    fig.update_yaxes(title_text="")
    style_fig(fig, "Top 15 markets")
    fig.update_layout(height=470)
    pchart(fig)

# ---- Payments & customers -------------------------------------------------- #
with tab_pay:
    a, b = st.columns(2)
    with a:
        t = (dff.groupby("payment_method", observed=True, as_index=False)
             .agg(net=("total_payout_usd", "sum")).sort_values("net"))
        fig = px.bar(t, x="net", y="payment_method", orientation="h",
                     color="payment_method", color_discrete_sequence=PALETTE,
                     text=t["net"].map(fmt_usd))
        fig.update_traces(showlegend=False, textposition="auto")
        money_xaxis(fig)
        fig.update_yaxes(title_text="")
        style_fig(fig, "Net payout by payment method")
        pchart(fig)
    with b:
        t = (dff.groupby("card_brand", observed=True, as_index=False)
             .agg(net=("total_payout_usd", "sum")).sort_values("net"))
        fig = px.bar(t, x="net", y="card_brand", orientation="h",
                     color_discrete_sequence=[BLUE],
                     text=t["net"].map(fmt_usd))
        fig.update_traces(textposition="auto")
        money_xaxis(fig)
        fig.update_yaxes(title_text="")
        style_fig(fig, "Net payout by card brand  (Unknown = non-card / APM)")
        pchart(fig)

    c, d = st.columns([1, 1.4])
    with c:
        t = (dff.groupby("gender", observed=True, as_index=False)
             .agg(orders=("orders_count", "sum")))
        fig = px.pie(t, names="gender", values="orders", hole=0.58,
                     color_discrete_sequence=PALETTE)
        fig.update_traces(textposition="auto",
                          texttemplate="%{label}<br>%{percent}")
        style_fig(fig, "Orders by gender")
        pchart(fig)
    with d:
        tbl = (dff.groupby(["month_label", "order_payment_type"], observed=True,
                           as_index=False)
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
    m = insights_metrics()
    pm_top = m["pm_top"].replace("_", " ").title()
    card_rank = m["card_rank"]
    if len(card_rank) >= 3:
        cards_txt = (f"Among cards, {card_rank[0]} leads {card_rank[1]}, "
                     f"with {card_rank[2]} third.")
    elif len(card_rank) == 2:
        cards_txt = f"Among cards, {card_rank[0]} leads {card_rank[1]}."
    elif card_rank:
        cards_txt = f"Among cards, {card_rank[0]} leads."
    else:
        cards_txt = ""

    insights = [
        ("1 · The product launched in Q4 2025",
         "About <span class='big'>98.8%</span> of all orders in the raw export "
         "and 100% of positive revenue fall in Oct–Dec 2025. The earlier months "
         "(Mar–Sep) hold only a few hundred net-<i>negative</i> rows — refunds or "
         "pre-launch test activity — so the dashboard is built on Q4 only."),
        ("2 · Recurring revenue is the engine",
         f"Recurring orders generate <span class='big'>{m['rec_share']:.0f}%</span> "
         f"of net payout and a higher value per order (<b>${m['avg_rec']:,.2f}</b>) "
         f"than first-time orders (<b>${m['avg_first']:,.2f}</b>). Upsells are the "
         f"most valuable at <b>${m['avg_up']:,.2f}</b> / order — the business "
         "monetises existing subscribers far more than new ones."),
        ("3 · Revenue is geographically concentrated",
         f"The United States alone is <span class='big'>{m['usa_share']:.0f}%</span> "
         f"of net payout, and the top 10 of {m['n_markets']} markets account for "
         f"<span class='big'>{m['top10_share']:.0f}%</span>. Growth depends heavily "
         "on a short list of countries — a concentration risk worth watching."),
        ("4 · The customer base is overwhelmingly male",
         f"Around <span class='big'>{m['male_share']:.0f}%</span> of orders come "
         "from male customers. That is a strong targeting signal — and a prompt to "
         "check whether the female / unknown segment is untapped demand or a "
         "tracking gap."),
        ("5 · Payments split three ways; 'missing' card brand is structural",
         "Payments split almost evenly three ways: card, Apple Pay and APM each "
         "carry roughly a third of net payout, with "
         f"<b>{pm_top}</b> marginally in front. The blank card brand is <i>not</i> "
         "dirty data — it maps almost 1:1 to APM (non-card) payments. "
         f"{cards_txt}"),
    ]
    for title, body in insights:
        st.markdown(f'<div class="insight"><h4>{title}</h4><p>{body}</p></div>',
                    unsafe_allow_html=True)

    st.caption(f"Figures derived from the full Q4 2025 dataset "
               f"({len(df):,} rows · {fmt_int(m['total_orders'])} orders · "
               f"{fmt_usd(m['total_net'])} net payout).")
