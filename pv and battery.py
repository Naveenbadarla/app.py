import streamlit as st
import pandas as pd


# ---------- Core calculation logic ----------

def compute_scenarios(
    load_kwh: float,
    load_kwh_2: float,
    pv_kwp: float,
    pv_yield_kwh_per_kwp: float,
    grid_price: float,
    fit_price: float,
    batt_capacity_kwh: float,
    batt_efficiency: float,
    cycles_per_day: float,
    sc_ratio_no_batt_1: float,
    sc_ratio_no_batt_2: float,
    da_spread: float,
    opt_capture: float,
    nonopt_capture: float,
) -> pd.DataFrame:
    """
    Compute yearly energy flows and costs for:
      - No battery
      - Battery, non-optimised
      - Battery, DA-optimised

    for two different household loads.
    """
    pv_gen = pv_kwp * pv_yield_kwh_per_kwp
    results = []

    def compute_for_load(load_kwh, sc_ratio_no_batt, label):
        # --- No battery ---
        # Direct PV self-consumption (simple assumption: fraction of load)
        pv_sc_no_batt = min(load_kwh * sc_ratio_no_batt, pv_gen)
        pv_export_no_batt = max(0.0, pv_gen - pv_sc_no_batt)
        grid_import_no_batt = max(0.0, load_kwh - pv_sc_no_batt)

        grid_cost_no_batt = grid_import_no_batt * grid_price
        fit_rev_no_batt = pv_export_no_batt * fit_price
        net_cost_no_batt = grid_cost_no_batt - fit_rev_no_batt

        # --- Battery basics (unidirectional: only PV -> battery -> house) ---
        batt_eff = batt_efficiency
        batt_nominal_throughput = batt_capacity_kwh * batt_eff * cycles_per_day * 365.0

        # Max extra self-consumption limited by remaining load
        max_extra_sc = max(0.0, load_kwh - pv_sc_no_batt)
        e_shift = min(batt_nominal_throughput, max_extra_sc)  # usable energy to load
        pv_to_batt = e_shift / batt_eff if batt_eff > 0 else 0.0

        pv_sc_batt = pv_sc_no_batt + e_shift
        pv_export_batt = max(0.0, pv_gen - pv_sc_no_batt - pv_to_batt)
        grid_import_batt = max(0.0, load_kwh - pv_sc_batt)

        grid_cost_batt_base = grid_import_batt * grid_price
        fit_rev_batt = pv_export_batt * fit_price
        net_cost_batt_base = grid_cost_batt_base - fit_rev_batt

        # --- DA arbitrage ---
        # Simple: only meaningful if there is actual grid import without battery
        # (otherwise you're basically fully PV-supplied already).
        arbitrage_energy = e_shift if grid_import_no_batt > 0 else 0.0

        spread_opt = da_spread * opt_capture
        spread_non = da_spread * nonopt_capture

        arbitrage_non = arbitrage_energy * spread_non
        arbitrage_opt = arbitrage_energy * spread_opt

        net_cost_batt_nonopt = net_cost_batt_base - arbitrage_non
        net_cost_batt_opt = net_cost_batt_base - arbitrage_opt

        # --- Collect rows ---
        results.extend([
            {
                "Scenario": label,
                "Configuration": "No battery",
                "Load (kWh/yr)": load_kwh,
                "PV generation (kWh/yr)": pv_gen,
                "Direct PV self-consumption (kWh/yr)": pv_sc_no_batt,
                "Battery -> load (kWh/yr)": 0.0,
                "PV export (kWh/yr)": pv_export_no_batt,
                "Grid import (kWh/yr)": grid_import_no_batt,
                "Grid cost (€)": grid_cost_no_batt,
                "EEG revenue (€)": fit_rev_no_batt,
                "DA arbitrage (€)": 0.0,
                "Net annual cost (€)": net_cost_no_batt,
            },
            {
                "Scenario": label,
                "Configuration": "Battery – non-optimised",
                "Load (kWh/yr)": load_kwh,
                "PV generation (kWh/yr)": pv_gen,
                "Direct PV self-consumption (kWh/yr)": pv_sc_no_batt,
                "Battery -> load (kWh/yr)": e_shift,
                "PV export (kWh/yr)": pv_export_batt,
                "Grid import (kWh/yr)": grid_import_batt,
                "Grid cost (€)": grid_cost_batt_base,
                "EEG revenue (€)": fit_rev_batt,
                "DA arbitrage (€)": arbitrage_non,
                "Net annual cost (€)": net_cost_batt_nonopt,
            },
            {
                "Scenario": label,
                "Configuration": "Battery – DA-optimised",
                "Load (kWh/yr)": load_kwh,
                "PV generation (kWh/yr)": pv_gen,
                "Direct PV self-consumption (kWh/yr)": pv_sc_no_batt,
                "Battery -> load (kWh/yr)": e_shift,
                "PV export (kWh/yr)": pv_export_batt,
                "Grid import (kWh/yr)": grid_import_batt,
                "Grid cost (€)": grid_cost_batt_base,
                "EEG revenue (€)": fit_rev_batt,
                "DA arbitrage (€)": arbitrage_opt,
                "Net annual cost (€)": net_cost_batt_opt,
            },
        ])

    compute_for_load(load_kwh, sc_ratio_no_batt_1, "Low load")
    compute_for_load(load_kwh_2, sc_ratio_no_batt_2, "High load")

    df = pd.DataFrame(results)
    return df


