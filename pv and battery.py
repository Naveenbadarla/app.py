import streamlit as st
import pandas as pd


# =====================================================================
#               CORE CALCULATION LOGIC (SINGLE SCENARIO)
# =====================================================================

def compute_scenario(
    load_kwh: float,
    pv_kwp: float,
    pv_yield: float,
    grid_price: float,
    fit_price: float,
    batt_capacity: float,
    batt_efficiency: float,
    cycles_per_day: float,
    sc_ratio_no_batt: float,
    da_spread: float,
    opt_capture: float,
    nonopt_capture: float,
):
    """
    Computes yearly energy flows and costs for a single household load
    under three configurations:
      1. No battery
      2. Battery – non-optimised
      3. Battery – DA-optimised
    """

    pv_gen = pv_kwp * pv_yield

    # ----------------------------------------------------------
    # 1. NO BATTERY CASE
    # ----------------------------------------------------------
    pv_direct_sc = min(load_kwh * sc_ratio_no_batt, pv_gen)
    pv_export_no_batt = max(0.0, pv_gen - pv_direct_sc)
    grid_import_no_batt = max(0.0, load_kwh - pv_direct_sc)

    cost_no_batt = grid_import_no_batt * grid_price
    revenue_no_batt = pv_export_no_batt * fit_price
    net_no_batt = cost_no_batt - revenue_no_batt

    # ----------------------------------------------------------
    # 2. BATTERY — NON OPTIMISED
    # ----------------------------------------------------------
    batt_theoretical = batt_capacity * batt_efficiency * cycles_per_day * 365
    remaining_load = max(0.0, load_kwh - pv_direct_sc)
    batt_usable = min(batt_theoretical, remaining_load)

    pv_to_batt = batt_usable / batt_efficiency if batt_efficiency > 0 else 0
    pv_export_batt = max(0.0, pv_gen - pv_direct_sc - pv_to_batt)
    grid_import_batt = max(0.0, load_kwh - (pv_direct_sc + batt_usable))

    cost_batt_base = grid_import_batt * grid_price
    revenue_batt = pv_export_batt * fit_price
    net_batt_base = cost_batt_base - revenue_batt

    # Arbitrage energy only makes sense if grid import would have existed
    arbitrage_energy = batt_usable if grid_import_no_batt > 0 else 0

    arbitrage_non = arbitrage_energy * da_spread * nonopt_capture

    net_batt_nonopt = net_batt_base - arbitrage_non

    # ----------------------------------------------------------
    # 3. BATTERY — DA OPTIMISED
    # ----------------------------------------------------------
    arbitrage_opt = arbitrage_energy * da_spread * opt_capture
    net_batt_opt = net_batt_base - arbitrage_opt

    # ----------------------------------------------------------
    # TABLE RESULTS
    # ----------------------------------------------------------
    df = pd.DataFrame([
        {
            "Configuration": "No battery",
            "PV generation (kWh)": pv_gen,
            "PV self-consumption (kWh)": pv_direct_sc,
            "Battery → load (kWh)": 0.0,
            "PV export (kWh)": pv_export_no_batt,
            "Grid import (kWh)": grid_import_no_batt,
            "Grid cost (€)": cost_no_batt,
            "EEG revenue (€)": revenue_no_batt,
            "DA arbitrage (€)": 0.0,
            "Net annual cost (€)": net_no_batt,
        },
        {
            "Configuration": "Battery – non-optimised",
            "PV generation (kWh)": pv_gen,
            "PV self-consumption (kWh)": pv_direct_sc,
            "Battery → load (kWh)": batt_usable,
            "PV export (kWh)": pv_export_batt,
            "Grid import (kWh)": grid_import_batt,
            "Grid cost (€)": cost_batt_base,
            "EEG revenue (€)": revenue_batt,
            "DA arbitrage (€)": arbitrage_non,
            "Net annual cost (€)": net_batt_nonopt,
        },
        {
            "Configuration": "Battery – DA-optimised",
            "PV generation (kWh)": pv_gen,
            "PV self-consumption (kWh)": pv_direct_sc,
            "Battery → load (kWh)": batt_usable,
            "PV export (kWh)": pv_export_batt,
            "Grid import (kWh)": grid_import_batt,
            "Grid cost (€)": cost_batt_base,
            "EEG revenue (€)": revenue_batt,
            "DA arbitrage (€)": arbitrage_opt,
            "Net annual cost (€)": net_batt_opt,
        },
    ])
    return df


