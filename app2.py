import streamlit as st
import numpy_financial as npf
import pandas as pd

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="Chicago Real Estate Pro",
    layout="wide",
    page_icon="🏙️",
    initial_sidebar_state="expanded"
)

# --- 2. APPLE-STYLE CSS ---
st.markdown("""
<style>
    /* Font & Background */
    .main { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    
    /* Widget Cards (Apple Style) */
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 10px;
        height: 100%;
    }
    .metric-label { font-size: 0.85rem; color: #6b7280; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-value { font-size: 1.8rem; font-weight: 700; color: #111827; margin-top: 5px; }
    .metric-sub { font-size: 0.85rem; margin-top: 5px; font-weight: 500; }
    
    .text-green { color: #10b981; }
    .text-red { color: #ef4444; }
    .text-gray { color: #6b7280; }
    
    /* Verdict Banners */
    .verdict-box { padding: 20px; border-radius: 12px; color: white; margin-bottom: 20px; }
    .v-buy { background: linear-gradient(135deg, #34d399 0%, #059669 100%); box-shadow: 0 10px 15px -3px rgba(5, 150, 105, 0.2); }
    .v-rent { background: linear-gradient(135deg, #f87171 0%, #dc2626 100%); box-shadow: 0 10px 15px -3px rgba(220, 38, 38, 0.2); }
    
    /* Sidebar headers */
    .stSidebar h1, .stSidebar h2, .stSidebar h3 { font-weight: 600; letter-spacing: -0.02em; }
</style>
""", unsafe_allow_html=True)

