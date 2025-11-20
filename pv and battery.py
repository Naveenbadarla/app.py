import streamlit as st
import pandas as pd

# =====================================================================
# CORE CALCULATION LOGIC
# =====================================================================

def compute_scenario(
    load_kwh,
    pv_kwp,
    pv_yield,
    grid_price,
    fit_price,
    batt_capacity,
    batt_efficiency,
    cycles_per_day,
    sc_ratio_no_batt,
    da_spread,
    opt_capture,
    nonopt_capture,
):
    pv_gen = pv_kwp * pv_yield

    # --------------------------
    # No Battery
    # --------------------------
    pv_direct_sc = min(load_kwh * sc_ratio_no_batt, pv_gen)
    pv_export_no_batt = max(0.0, pv_gen - pv_direct_sc)
    grid_import_no_batt = max(0.0, load_kwh - pv_direct_sc)

    cost_no_batt = grid_import_no_batt * grid_price
    revenue_no_batt = pv_export_no_batt * fit_price
    net_no_batt = cost_no_batt - revenue_no_batt

    # --------------------------
    # Battery Baseline
    # --------------------------
    batt_theoretical = batt_capacity * batt_efficiency * cycles_per_day * 365
    remaining_load = max(0.0, load_kwh - pv_direct_sc)
    batt_usable = min(batt_theoretical, remaining_load)

    pv_to_batt = batt_usable / batt_efficiency
    pv_export_batt = max(0.0, pv_gen - pv_direct_sc - pv_to_batt)
    grid_import_batt = max(0.0, load_kwh - (pv_direct_sc + batt_usable))

    cost_batt_base = grid_import_batt * grid_price
    revenue_batt = pv_export_batt * fit_price
    net_batt_base = cost_batt_base - revenue_batt

    arbitrage_energy = batt_usable if grid_import_no_batt > 0 else 0

    arbitrage_non = arbitrage_energy * da_spread * nonopt_capture
    arbitrage_opt = arbitrage_energy * da_spread * opt_capture

    net_batt_nonopt = net_batt_base - arbitrage_non
    net_batt_opt = net_batt_base - arbitrage_opt

    df = pd.DataFrame([
        {
            "Configuration": "No battery",
            "PV generation (kWh)": pv_gen,
            "PV self-consumption (kWh)": pv_direct_sc,
            "Battery -> load (kWh)": 0.0,
            "PV export (kWh)": pv_export_no_batt,
            "Grid import (kWh)": grid_import_no_batt,
            "Grid cost (€)": cost_no_batt,
            "EEG revenue (€)": revenue_no_batt,
            "DA arbitrage (€)": 0.0,
            "Net annual cost (€)": net_no_batt
        },
        {
            "Configuration": "Battery – non-optimised",
            "PV generation (kWh)": pv_gen,
            "PV self-consumption (kWh)": pv_direct_sc,
            "Battery -> load (kWh)": batt_usable,
            "PV export (kWh)": pv_export_batt,
            "Grid import (kWh)": grid_import_batt,
            "Grid cost (€)": cost_batt_base,
            "EEG revenue (€)": revenue_batt,
            "DA arbitrage (€)": arbitrage_non,
            "Net annual cost (€)": net_batt_nonopt
        },
        {
            "Configuration": "Battery – DA-optimised",
            "PV generation (kWh)": pv_gen,
            "PV self-consumption (kWh)": pv_direct_sc,
            "Battery -> load (kWh)": batt_usable,
            "PV export (kWh)": pv_export_batt,
            "Grid import (kWh)": grid_import_batt,
            "Grid cost (€)": cost_batt_base,
            "EEG revenue (€)": revenue_batt,
            "DA arbitrage (€)": arbitrage_opt,
            "Net annual cost (€)": net_batt_opt
        }
    ])

    return df

# =====================================================================
# STREAMLIT UI
# =====================================================================

