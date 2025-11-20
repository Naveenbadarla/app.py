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

