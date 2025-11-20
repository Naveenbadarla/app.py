import streamlit as st
import pandas as pd


# ---------- Core calculation logic (single scenario) ----------

def compute_scenario(
    load_kwh: float,
    pv_kwp: float,
    pv_yield_kwh_per_kwp: float,
    grid_price: float,
    fit_price: float,
    batt_capacity_kwh: float,
    batt_efficiency: float,
    cycles_per_day: float,
    sc_ratio_no_batt: float,
    da_spread: float,
    opt_capture: float,
    nonopt_capture: float,
) -> pd.DataFrame:
    """
    Compute yearly energy flows and costs for one household load:
      - No battery
      - Battery, non-optimised
      - Battery, DA-optimised
    """
    pv_gen = pv_kwp * pv_yield_kwh_per_kwp
    results = []

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
    # Simplified assumption: arbitrage is only relevant if there is grid import
    # in the "no battery" case – otherwise there's nothing to shift on the tariff.
    arbitrage_energy = e_shift if grid_import_no_batt > 0 else 0.0

    spread_opt = da_spread * opt_capture
    spread_non = da_spread * nonopt_capture

    arbitrage_non = arbitrage_energy * spread_non
    arbitrage_opt = arbitrage_energy * spread_opt

    net_cost_batt_nonopt = net_cost_batt_base - arbitrage_non
    net_cost_batt_opt = net_cost_batt_base - arbitrage_opt

    # --- Collect rows ---
    results.append(
        {
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
        }
    )
    results.append(
        {
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
        }
    )
    results.append(
        {
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
        }
    )

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
This app shows **how much money a household can save per year** with:

- A PV system (with EEG feed-in),
- A battery that only supplies the house (no battery → grid export),
- And **smart vs simple** battery control using day-ahead prices.

You can change the load, PV size and battery size and see immediately:
**What changes in the bill?**
"""
    )

    # ---- Sidebar ----
    st.sidebar.header("Model setup")

    with st.sidebar.expander("💡 Quick explanation (read this first)", expanded=True):
        st.markdown(
            """
Think of the energy flow like this:

- ☀️ **PV** produces electricity.
- 🏠 Your **home** uses some of it immediately (self-consumption).
- 🔋 Your **battery** can store extra PV and use it later for the home.
- 🔌 **Grid** delivers any remaining energy you still need,  
  and buys your surplus PV via EEG.

What the app compares:
1. **No battery** → PV + grid only  
2. **Battery – non-optimised** → battery increases self-consumption, but control is simple  
3. **Battery – DA-optimised** → battery also tries to use **cheap hours to charge** and **expensive hours to discharge**, based on day-ahead prices