# --- 3. STATE INITIALIZATION ---
defaults = {
    "price": 450000, "down_pct": 0.20, "rate": 0.065, "term": 30,
    "tax_rate": 1.80, "hoa": 450, "insurance": 1200, "maint": 0.005,
    "pmi": 0.005, "closing_costs": 3000, "use_chi_tax": True,
    "rent": 2800, "rent_inf": 0.03, "apprec": 0.03, "hold": 7, "inv_ret": 0.07,
    "income": 150000, "status": "Single", "debt": 500,
    "assess_amt": 0, "assess_yr": 5, "sell_cost": 0.06
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

NEIGHBORHOODS = {
    "Custom": 1.80, "Loop": 1.95, "River North": 1.85, "West Loop": 2.10, 
    "Lincoln Park": 1.65, "Lakeview": 1.70, "South Loop": 2.05, "Wicker Park": 1.75
}

# --- 4. SIDEBAR SETTINGS ---
with st.sidebar:
    st.title("Settings")
    
    with st.expander("🏠 Loan & Property", expanded=True):
        st.session_state.price = st.number_input("Price ($)", value=st.session_state.price, step=5000)
        c1, c2 = st.columns(2)
        st.session_state.down_pct = c1.number_input("Down %", 0, 100, int(st.session_state.down_pct*100)) / 100
        st.session_state.rate = c2.number_input("Rate %", 0.0, 10.0, st.session_state.rate*100, step=0.125) / 100
        st.checkbox("Chicago Transfer Tax (0.75%)", key="use_chi_tax")

    with st.expander("💸 Monthly Expenses"):
        hood = st.selectbox("Auto-fill Tax Rate", list(NEIGHBORHOODS.keys()))
        if hood != "Custom" and NEIGHBORHOODS[hood] != st.session_state.tax_rate:
            st.session_state.tax_rate = NEIGHBORHOODS[hood]
            
        st.session_state.tax_rate = st.number_input("Tax Rate (%)", value=st.session_state.tax_rate, step=0.1)
        st.session_state.hoa = st.number_input("HOA ($)", value=st.session_state.hoa, step=10)
        st.session_state.insurance = st.number_input("Insurance ($/yr)", value=st.session_state.insurance, step=100)

    with st.expander("📈 Market Assumptions"):
        st.session_state.rent = st.number_input("Comp Rent ($)", value=st.session_state.rent, step=50)
        st.session_state.apprec = st.slider("Appreciation %", -2.0, 8.0, st.session_state.apprec*100) / 100
        st.session_state.hold = st.slider("Hold Years", 1, 30, st.session_state.hold)
        
    with st.expander("👤 Income & Tax Shield"):
        st.session_state.income = st.number_input("Annual Income ($)", value=st.session_state.income, step=5000)
        st.session_state.status = st.selectbox("Filing Status", ["Single", "Married"])
        st.session_state.debt = st.number_input("Other Debt ($/mo)", value=st.session_state.debt)

# --- 5. LOGIC ENGINE ---
def run_simulation(years, appreciation):
    # Setup
    P = st.session_state.price
    DP = P * st.session_state.down_pct
    L = P - DP
    r_mo = st.session_state.rate / 12
    n_mo = 360 
    
    # Mortgage Calc
    if r_mo > 0:
        pi = L * (r_mo * (1 + r_mo)**n_mo) / ((1 + r_mo)**n_mo - 1)
    else:
        pi = L / n_mo

    # Cash to Close
    chi_tax = P * 0.0075 if st.session_state.use_chi_tax else 0
    initial_cash = DP + st.session_state.closing_costs + chi_tax
    
    # 2026 Tax Shield Logic
    # Standard Deduction 2026 Est
    std_ded = 15450 if st.session_state.status == "Single" else 30900
    # 35% Bracket Threshold
    threshold = 258000 if st.session_state.status == "Single" else 516000
    marg_rate = 0.35 if st.session_state.income > threshold else 0.24
    
    # Loop
    data = []
    diff_flows = [] 
    
    curr_val = P
    curr_rent = st.session_state.rent
    curr_hoa = st.session_state.hoa
    loan_bal = L
    renter_wealth = initial_cash
    
    # Capture Year 1 Tax Savings for Dashboard
    y1_monthly_tax_savings = 0
    
    for y in range(1, years + 1):
        # Interest & Principal
        int_yr = 0
        for _ in range(12):
            i = loan_bal * r_mo
            loan_bal -= (pi - i)
            int_yr += i
            
        # Expenses
        tax = curr_val * (st.session_state.tax_rate/100)
        maint = curr_val * st.session_state.maint
        ins = st.session_state.insurance
        hoa_yr = curr_hoa * 12
        assess = st.session_state.assess_amt if y == st.session_state.assess_yr else 0
        
        # PMI
        ltv = loan_bal / curr_val
        pmi = (P * st.session_state.pmi) if ltv > 0.80 else 0
        
        # Tax Benefit Calc
        # Itemized = SALT (Max 10k) + Mortgage Interest
        salt_deduction = min(tax, 10000)
        itemized = salt_deduction + int_yr
        # Only count benefit ABOVE standard deduction
        benefit = max(0, itemized - std_ded) * marg_rate
        
        if y == 1:
            y1_monthly_tax_savings = benefit / 12

        # Net Annual Cost
        cost_buy = (pi*12) + hoa_yr + tax + maint + ins + pmi + assess - benefit
        cost_rent = (curr_rent * 12) + 250
        
        diff = cost_buy - cost_rent
        renter_wealth = renter_wealth * (1 + st.session_state.inv_ret) + diff
        diff_flows.append(-cost_buy)
        
        # Sunk Costs
        sunk_buy = int_yr + tax + hoa_yr + maint + ins + pmi - benefit
        
        data.append({
            "Year": y, "Equity": curr_val - loan_bal, "Renter Wealth": renter_wealth,
            "Buy Sunk": sunk_buy, "Rent Sunk": cost_rent,
            "Tax Savings": benefit
        })
        
        curr_val *= (1 + appreciation)
        curr_rent *= (1 + st.session_state.rent_inf)
        curr_hoa *= 1.04 

    # Terminal Sale
    sale_cost = curr_val * st.session_state.sell_cost
    sale_proceeds = curr_val - loan_bal - sale_cost
    diff_flows[-1] += sale_proceeds
    
    npv = npf.npv(st.session_state.inv_ret, [-initial_cash] + diff_flows)
    
    rent_stream = [-(st.session_state.rent * 12 * ((1+st.session_state.rent_inf)**i)) for i in range(years)]
    rent_stream[-1] += renter_wealth
    npv_rent = npf.npv(st.session_state.inv_ret, [0] + rent_stream)
    
    # Underwriting Monthly (Gross)
    gross_monthly_housing = pi + st.session_state.hoa + (tax/12) + (ins/12) + (pmi/12)
    
    return npv - npv_rent, data, initial_cash, pi, gross_monthly_housing, y1_monthly_tax_savings

# Run Simulation
net_val, data, cash_req, monthly_pi, gross_housing, tax_savings = run_simulation(st.session_state.hold, st.session_state.apprec)

# --- 6. DASHBOARD UI ---
st.title("Chicago Real Estate Pro")

# --- VERDICT ---
if net_val > 0:
    st.markdown(f'<div class="verdict-box v-buy"><h2>✅ BUYING WINS</h2><h1 style="margin:0;">${net_val:,.0f}</h1><p>NPV Advantage over {st.session_state.hold} years</p></div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="verdict-box v-rent"><h2>🛑 RENTING WINS</h2><h1 style="margin:0;">${abs(net_val):,.0f}</h1><p>NPV Advantage over {st.session_state.hold} years</p></div>', unsafe_allow_html=True)

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Snapshot", "⚠️ Sensitivity", "📉 Sunk Costs"])

with tab1:
    # --- ROW 1: CASH & DTI ---
    c1, c2, c3, c4 = st.columns(4)
    
    def card(label, value, sub="", color="text-gray"):
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub {color}">{sub}</div>
        </div>
        """, unsafe_allow_html=True)

    with c1:
        card("Cash to Close", f"${cash_req:,.0f}", "Includes Closing Costs")
    with c2:
        # DTI
        gross_inc = st.session_state.income / 12
        dti = (gross_housing + st.session_state.debt) / gross_inc
        dti_color = "text-green" if dti < 0.36 else "text-red"
        card("Back-End DTI", f"{dti*100:.1f}%", f"Limit: 43%", dti_color)
    with c3:
        # Tax Shield Card
        if tax_savings > 0:
            card("Tax Shield", f"${tax_savings:,.0f}/mo", "IRS Savings (Yr 1)", "text-green")
        else:
            card("Tax Shield", "$0", "Std Deduction Used", "text-gray")
    with c4:
        # Net Effective Cost
        net_cost = gross_housing - tax_savings
        card("Net Monthly", f"${net_cost:,.0f}", "After Tax Savings", "text-green")

    # --- ROW 2: WEALTH CHART ---
    st.markdown("### 📈 Wealth Accumulation")
    df = pd.DataFrame(data).set_index("Year")
    st.line_chart(df[["Equity", "Renter Wealth"]], color=["#007AFF", "#FF3B30"])

with tab2:
    st.subheader("Sensitivity Matrix")
    st.caption("Green = Buying is Better | Red = Renting is Better")
    
    # Lightweight Matrix Run
    holds = [3, 5, 7, 10, 15]
    apprecs = [-0.01, 0.00, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
    
    matrix = []
    for a in apprecs:
        row = {"Appreciation": f"{a*100:.0f}%"}
        for h in holds:
            val, _, _, _, _, _ = run_simulation(h, a)
            row[f"{h} Yrs"] = int(val)
        matrix.append(row)
        
    df_mat = pd.DataFrame(matrix).set_index("Appreciation")
    st.dataframe(df_mat.style.background_gradient(cmap="RdYlGn", axis=None).format("${:,.0f}"), use_container_width=True)

with tab3:
    st.subheader("Sunk Cost Analysis")
    st.markdown("**'Money Thrown Away' Comparison:**")
    st.markdown("- **Rent:** 100% Sunk Cost")
    st.markdown("- **Buy:** Interest + Taxes + HOA + Maintenance - **Tax Savings**")
    st.line_chart(df[["Buy Sunk", "Rent Sunk"]], color=["#007AFF", "#FF3B30"])