# ---------- Streamlit UI ----------

def main():
    st.set_page_config(
        page_title="PV + Battery + DA Optimisation (Germany / EEG)",
        layout="wide",
    )

    st.title("PV + Battery + Day-Ahead Optimisation – Comparison Tool")
    st.markdown(
        """
This tool compares **annual energy flows and costs** for two households with:
- PV, EEG feed-in,
- an optional battery (unidirectional to the grid),
- and **non-optimised vs DA-optimised** battery control.

You can tune all assumptions in the sidebar.
"""
    )

    # ---- Sidebar inputs ----
    st.sidebar.header("Global assumptions")

    col_pv1, col_pv2 = st.sidebar.columns(2)
    with col_pv1:
        pv_kwp = st.number_input("PV size (kWp)", min_value=0.0, value=9.5, step=0.1)
    with col_pv2:
        pv_yield = st.number_input(
            "PV yield (kWh/kWp·year)", min_value=400.0, value=950.0, step=10.0
        )

    st.sidebar.subheader("Prices")
    grid_price = st.number_input(
        "Grid price (€/kWh)", min_value=0.0, value=0.39, step=0.01, format="%.3f"
    )
    fit_price = st.number_input(
        "Feed-in tariff (€/kWh)", min_value=0.0, value=0.08, step=0.005, format="%.3f"
    )

    st.sidebar.subheader("Battery")
    batt_capacity = st.number_input(
        "Battery capacity (kWh)", min_value=0.0, value=8.8, step=0.1
    )
    batt_efficiency = st.slider(
        "Round-trip efficiency (%)", min_value=50, max_value=100, value=93, step=1
    ) / 100.0
    cycles_per_day = st.number_input(
        "Cycles per day", min_value=0.0, value=1.0, step=0.1
    )

    st.sidebar.subheader("Day-ahead (DA) market")
    da_spread = st.number_input(
        "Average DA daily spread (€/kWh)",
        min_value=0.0,
        value=0.112,
        step=0.01,
        format="%.3f",
    )
    col_da1, col_da2 = st.sidebar.columns(2)
    with col_da1:
        opt_capture = st.slider(
            "Optimised capture fraction", min_value=0.0, max_value=1.0, value=0.7, step=0.05
        )
    with col_da2:
        nonopt_capture = st.slider(
            "Non-optimised capture fraction",
            min_value=0.0,
            max_value=1.0,
            value=0.35,
            step=0.05,
        )

    st.sidebar.subheader("Household loads & self-consumption (no battery)")
    load1 = st.number_input(
        "Scenario 1 load (kWh/yr)", min_value=0.0, value=3000.0, step=500.0
    )
    load2 = st.number_input(
        "Scenario 2 load (kWh/yr)", min_value=0.0, value=10000.0, step=500.0
    )
    sc_ratio1 = st.slider(
        "Scenario 1 self-consumption ratio without battery (fraction of load)",
        min_value=0.0,
        max_value=1.0,
        value=0.8,
        step=0.05,
    )
    sc_ratio2 = st.slider(
        "Scenario 2 self-consumption ratio without battery (fraction of load)",
        min_value=0.0,
        max_value=1.0,
        value=0.3,
        step=0.05,
    )

    st.sidebar.markdown("---")
    st.sidebar.caption("Tip: adjust loads, PV size, and DA spread to see how the optimisation value changes.")

    # ---- Compute and display ----
    df = compute_scenarios(
        load_kwh=load1,
        load_kwh_2=load2,
        pv_kwp=pv_kwp,
        pv_yield_kwh_per_kwp=pv_yield,
        grid_price=grid_price,
        fit_price=fit_price,
        batt_capacity_kwh=batt_capacity,
        batt_efficiency=batt_efficiency,
        cycles_per_day=cycles_per_day,
        sc_ratio_no_batt_1=sc_ratio1,
        sc_ratio_no_batt_2=sc_ratio2,
        da_spread=da_spread,
        opt_capture=opt_capture,
        nonopt_capture=nonopt_capture,
    )

    # Round for nicer display
    display_cols = [
        "Scenario",
        "Configuration",
        "Load (kWh/yr)",
        "PV generation (kWh/yr)",
        "Direct PV self-consumption (kWh/yr)",
        "Battery -> load (kWh/yr)",
        "PV export (kWh/yr)",
        "Grid import (kWh/yr)",
        "Grid cost (€)",
        "EEG revenue (€)",
        "DA arbitrage (€)",
        "Net annual cost (€)",
    ]
    df_display = df[display_cols].copy()
    numeric_cols = [
        c for c in df_display.columns if c not in ["Scenario", "Configuration"]
    ]
    df_display[numeric_cols] = df_display[numeric_cols].round(2)

    st.header("Results table")
    st.dataframe(df_display, use_container_width=True)

    # ---- Summary tables ----
    st.header("Summary: net annual costs and savings")

    # Pivot for charts
    cost_summary = df.pivot(
        index="Scenario", columns="Configuration", values="Net annual cost (€)"
    )

    st.subheader("Net annual cost by scenario and configuration")
    st.dataframe(cost_summary.round(2))

    # Calculate savings vs no battery within each scenario
    summary_rows = []
    for scenario in df["Scenario"].unique():
        df_s = df[df["Scenario"] == scenario].set_index("Configuration")
        cost_no_batt = df_s.loc["No battery", "Net annual cost (€)"]
        cost_nonopt = df_s.loc["Battery – non-optimised", "Net annual cost (€)"]
        cost_opt = df_s.loc["Battery – DA-optimised", "Net annual cost (€)"]

        summary_rows.append(
            {
                "Scenario": scenario,
                "No battery – net cost (€)": cost_no_batt,
                "Battery non-optimised – net cost (€)": cost_nonopt,
                "Battery DA-optimised – net cost (€)": cost_opt,
                "Savings vs no battery (non-optimised) (€)": cost_no_batt - cost_nonopt,
                "Savings vs no battery (DA-optimised) (€)": cost_no_batt - cost_opt,
                "Extra savings from optimisation (€)": cost_nonopt - cost_opt,
            }
        )

    df_summary = pd.DataFrame(summary_rows)
    df_summary_rounded = df_summary.copy()
    for c in df_summary_rounded.columns:
        if c != "Scenario":
            df_summary_rounded[c] = df_summary_rounded[c].round(2)

    st.dataframe(df_summary_rounded, use_container_width=True)

    # ---- Simple bar chart ----
    st.subheader("Net annual cost comparison (lower is better)")
    st.bar_chart(cost_summary)


if __name__ == "__main__":
    main()