def main():
    st.set_page_config(page_title="PV + Battery + DA Optimisation", layout="wide")

    st.title("⚡ PV + Battery + Day-Ahead Optimisation (Germany / EEG)")

    st.markdown('''
Welcome!  
This tool shows how PV, a battery, and day-ahead (DA) optimisation change your **yearly energy cost**.
''')

    # Sidebar
    st.sidebar.header("System Setup")

    with st.sidebar.expander("Quick explanation", expanded=True):
        st.markdown('''
### Energy Flow Model

### What "Net Annual Cost" Means
Net annual cost = Grid cost - EEG revenue  
Positive = You pay money  
Negative = You earn money  
''')

    load_kwh = st.sidebar.number_input("Annual household load (kWh)", 0.0, 20000.0, 3000.0, 500.0)
    pv_kwp = st.sidebar.number_input("PV size (kWp)", 0.0, 40.0, 9.5, 0.1)
    pv_yield = st.sidebar.number_input("PV yield (kWh/kWp·yr)", 200.0, 1500.0, 950.0, 10.0)
    grid_price = st.sidebar.number_input("Grid price (€/kWh)", 0.0, 1.0, 0.39, 0.01)
    fit_price = st.sidebar.number_input("Feed-in tariff (€/kWh)", 0.0, 1.0, 0.08, 0.01)
    batt_capacity = st.sidebar.number_input("Battery capacity (kWh)", 0.0, 40.0, 8.8, 0.1)
    batt_eff = st.sidebar.slider("Battery efficiency (%)", 60, 100, 93) / 100
    cycles = st.sidebar.number_input("Cycles per day", 0.0, 2.0, 1.0, 0.1)
    sc_ratio = st.sidebar.slider("Self-consumption ratio (no battery)", 0.0, 1.0, 0.8, 0.05)
    da_spread = st.sidebar.number_input("DA price spread (€/kWh)", 0.0, 0.5, 0.112, 0.01)
    opt_cap = st.sidebar.slider("Optimiser capture fraction", 0.0, 1.0, 0.7)
    nonopt_cap = st.sidebar.slider("Non-optimised capture fraction", 0.0, 1.0, 0.35)

    # Run model
    df = compute_scenario(
        load_kwh, pv_kwp, pv_yield, grid_price, fit_price,
        batt_capacity, batt_eff, cycles, sc_ratio,
        da_spread, opt_cap, nonopt_cap,
    )

    for col in df.columns:
        if col != "Configuration":
            df[col] = df[col].round(2)

    # Tabs
    tab_results, tab_params, tab_logic, tab_read = st.tabs([
        "Results", "Parameter Guide", "Optimisation Logic", "How to Read Results"
    ])

    # =================== RESULTS TAB ===================
    with tab_results:
        st.header("Results")
        st.dataframe(df, use_container_width=True)

        cost = df.set_index("Configuration")["Net annual cost (€)"]
        nb = float(cost["No battery"])
        non = float(cost["Battery – non-optimised"])
        opt = float(cost["Battery – DA-optimised"])

        c1, c2, c3 = st.columns(3)
        c1.metric("No battery", f"{nb:,.0f} €")
        c2.metric("Battery (simple)", f"{non:,.0f} €", f"{nb - non:,.0f} € saved")
        c3.metric("Battery (optimised)", f"{opt:,.0f} €", f"{non - opt:,.0f} € extra")

        st.subheader("Cost comparison chart")
        st.bar_chart(df.set_index("Configuration")["Net annual cost (€)"])

        with st.expander("Short explanation"):
            st.markdown('''
- Positive net cost -> you pay money  
- Negative net cost -> your exported PV earns more than your costs  
- Battery gives major savings  
- Optimisation adds extra value  
''')

    # =================== PARAMETER GUIDE ===================
    with tab_params:
        st.header("Parameter Guide")
        st.markdown('''
### Load  
Higher load = more battery value.

### PV  
Larger PV = more self-consumption + export revenue.

### Battery  
- Larger = more storage  
- Higher efficiency = less loss  
- More cycles/day = more throughput  

### DA Spread  
Bigger spread = more price differences to exploit.
''')

    # =================== OPTIMISATION LOGIC ===================
    with tab_logic:
        st.header("Optimisation Logic")
        st.markdown('''
The optimiser:
- Charges more during cheap hours  
- Discharges more during expensive hours  

Limited by:
- Battery capacity  
- Cycles/day  
- PV availability  
- Remaining load  
''')

    # =================== HOW TO READ RESULTS ===================
    with tab_read:
        st.header("How to Read Results")

        st.markdown('''
## Net Annual Cost  
Net cost = Grid cost - EEG revenue  
Positive = you pay money  
Negative = you earn money  

## How to Compare  
- Battery vs No Battery -> main savings  
- Optimised vs Non-Optimised -> extra optimisation value  

## Why negative costs occur  
Large PV + small load = export earnings exceed grid import.
''')


if __name__ == "__main__":
    main()