The main question:
> *How much extra does smart optimisation save on top of just having a battery?*
"""
        )

    # ---- Sidebar inputs ----
    st.sidebar.subheader("Household & PV")

    load_kwh = st.number_input(
        "Household load (kWh/year)",
        min_value=0.0,
        value=3000.0,
        step=500.0,
        help="Total electricity use of the household per year.",
    )

    col_pv1, col_pv2 = st.sidebar.columns(2)
    with col_pv1:
        pv_kwp = st.number_input(
            "PV size (kWp)",
            min_value=0.0,
            value=9.5,
            step=0.1,
            help="Installed peak PV power. Higher = more PV generation.",
        )
    with col_pv2:
        pv_yield = st.number_input(
            "PV yield (kWh/kWp·year)",
            min_value=400.0,
            value=950.0,
            step=10.0,
            help="Yearly PV output per kWp. Depends on location & orientation.",
        )

    st.sidebar.subheader("Prices (Germany-style)")
    grid_price = st.number_input(
        "Grid price (€/kWh)",
        min_value=0.0,
        value=0.39,
        step=0.01,
        format="%.3f",
        help="What you pay per kWh from the grid.",
    )
    fit_price = st.number_input(
        "Feed-in tariff / EEG (€/kWh)",
        min_value=0.0,
        value=0.08,
        step=0.005,
        format="%.3f",
        help="What you get per kWh when exporting PV to the grid.",
    )

    st.sidebar.subheader("Battery")
    batt_capacity = st.number_input(
        "Battery capacity (kWh)",
        min_value=0.0,
        value=8.8,
        step=0.1,
        help="Usable energy capacity of the battery.",
    )
    batt_efficiency = st.slider(
        "Round-trip efficiency (%)",
        min_value=50,
        max_value=100,
        value=93,
        step=1,
        help="Charge + discharge efficiency. 93% means 1000 kWh in → 930 kWh out.",
    ) / 100.0
    cycles_per_day = st.number_input(
        "Cycles per day",
        min_value=0.0,
        value=1.0,
        step=0.1,
        help="How often, on average, the full battery capacity is cycled each day.",
    )

    st.sidebar.subheader("Day-ahead (DA) market behaviour")
    da_spread = st.number_input(
        "Average DA daily spread (€/kWh)",
        min_value=0.0,
        value=0.112,
        step=0.01,
        format="%.3f",
        help="Typical difference between cheap and expensive hours in DA prices.",
    )
    col_da1, col_da2 = st.sidebar.columns(2)
    with col_da1:
        opt_capture = st.slider(
            "Optimised capture fraction",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.05,
            help="How much of the DA spread smart control actually captures.",
        )
    with col_da2:
        nonopt_capture = st.slider(
            "Non-optimised capture fraction",
            min_value=0.0,
            max_value=1.0,
            value=0.35,
            step=0.05,
            help="How much of the DA spread simple control captures by accident.",
        )

    st.sidebar.subheader("Baseline self-consumption (no battery)")
    sc_ratio = st.slider(
        "Self-consumption ratio without battery",
        min_value=0.0,
        max_value=1.0,
        value=0.8,
        step=0.05,
        help=(
            "Share of your load directly covered by PV without a battery. "
            "High value = PV already covers a lot of your use at the right time."
        ),
    )

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Tip: slide the **load** up and down. At low load and big PV, optimisation adds very little. "
        "At high load and moderate PV, optimisation can add noticeable extra savings."
    )

    # ---- Compute scenario ----
    df = compute_scenario(
        load_kwh=load_kwh,
        pv_kwp=pv_kwp,
        pv_yield_kwh_per_kwp=pv_yield,
        grid_price=grid_price,
        fit_price=fit_price,
        batt_capacity_kwh=batt_capacity,
        batt_efficiency=batt_efficiency,
        cycles_per_day=cycles_per_day,
        sc_ratio_no_batt=sc_ratio,
        da_spread=da_spread,
        opt_capture=opt_capture,
        nonopt_capture=nonopt_capture,
    )

    # Tabs
    tab_results, tab_params, tab_readme = st.tabs(
        ["🧮 Results", "📊 Parameter guide", "📘 Model & optimisation logic"]
    )

    # ========== TAB 1: RESULTS ==========
    with tab_results:
        st.header("Results for this household")

        # Round for display
        df_display = df.copy()
        numeric_cols = [c for c in df_display.columns if c != "Configuration"]
        df_display[numeric_cols] = df_display[numeric_cols].round(2)

        # Extract costs for metrics
        costs = df.set_index("Configuration")["Net annual cost (€)"]
        cost_no_batt = float(costs["No battery"])
        cost_nonopt = float(costs["Battery – non-optimised"])
        cost_opt = float(costs["Battery – DA-optimised"])

        savings_nonopt = cost_no_batt - cost_nonopt
        savings_opt = cost_no_batt - cost_opt
        extra_opt = cost_nonopt - cost_opt

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Net annual cost – No battery", f"{cost_no_batt:,.0f} €")
        col_m2.metric("Net annual cost – Battery (non-optimised)", f"{cost_nonopt:,.0f} €",
                      f"{savings_nonopt:,.0f} € vs no battery")
        col_m3.metric("Net annual cost – Battery (DA-optimised)", f"{cost_opt:,.0f} €",
                      f"{extra_opt:,.0f} € extra vs non-optimised")

        st.subheader("Energy flow summary (per year)")
        st.caption("All values are annual. PV → Battery → Home → Grid, under different controls.")
        st.dataframe(df_display, use_container_width=True)

        st.subheader("Net annual cost per configuration (lower is better)")
        cost_summary = df.set_index("Configuration")[["Net annual cost (€)"]]
        st.bar_chart(cost_summary)

        with st.expander("📖 How to read these results (simple version)", expanded=True):
            st.markdown(
                f"""
