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
        # Simple assumption: arbitrage is only relevant if there is grid import
        # without a battery (you can't arbitrage zero import).
        arbitrage_energy = e_shift if grid_import_no_batt > 0 else 0.0

        spread_opt = da_spread * opt_capture
        spread_non = da_spread * nonopt_capture

        arbitrage_non = arbitrage_energy * spread_non
        arbitrage_opt = arbitrage_energy * spread_opt

        net_cost_batt_nonopt = net_cost_batt_base - arbitrage_non
        net_cost_batt_opt = net_cost_batt_base - arbitrage_opt

        # --- Collect rows ---
        results.extend(
            [
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
            ]
        )

    compute_for_load(load_kwh, sc_ratio_no_batt_1, "Scenario 1 (e.g. 3 MWh)")
    compute_for_load(load_kwh_2, sc_ratio_no_batt_2, "Scenario 2 (e.g. 10 MWh)")

    df = pd.DataFrame(results)
    return df


# ---------- Streamlit UI ----------

def main():
    st.set_page_config(
        page_title="PV + Battery + DA Optimisation (Germany / EEG)",
        layout="wide",
    )

    st.title("PV + Battery + Day-Ahead Optimisation – Germany / EEG")
    st.markdown(
        """
This app compares **annual energy flows and costs** for two household demand levels
(e.g. 3,000 kWh and 10,000 kWh per year) with:

- Rooftop PV and EEG feed-in,
- An optional **battery** that only supplies the house (no feed-in from the battery to the grid),
- Two control strategies:
  - **Non-optimised** (simple control),
  - **Day-ahead (DA) optimised** control using price signals.

Use the **sidebar** to adjust all assumptions, and use the tabs below to:
- See results,
- Understand what each parameter means,
- Read about the optimisation logic and the energy flow model.
"""
    )

    st.sidebar.header("Model assumptions")

    with st.sidebar.expander("ℹ️ Quick explanation", expanded=True):
        st.write(
            """
- **PV + EEG:** PV generation can be self-consumed or exported to the grid for a feed-in tariff (EEG).
- **Battery (unidirectional):** The battery can be charged from PV and serve the house, but we assume it does **not** export to the grid.
- **Optimisation:** Day-ahead optimisation tries to charge in cheaper hours and discharge in expensive hours (within the limits of your load and PV).
"""
        )

    # ---- Sidebar inputs ----
    st.sidebar.subheader("PV system")
    col_pv1, col_pv2 = st.sidebar.columns(2)
    with col_pv1:
        pv_kwp = st.number_input(
            "PV size (kWp)",
            min_value=0.0,
            value=9.5,
            step=0.1,
            help="Installed peak power of the PV system. Higher kWp → more annual PV generation.",
        )
    with col_pv2:
        pv_yield = st.number_input(
            "PV yield (kWh/kWp·year)",
            min_value=400.0,
            value=950.0,
            step=10.0,
            help=(
                "Annual specific yield per kWp. Depends on location, tilt, orientation etc. "
                "Total PV generation = kWp × this value."
            ),
        )

    st.sidebar.subheader("Prices")
    grid_price = st.number_input(
        "Grid price (€/kWh)",
        min_value=0.0,
        value=0.39,
        step=0.01,
        format="%.3f",
        help="Retail electricity price you pay for each kWh imported from the grid.",
    )
    fit_price = st.number_input(
        "Feed-in tariff (€/kWh)",
        min_value=0.0,
        value=0.08,
        step=0.005,
        format="%.3f",
        help="EEG remuneration for each kWh of PV exported to the grid.",
    )

    st.sidebar.subheader("Battery")
    batt_capacity = st.number_input(
        "Battery capacity (kWh)",
        min_value=0.0,
        value=8.8,
        step=0.1,
        help="Usable energy capacity of the battery. Higher capacity allows more shifting per day.",
    )
    batt_efficiency = st.slider(
        "Round-trip efficiency (%)",
        min_value=50,
        max_value=100,
        value=93,
        step=1,
        help="Combined charge + discharge efficiency. 93% means that 1000 kWh in → 930 kWh out.",
    ) / 100.0
    cycles_per_day = st.number_input(
        "Cycles per day",
        min_value=0.0,
        value=1.0,
        step=0.1,
        help=(
            "Average number of full cycles per day. 1 cycle/day means the battery charges and discharges "
            "its full capacity once per day on average."
        ),
    )

    st.sidebar.subheader("Day-ahead (DA) market")
    da_spread = st.number_input(
        "Average DA daily spread (€/kWh)",
        min_value=0.0,
        value=0.112,
        step=0.01,
        format="%.3f",
        help=(
            "Typical difference between cheap and expensive hours in the day-ahead price. "
            "Higher spread → more value from shifting energy between hours."
        ),
    )
    col_da1, col_da2 = st.sidebar.columns(2)
    with col_da1:
        opt_capture = st.slider(
            "Optimised capture fraction",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.05,
            help=(
                "Fraction of the DA spread that the optimised control can actually capture. "
                "1.0 = perfect arbitrage between cheapest and most expensive hours."
            ),
        )
    with col_da2:
        nonopt_capture = st.slider(
            "Non-optimised capture fraction",
            min_value=0.0,
            max_value=1.0,
            value=0.35,
            step=0.05,
            help=(
                "Fraction of the DA spread captured by simple / non-optimised control. "
                "Higher value means the baseline is already quite good."
            ),
        )

    st.sidebar.subheader("Household loads & baseline self-consumption")
    load1 = st.number_input(
        "Scenario 1 load (kWh/yr)",
        min_value=0.0,
        value=3000.0,
        step=500.0,
        help="Annual electricity demand of household in Scenario 1 (e.g. small / low-usage home).",
    )
    load2 = st.number_input(
        "Scenario 2 load (kWh/yr)",
        min_value=0.0,
        value=10000.0,
        step=500.0,
        help="Annual electricity demand of household in Scenario 2 (e.g. larger / high-usage home).",
    )
    sc_ratio1 = st.slider(
        "Scenario 1 self-consumption (no battery)",
        min_value=0.0,
        max_value=1.0,
        value=0.8,
        step=0.05,
        help=(
            "Share of Scenario 1 load that is directly covered by PV without a battery. "
            "High value means PV >> load and mid-day PV already meets most consumption."
        ),
    )
    sc_ratio2 = st.slider(
        "Scenario 2 self-consumption (no battery)",
        min_value=0.0,
        max_value=1.0,
        value=0.3,
        step=0.05,
        help=(
            "Share of Scenario 2 load that is directly covered by PV without a battery. "
            "Lower value means more grid import and more potential benefit from a battery."
        ),
    )

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Tip: play with load, PV size, DA spread, and battery size to see when DA optimisation adds value."
    )

    # ---- Compute once ----
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

    # ---- Tabs ----
    tab_results, tab_params, tab_readme = st.tabs(
        ["🧮 Results", "📊 Parameter definitions", "📘 Model & optimisation logic"]
    )

    # ========== TAB 1: RESULTS ==========
    with tab_results:
        st.header("Results")

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

        st.subheader("Detailed energy and cost table")
        st.caption(
            "Positive 'Net annual cost' means you pay money overall. "
            "Negative values mean you earn more from EEG than you pay for grid import."
        )
        st.dataframe(df_display, use_container_width=True)

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
                    "Savings vs no battery (non-optimised) (€)": cost_no_batt
                    - cost_nonopt,
                    "Savings vs no battery (DA-optimised) (€)": cost_no_batt
                    - cost_opt,
                    "Extra savings from optimisation (€)": cost_nonopt - cost_opt,
                }
            )

        df_summary = pd.DataFrame(summary_rows)
        df_summary_rounded = df_summary.copy()
        for c in df_summary_rounded.columns:
            if c != "Scenario":
                df_summary_rounded[c] = df_summary_rounded[c].round(2)

        st.subheader("Summary: savings from battery and optimisation")
        st.dataframe(df_summary_rounded, use_container_width=True)

        st.subheader("Net annual cost comparison (lower is better)")
        st.bar_chart(cost_summary)

        with st.expander("How to read these results"):
            st.markdown(
                """
- **Compare rows within the same Scenario:**
  - *No battery* is your reference.
  - *Battery – non-optimised* shows what happens if you only increase self-consumption with simple control.
  - *Battery – DA-optimised* adds extra value from reacting to day-ahead price spreads.
- **'Savings vs no battery'** shows how much better the battery configurations are compared to not having a battery.
- **'Extra savings from optimisation'** is the incremental gain from smarter control, given that the battery is already installed.
"""
            )

    # ========== TAB 2: PARAMETERS ==========
    with tab_params:
        st.header("Parameter definitions & impact")

        st.markdown(
            """
### PV & prices

- **PV size (kWp)**  
  Installed peak capacity of your PV system. Higher kWp → more annual PV generation.

- **PV yield (kWh/kWp·year)**  
  Annual production per kWp. Total PV generation = kWp × yield.  
  Depends on location, tilt, orientation, shading.

- **Grid price (€/kWh)**  
  What you pay per kWh imported from the grid.  
  Higher grid price makes **self-consumption and the battery more valuable**.

- **Feed-in tariff (€/kWh)**  
  EEG remuneration for exporting PV to the grid.  
  The value of self-consumption is roughly: `grid price − feed-in tariff`.

---

### Battery

- **Battery capacity (kWh)**  
  Usable energy capacity. Larger batteries can shift more energy per day, up to the limit set by your load and PV.

- **Round-trip efficiency (%)**  
  Fraction of energy that is recovered after charging and discharging.  
  Example: 93% means 1000 kWh charged → 930 kWh discharged.  
  Lower efficiency reduces the economic benefit of each shifted kWh.

- **Cycles per day**  
  Average number of full cycles per day.  
  1 cycle/day = charging from 0 → 100% and discharging back to 0% once per day on average.  
  More cycles per day increase throughput and therefore potential arbitrage value.

---

### DA (day-ahead) market

- **Average DA daily spread (€/kWh)**  
  Typical difference between cheap and expensive hours in the day-ahead market.  
  Larger spread = more value from charging in cheap hours and discharging in expensive hours.

- **Optimised capture fraction**  
  How much of the DA spread a smart optimiser can capture.  
  1.0 = perfect timing; 0.7 = captures 70% of the theoretical spread.

- **Non-optimised capture fraction**  
  How much of the DA spread a simple / rule-based controller captures accidentally.  
  Higher value means the baseline is already good, so **the extra benefit of optimisation becomes smaller**.

---

### Loads & baseline self-consumption

- **Scenario 1 / 2 load (kWh/yr)**  
  Annual electricity demand of two different households, e.g.:
  - Scenario 1: 3,000 kWh (small household),
  - Scenario 2: 10,000 kWh (larger household).

- **Self-consumption ratio without battery**  
  Fraction of the load that PV covers directly (without a battery).  
  - High ratio → PV already meets a lot of consumption → less remaining potential for the battery.  
  - Low ratio → more grid import → more potential benefit from adding a battery.
"""
        )

    # ========== TAB 3: MODEL & LOGIC ==========
    with tab_readme:
        st.header("Model & optimisation logic (in-app README)")

        st.markdown(
            """
### 1. High-level idea

This tool compares three configurations for each scenario:

1. **No battery**  
2. **Battery – non-optimised control**  
3. **Battery – DA-optimised control**

All three share the same PV system and prices.  
The battery is assumed to be **unidirectional** with respect to the grid:  
it can charge from PV and supply the house, but **does not export energy into the grid**.

---

### 2. Energy flow assumptions

For each scenario:

1. **PV generation**  
   - Annual PV generation = `PV size (kWp) × PV yield (kWh/kWp·year)`.

2. **No battery case**  
   - We assume a fixed **self-consumption ratio without battery**.  
   - Direct PV → load = `min(load × sc_ratio_no_batt, PV generation)`.  
   - PV export = `PV generation − direct PV → load`.  
   - Grid import = `load − direct PV → load`, limited to ≥ 0.

3. **Battery case**  
   - The battery can only increase **self-consumption**, i.e. take PV that would otherwise be exported and shift it to other hours where there is remaining load.
   - Maximum **theoretical** usable battery throughput per year:  
     `battery_capacity × efficiency × cycles_per_day × 365`.
   - But the **actual** usable throughput is limited by the remaining load not already covered by direct PV:  
     `max_extra_self_consumption = load − direct PV → load`  
     `usable_throughput = min(theoretical_throughput, max_extra_self_consumption)`.

   - The corresponding PV energy required to charge the battery is:  
     `PV → battery = usable_throughput / efficiency`.

   - New self-consumption:  
     `total PV self-consumption = direct PV → load + usable_throughput`.

   - PV export shrinks by the PV that goes into the battery.  
   - Grid import shrinks by the usable throughput (as long as there is remaining load).

4. **Unidirectional constraint**  
   - The model assumes **no battery → grid export**.  
   - All exported energy is treated as coming directly from PV, which keeps EEG accounting simple.

---

### 3. Cost calculation

For each configuration:

- **Grid cost (€)**  
  `grid_import × grid_price`.

- **EEG revenue (€)**  
  `PV_export × feed-in_tariff`.

- **Net annual cost (€)**  
  `grid cost − EEG revenue`.

Positive values = you pay money overall.  
Negative values = you earn more from EEG than you pay for grid import.

---

### 4. Day-ahead optimisation logic

We use a **simplified, annualised view** of DA optimisation:

1. **DA spread**  
   - `da_spread` represents the typical difference between cheap and expensive hours (€/kWh).

2. **Capture fractions**  
   - Optimised control captures a fraction of this:  
     `spread_opt = da_spread × opt_capture`.
   - Non-optimised control captures a smaller fraction:  
     `spread_non = da_spread × nonopt_capture`.

3. **Energy available for arbitrage**  
   - We approximate that only the **battery throughput that replaces grid import** can be used for grid arbitrage.  
   - If grid import without a battery is zero, arbitrage is set to zero (there is nothing to arbitrage).

4. **Arbitrage value**  
   - `arbitrage_non = arbitrage_energy × spread_non`.  
   - `arbitrage_opt = arbitrage_energy × spread_opt`.

5. **Net cost with arbitrage**  
   - Base battery cost (self-consumption only): `net_cost_batt_base`.  
   - Non-optimised: `net_cost_batt_nonopt = net_cost_batt_base − arbitrage_non`.  
   - Optimised: `net_cost_batt_opt = net_cost_batt_base − arbitrage_opt`.

The **extra value of optimisation** is simply the difference between these two battery cases.

---

### 5. How to interpret the results

- The **main value** of the battery (especially in Germany with EEG) usually comes from:
  - Increasing **self-consumption**, avoiding paying the grid price,
  - Instead of exporting for a lower feed-in tariff.

- **Day-ahead optimisation** adds **extra value on top** of this by:
  - Shifting battery charging/discharging within the day to exploit price spreads.

- In **high-load scenarios** (e.g. 10,000 kWh/yr), the battery can typically cycle close to once per day and DA optimisation can have a noticeable impact.

- In **low-load scenarios** with large PV (e.g. 3,000 kWh/yr and 9.5 kWp), PV + battery can already cover almost all load, so:
  - Grid import becomes very small or zero,
  - The potential for DA arbitrage is limited,
  - The extra value of optimisation is much smaller.

This README is intentionally high-level. You can use the parameter tab and the sidebar tooltips to explain the details to end-users and tweak the assumptions for your specific project or customer.
"""
        )


if __name__ == "__main__":
    main()