# =====================================================================
#                           STREAMLIT UI
# =====================================================================

def main():
    st.set_page_config(page_title="PV + Battery + DA Optimisation", layout="wide")

    st.title("⚡ PV + Battery + Day-Ahead Optimisation (Germany / EEG)")
    st.markdown(
        """
Explore how PV, a battery, and smart day-ahead optimisation change your **annual energy cost**.
Choose your system parameters on the left and interpret results through the results tabs.
        """
    )

    # ----------------------------------------------------------
    # SIDEBAR — INPUT SECTION
    # ----------------------------------------------------------
    st.sidebar.header("🔧 System Setup")

    with st.sidebar.expander("💡 Quick explanation", expanded=True):
        st.markdown("""
### Energy Flow Mental Model
    ☀️ PV
      │
      ├──→ 🏠 Home (direct self-consumption)
      │
      ├──→ 🔋 Battery → 🏠 Home (shifted self-consumption)
      │
      └──→ 🔌 Grid (EEG export)

### What we compare
1️⃣ **No battery**  
2️⃣ **Battery – simple control** (increase self-consumption)  
3️⃣ **Battery – smart DA-optimised control**  
   Uses cheap hours to charge and expensive hours to discharge.

### What “Net Annual Cost” means
- **Positive → you pay money overall**  
- **Negative → your PV exports earn you more than you pay the grid**
""")

    load_kwh = st.sidebar.number_input(
        "Annual household load (kWh)", min_value=0.0, value=3000.0, step=500.0
    )

    pv_kwp = st.sidebar.number_input("PV size (kWp)", 0.0, 20.0, 9.5, 0.1)
    pv_yield = st.sidebar.number_input("PV yield (kWh/kWp·yr)", 100.0, 1500.0, 950.0, 10.0)

    grid_price = st.sidebar.number_input("Grid price (€/kWh)", 0.0, 1.0, 0.39, 0.01)
    fit_price = st.sidebar.number_input("Feed-in tariff (€/kWh)", 0.0, 1.0, 0.08, 0.01)

    batt_capacity = st.sidebar.number_input("Battery capacity (kWh)", 0.0, 40.0, 8.8, 0.1)
    batt_eff = st.sidebar.slider("Battery efficiency (%)", 60, 100, 93) / 100
    cycles = st.sidebar.number_input("Cycles per day", 0.0, 2.0, 1.0, 0.1)

    sc_ratio = st.sidebar.slider(
        "Self-consumption ratio (no battery)",
        0.0, 1.0, 0.8, 0.05,
        help="How much of your consumption happens during PV production hours."
    )

    da_spread = st.sidebar.number_input("DA price spread (€/kWh)", 0.0, 0.5, 0.112, 0.01)
    opt_cap = st.sidebar.slider("Optimiser spread capture", 0.0, 1.0, 0.7)
    nonopt_cap = st.sidebar.slider("Non-optimised capture", 0.0, 1.0, 0.35)

    # ----------------------------------------------------------
    # RUN MODEL
    # ----------------------------------------------------------
    df = compute_scenario(
        load_kwh, pv_kwp, pv_yield, grid_price, fit_price,
        batt_capacity, batt_eff, cycles, sc_ratio,
        da_spread, opt_cap, nonopt_cap,
    )

    df_display = df.copy()
    for col in df_display.columns:
        if col != "Configuration":
            df_display[col] = df_display[col].round(2)

    # ==========================================================
    # TABS
    # ==========================================================

    tab_results, tab_params, tab_logic, tab_read = st.tabs([
        "🧮 Results",
        "📊 Parameter Guide",
        "⚙️ Optimisation Logic",
        "🧭 How to Read Results",
    ])

    # ----------------------------------------------------------
    # TAB 1 — RESULTS
    # ----------------------------------------------------------
    with tab_results:
        st.header("🧮 Results")

        st.dataframe(df_display, use_container_width=True)

        # Extract costs
        costs = df.set_index("Configuration")["Net annual cost (€)"]
        nb = float(costs["No battery"])
        b_non = float(costs["Battery – non-optimised"])
        b_opt = float(costs["Battery – DA-optimised"])

        col1, col2, col3 = st.columns(3)
        col1.metric("No battery", f"{nb:,.0f} €")
        col2.metric("Battery – non-opt", f"{b_non:,.0f} €", f"{nb - b_non:,.0f} € saved")
        col3.metric("Battery – optimised", f"{b_opt:,.0f} €", f"{b_non - b_opt:,.0f} € extra saved")

        st.subheader("📉 Visual comparison")
        st.bar_chart(df.set_index("Configuration")["Net annual cost (€)"])

        with st.expander("📘 Short explanation"):
            st.markdown(
                """
### What these numbers mean:

- **Positive net cost** → you pay money overall.  
- **Negative net cost** → your PV exports earn you *more* than your grid import costs.  
- **Battery (non-opt)** shows how much you save simply by increasing PV self-consumption.  
- **Battery (DA-optimised)** shows the *extra* savings from reacting to daily price patterns.
                """
            )

    # ----------------------------------------------------------
    # TAB 2 — PARAMETER GUIDE
    # ----------------------------------------------------------
    with tab_params:
        st.header("📊 Parameter Guide")
        st.markdown("""
This tab explains every slider in simple language.

### Load
Higher load → more room for the battery to provide value.

### PV Size & Yield
More PV → more self-consumption & EEG revenue.

### Battery
- Bigger battery = more energy shifting.
- Higher efficiency = less energy lost.
- More cycles/day = more annual throughput (if useful).

### Day-ahead Spread
Bigger spread → more money from reacting to cheap/expensive hours.
        """)

    # ----------------------------------------------------------
    # TAB 3 — OPTIMISATION LOGIC
    # ----------------------------------------------------------
    with tab_logic:
        st.header("⚙️ Optimisation Logic")
        st.markdown("""
The optimiser works like this:

1. Identify **cheap hours** and **expensive hours** from the DA price curve.  
2. Charge battery more in cheap hours, less in expensive hours.  
3. Discharge battery in expensive hours to avoid grid import.  
4. The amount it *can* shift is limited by:
   - Your battery size  
   - Number of cycles/day  
   - Remaining household load  
   - PV availability

We model this yearly using a simplified but robust approach.
        """)

    # ----------------------------------------------------------
    # TAB 4 — HOW TO READ RESULTS
    # ----------------------------------------------------------
    with tab_read:
        st.header("🧭 How to Read the Results")

        st.markdown("""
## 1️⃣ What “Net Annual Cost” means

- **Positive number = you pay money overall.**
- **Negative number = your PV exports earn more than your grid costs.**

---

## 2️⃣ How to understand the three configurations

### 🏠 No battery
You use PV instantly, export the rest, and buy from grid when needed.

### 🔋 Battery – Non-optimised
Battery increases self-consumption → large savings.

### 🤖 Battery – DA-optimised
Same battery, but smarter timing → extra savings.

---

## 3️⃣ What to look for

### ✔ Battery vs No Battery  
This shows whether having a battery makes sense **at all**.

### ✔ Optimised vs Non-Optimised  
This shows the **extra value of smart control**  
(often smaller than the battery’s main effect).

---

## 4️⃣ Example interpretation

If you see:

| Config | Net cost |
|--------|----------|
| No battery | +400 € |
| Battery – non-opt | –200 € |
| Battery – opt | –260 € |

Interpretation:

- You pay 400 €/yr without battery  
- You **earn 200 €/yr** with a simple battery  
- You **earn 260 €/yr** with smart optimisation  
- Optimisation adds **60 €/yr** extra

---

## 5️⃣ Why negative values happen

Large PV + small load → most energy exported at EEG → revenue > grid cost → **negative net cost**.

That is normal and correct.
        """)


if __name__ == "__main__":
    main()