1. **Look at the three net annual costs at the top.**  
   - *No battery* = your reference case.  
   - *Battery – non-optimised* = same hardware, but simple control.  
   - *Battery – DA-optimised* = same hardware, smarter control.

2. **Battery vs. no battery**  
   - The value **“X € vs no battery”** under *Battery – non-optimised* tells you:  
     > “How much money does the battery save per year, **even without smart optimisation**?”

3. **Extra value from optimisation**  
   - The value **“extra vs non-optimised”** under *Battery – DA-optimised* tells you:  
     > “If I already have a battery, how much more can I save by using smarter DA control?”

4. **Sign of the numbers**  
   - Positive net cost = you pay money overall.  
   - Negative net cost = your EEG income is larger than your grid payments (you’re a net earner).

5. **Play with the sliders**  
   - Increase **load** → battery and optimisation usually become more valuable.  
   - Increase **PV size** with small load → PV + battery can already cover almost everything, so DA optimisation adds very little.
"""
            )

        with st.expander("🔍 Visual mental model of the energy flow"):
            st.markdown(
                """
**Think of three layers:**

1. **Without battery**  
   - Daytime: PV first covers your home, the rest goes to the grid (EEG).  
   - Night: Everything comes from the grid.

2. **With battery (non-optimised)**  
   - Excess PV charges the battery instead of going straight to the grid.  
   - Later (evening/night), the battery covers part of your load → less grid import.

3. **With DA-optimised battery**  
   - Same as above, **plus**:  
     - The timing of charge/discharge follows **cheap vs expensive hours** as much as possible.  
     - This squeezes a bit more value out of the same battery.
"""
            )

    # ========== TAB 2: PARAMETER GUIDE ==========
    with tab_params:
        st.header("Parameter guide – what each slider means")

        st.markdown(
            """
### Household & PV

- **Household load (kWh/year)**  
  Total electricity use of the home.  
  Higher load → more potential for the battery to do useful work.

- **PV size (kWp)**  
  Installed peak power of the PV system.  
  More kWp → more PV production → more self-consumption but also more export.

- **PV yield (kWh/kWp·year)**  
  Annual PV output per kWp.  
  Total PV generation = *kWp × yield*.

---

### Prices

- **Grid price (€/kWh)**  
  What you pay for each kWh you buy from the grid.  
  The higher this is, the more valuable self-consumption becomes.

- **Feed-in tariff / EEG (€/kWh)**  
  What you earn for each kWh of PV exported to the grid.  
  Roughly speaking, **value of self-consumption ≈ grid price − EEG price**.

---

### Battery

- **Battery capacity (kWh)**  
  How much energy the battery can store.  
  Bigger battery → can shift more energy between times of day.

- **Round-trip efficiency (%)**  
  Efficiency of charge + discharge.  
  93% means: 1000 kWh into the battery → 930 kWh back out.  
  Lower efficiency reduces the financial benefit per shifted kWh.

- **Cycles per day**  
  How often the battery is fully charged and discharged per day on average.  
  More cycles → more annual throughput → more potential savings (if the energy is actually useful).

---

### Day-ahead market

- **Average DA daily spread (€/kWh)**  
  Typical price gap between cheapest and most expensive hours in a day.  
  Bigger spread = more money to be made by shifting energy.

- **Optimised capture fraction**  
  How much of that spread smart control can really capture (0–1).  
  1.0 would be a perfect optimiser; 0.7 is realistic and still ambitious.

