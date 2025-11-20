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