- **Non-optimised capture fraction**  
  How much of that spread a simple or dumb control captures “by accident”.  
  If this is already high, extra value from optimisation will be small.

---

### Self-consumption ratio (no battery)

- **Self-consumption ratio without battery**  
  Approximate share of your load directly covered by PV in real time **without** a battery.  
  - High value (e.g. 0.8 with small load & big PV) → battery has less to improve.  
  - Lower value (e.g. 0.3 with big load & modest PV) → battery (and optimisation) can do more.
"""
        )

    # ========== TAB 3: MODEL & LOGIC ==========
    with tab_readme:
        st.header("Model & optimisation logic (README)")

        st.markdown(
            """
### 1. What the model does

For the chosen household and system, the app calculates – on a **yearly** basis:

1. How much of the load is covered directly by PV.  
2. How much PV is exported to the grid (EEG).  
3. How much the battery can increase self-consumption.  
4. How much additional value comes from reacting to **day-ahead prices**.

It then converts all of this into **annual euros**:
- Grid cost (what you pay),
- EEG revenue (what you earn),
- Net annual cost (grid cost – EEG revenue).

---

### 2. Energy flow assumptions

1. **PV generation**  
   - Annual PV generation = `PV size × PV yield`.

2. **No battery**  
   - A fixed share of the load is assumed to be directly covered by PV  
     → `load × self-consumption ratio (no battery)`.  
   - The rest of the load comes from the grid.  
   - Any PV that isn’t used instantly is exported to the grid (EEG).

3. **With battery**  
   - The battery can only be charged from **PV** and only supplies the **house**.  
     (No export from battery to grid – “unidirectional” battery.)  
   - The maximum theoretical energy the battery can shift per year is:  
     `capacity × efficiency × cycles_per_day × 365`.  
   - But it is **limited** by how much load is left *after* direct PV self-consumption.  
   - The model takes the minimum of those two values.

4. **PV to battery**  
   - To deliver `usable_throughput` to the house, the battery needs  
     `PV → battery = usable_throughput / efficiency`.  
   - That PV is taken away from export and turned into extra self-consumption.

5. **New energy balances**  
   - More PV is used in the home (via the battery).  
   - Less PV is exported.  
   - Less energy is imported from the grid.

---

### 3. Cost calculation

For each configuration:

- **Grid cost (€)** = `grid_import × grid_price`  
- **EEG revenue (€)** = `PV_export × feed-in tariff`  
- **Net annual cost (€)** = `grid cost − EEG revenue`

A **negative** net annual cost means you earn more from feed-in than you pay for grid energy.

---

### 4. Day-ahead optimisation

This is simplified but captures the key idea:

1. The **day-ahead spread** (€/kWh) says how big the price difference is between cheap and expensive hours on average.

2. Not all of that spread is usable in practice.  
   - Smart control captures a share → `opt_capture`.  
   - Simple control captures a smaller share → `nonopt_capture`.

3. Only battery throughput that **replaces grid import** can be used for grid arbitrage.  
   - If, without a battery, you already import almost nothing from the grid, there’s nothing to arbitrage.

4. Annual arbitrage value is then:  
   - Non-optimised: `arbitrage_energy × (DA spread × nonopt_capture)`  
   - Optimised: `arbitrage_energy × (DA spread × opt_capture)`

5. This arbitrage value is subtracted from the base battery net cost to get the final net cost for each control strategy.

---

### 5. How to use this tool in practice

- Start with realistic **prices** and **PV size** for your country.  
- Set your **annual load** and a plausible **self-consumption ratio without battery**.  
- Then:
  1. See if a **battery at all** makes economic sense compared to no battery.  
  2. Look at the **extra** value from DA optimisation.  
  3. Change load / PV / battery size to understand under which conditions optimisation becomes significant.

This is a **planning / intuition tool**, not a detailed hourly simulation – but it gives a clear picture of:
- Where the money comes from (self-consumption vs EEG),
- And how much extra smart control can realistically add on top.
"""
        )


if __name__ == "__main__":
    main()

