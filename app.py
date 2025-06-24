import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import time
import stpyvista as stpv
import os
from helpers.isa import get_isa_rho

from engine_simulator import EngineSimulator, FUEL_PROPERTIES
from engine_visualizer_3d import EngineVisualizer3D

# --- UI Helper Functions ---
def make_gauge(label, value, max_value, unit, color):
    """Creates a custom HTML/CSS gauge."""
    # Prevent division by zero
    if max_value == 0:
        normalized_value = 0.0
    else:
        normalized_value = min(value / max_value, 1.0)
    
    gauge_html = f"""
    <div style="margin-bottom: 1rem;">
        <div style="font-size: 1rem; font-weight: bold;">{label}</div>
        <div style="position: relative; height: 25px; background-color: #eee; border-radius: 5px; overflow: hidden;">
            <div style="position: absolute; height: 100%; width: {normalized_value * 100}%; background-color: {color}; border-radius: 5px;"></div>
            <div style="position: absolute; width: 100%; text-align: center; color: #000; font-weight: bold; line-height: 25px;">
                {value:.1f} {unit}
            </div>
        </div>
    </div>
    """
    return gauge_html

# --- App Configuration ---
st.set_page_config(
    page_title="Engine Performance Simulator",
    page_icon="⚙️",
    layout="wide",
)

# --- App Title and Description ---
st.title("🔧 Engine Performance Simulator")
st.write(
    "An interactive, production-grade application to compute and visualize the performance of internal combustion engines. "
    "Adjust the parameters in the sidebar to see how they affect engine performance in real-time."
)

# --- Sidebar for User Inputs ---
st.sidebar.header("Engine Configuration")

# Engine Geometry
st.sidebar.subheader("Geometry")
num_cylinders = st.sidebar.selectbox("Number of Cylinders", [2, 4, 6, 8, 12], index=1)
engine_config = st.sidebar.selectbox("Engine Configuration", ['Inline', 'V', 'Boxer'], index=0)
bore_mm = st.sidebar.slider("Bore (mm)", min_value=60.0, max_value=120.0, value=82.5, step=0.1)
stroke_mm = st.sidebar.slider("Stroke (mm)", min_value=60.0, max_value=120.0, value=92.8, step=0.1)
con_rod_mm = st.sidebar.slider("Connecting Rod (mm)", min_value=100.0, max_value=200.0, value=140.0, step=0.1)
compression_ratio = st.sidebar.slider("Compression Ratio", min_value=8.0, max_value=20.0, value=11.0, step=0.1)

v_angle_deg = 90
if engine_config == 'V':
    v_angle_deg = st.sidebar.slider("V-Angle (degrees)", min_value=45, max_value=120, value=90, step=1)

# Operating Conditions
st.sidebar.subheader("Operating Conditions")
rpm = st.sidebar.slider("Engine Speed (RPM)", min_value=1000, max_value=9000, value=2500, step=100)
rpm_redline = st.sidebar.slider("Engine Redline (RPM)", min_value=5000, max_value=12000, value=8500, step=100)

# Animation Controls
st.sidebar.subheader("Animation")
run_animation = st.sidebar.checkbox("Run Animation")
if 'crank_angle_deg' not in st.session_state:
    st.session_state.crank_angle_deg = 0

# Ensure crank_angle_deg is a scalar, not a list/tuple
if isinstance(st.session_state.crank_angle_deg, (list, tuple)):
    st.session_state.crank_angle_deg = st.session_state.crank_angle_deg[0]

if run_animation:
    crank_angle_deg = st.session_state.crank_angle_deg
    st.sidebar.slider("Crank Angle (deg)", min_value=0, max_value=720, value=int(crank_angle_deg), step=1, key='crank_angle_slider', disabled=True)
else:
    crank_angle_deg = st.sidebar.slider("Crank Angle (deg)", min_value=0, max_value=720, value=int(st.session_state.crank_angle_deg), step=1, key='crank_angle_slider')
    st.session_state.crank_angle_deg = crank_angle_deg

vehicle_speed_kph = st.sidebar.slider("Vehicle Speed (km/h)", min_value=0, max_value=300, value=100, step=5)

# --- Phase 2: Ambient, Boost, Throttle ---
st.sidebar.subheader("Ambient Conditions")
ambient_temp_c = st.sidebar.slider("Ambient Temp (°C)", -20, 50, 15, 1)
altitude_m = st.sidebar.slider("Altitude (m)", 0, 4000, 0, 50)
rho_air = get_isa_rho(altitude_m, ambient_temp_c)

st.sidebar.subheader("Intake Conditions")
boost_kpa = st.sidebar.slider("Boost Pressure (kPa)", 0.0, 200.0, 0.0, 5.0)
throttle_pct = st.sidebar.slider("Throttle", 0, 100, 100, 1)
manifold_pressure_ratio = 1.0 + (boost_kpa / 101.325)
throttle_scaler = throttle_pct / 100.0

# --- Fuel and Efficiency ---
st.sidebar.subheader("Fuel & Efficiency")

# When fuel type changes, update the AFR slider to its stoichiometric value
def update_afr():
    st.session_state.afr_slider = FUEL_PROPERTIES[st.session_state.fuel_selector]['stoich_afr']

fuel_type = st.sidebar.selectbox(
    "Fuel Type", 
    list(FUEL_PROPERTIES.keys()),
    key='fuel_selector',
    on_change=update_afr
)
afr = st.sidebar.slider(
    "Air-Fuel Ratio (AFR)", 
    min_value=8.0, 
    max_value=22.0, 
    value=FUEL_PROPERTIES[fuel_type]['stoich_afr'], 
    step=0.1,
    key='afr_slider'
)
bsfc_g_kwh = st.sidebar.slider("Base BSFC (g/kWh)", min_value=200.0, max_value=400.0, value=250.0, step=1.0)

# --- Comparison Engine Inputs ---
st.sidebar.header("Comparison Engine")
compare_enabled = st.sidebar.checkbox("Enable Comparison")
if compare_enabled:
    st.sidebar.subheader("Engine B Geometry")
    num_cylinders_b = st.sidebar.selectbox("Number of Cylinders (B)", [2, 4, 6, 8, 12], index=2, key='cyl_b')
    bore_mm_b = st.sidebar.slider("Bore (mm) (B)", min_value=60.0, max_value=120.0, value=86.0, step=0.1, key='bore_b')
    stroke_mm_b = st.sidebar.slider("Stroke (mm) (B)", min_value=60.0, max_value=120.0, value=86.0, step=0.1, key='stroke_b')
    compression_ratio_b = st.sidebar.slider("Compression Ratio (B)", min_value=8.0, max_value=20.0, value=10.5, step=0.1, key='cr_b')
    bsfc_g_kwh_b = st.sidebar.slider("BSFC (g/kWh) (B)", min_value=200.0, max_value=400.0, value=240.0, step=1.0, key='bsfc_b')
    rpm_redline_b = st.sidebar.slider("Redline (RPM) (B)", min_value=5000, max_value=12000, value=7000, step=100, key='redline_b')

# --- Simulation Execution ---
sim = EngineSimulator(
    num_cylinders=num_cylinders,
    bore_mm=bore_mm,
    stroke_mm=stroke_mm,
    compression_ratio=compression_ratio,
    rpm=rpm,
    bsfc_g_kwh=bsfc_g_kwh,
    afr=afr,
    fuel_type=fuel_type,
    rpm_redline=rpm_redline,
    rho_air=rho_air,
    manifold_pressure_ratio=manifold_pressure_ratio,
    throttle_scaler=throttle_scaler
)
results = sim.get_results()

# --- Main Panel for Outputs ---
st.header("Simulation Outputs")

# Create two columns for results and visualization
res_col, vis_col = st.columns([0.8, 1.2])

with res_col:
    st.subheader("Performance Metrics")
    # Key Metrics Display as gauges
    st.markdown(make_gauge("I Horsepower (IHP)", results['ihp'], 600, "HP", "#d62728"), unsafe_allow_html=True)
    st.markdown(make_gauge("Brake Horsepower", results['bhp'], 500, "HP", "#1f77b4"), unsafe_allow_html=True)
    st.markdown(make_gauge("Torque", results['torque_nm'], 600, "N·m", "#2ca02c"), unsafe_allow_html=True)
    st.markdown(make_gauge("BMEP", results['bmep_kpa'], 1500, "kPa", "#ff7f0e"), unsafe_allow_html=True)
    st.markdown(make_gauge("Brake Thermal Eff.", results['brake_thermal_efficiency_percent'], 50, "%", "#9467bd"), unsafe_allow_html=True)
    st.markdown(make_gauge("Mechanical Eff.", results['mechanical_efficiency_percent'], 100, "%", "#8c564b"), unsafe_allow_html=True)

    # Fuel Metrics in an expander
    with st.expander("Fuel & Air Flow Metrics"):
        fuel_flow_l_hr = results['fuel_flow_l_hr']
        if vehicle_speed_kph > 0 and fuel_flow_l_hr > 0:
            fuel_efficiency_kml = vehicle_speed_kph / fuel_flow_l_hr
        else:
            fuel_efficiency_kml = 0
        
        st.markdown(make_gauge("Fuel Efficiency", fuel_efficiency_kml, 25, "km/L", "#ffc107"), unsafe_allow_html=True)
        st.markdown(make_gauge("Fuel Flow", fuel_flow_l_hr, 50, "L/h", "#dc3545"), unsafe_allow_html=True)
    
    # Other details in an expander
    with st.expander("Show Detailed Engine Specs"):
        col1, col2 = st.columns(2)
        col1.metric("Indicated HP", f"{results['ihp']:.1f} HP")
        col2.metric("Displacement", f"{results['displacement_l']:.2f} L")
        col1.metric("Ideal Otto Efficiency", f"{results['thermal_efficiency_percent']:.1f}%")
        col2.metric("Volumetric Efficiency", f"{results['volumetric_efficiency_percent']:.1f}% @ {rpm} RPM")
        col1.metric("IMEP", f"{results['imep_kpa']:.0f} kPa")
        col2.metric("FMEP", f"{results['fmep_kpa']:.0f} kPa")
        col1.metric("BSFC", f"{results['bsfc_g_kwh']:.1f} g/kWh")

with vis_col:
    st.subheader("3D Engine Visualizer")
    visualizer = EngineVisualizer3D(
        bore_mm=bore_mm,
        stroke_mm=stroke_mm,
        con_rod_mm=con_rod_mm,
        num_cyl=num_cylinders,
        layout=engine_config,
        v_angle_deg=v_angle_deg
    )
    plotter = visualizer.build_scene(crank_deg=st.session_state.crank_angle_deg)
    stpv.stpyvista(plotter, key=f"vtk_plotter_{num_cylinders}_{engine_config}")


# --- Visualizations ---
st.header("Performance & Efficiency Analysis")

# Create two columns for the charts
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    # Power Comparison Bar Chart
    st.subheader("Power Breakdown")
    power_data = pd.DataFrame({
        'Type': ['Indicated HP', 'Brake HP'],
        'Horsepower': [results['ihp'], results['bhp']]
    })
    power_chart = alt.Chart(power_data).mark_bar().encode(
        x=alt.X('Horsepower', type='quantitative', title='Horsepower (HP)'),
        y=alt.Y('Type', type='nominal', title='', sort='-x'),
        color=alt.Color('Type', legend=None, scale=alt.Scale(domain=['Indicated HP', 'Brake HP'], range=['#d62728', '#1f77b4']))
    ).properties(
        title=f'Power @ {rpm} RPM'
    )
    st.altair_chart(power_chart, use_container_width=True)

    # Performance Curve over RPM Range
    st.subheader("Performance Curves")
    rpm_range = np.arange(1000, rpm_redline + 1, 250)
    perf_data = []

    # Engine A
    for r in rpm_range:
        res = EngineSimulator(
            num_cylinders, bore_mm, stroke_mm, compression_ratio, r, bsfc_g_kwh, afr, fuel_type, rpm_redline,
            rho_air, manifold_pressure_ratio, throttle_scaler
        ).get_results()
        perf_data.append({'Engine': 'A', 'RPM': r, 'Torque (N·m)': res['torque_nm'], 'BHP': res['bhp']})

    # Engine B (if enabled)
    if compare_enabled:
        for r in rpm_range:
            res_b = EngineSimulator(
                num_cylinders_b, bore_mm_b, stroke_mm_b, compression_ratio_b, r, bsfc_g_kwh_b, afr, fuel_type, rpm_redline_b,
                rho_air, manifold_pressure_ratio, throttle_scaler
            ).get_results()
            perf_data.append({'Engine': 'B', 'RPM': r, 'Torque (N·m)': res_b['torque_nm'], 'BHP': res_b['bhp']})

    perf_curve_data = pd.DataFrame(perf_data)

    # Melt data for layered chart
    perf_curve_melted = perf_curve_data.melt(id_vars=['RPM', 'Engine'], value_vars=['Torque (N·m)', 'BHP'], var_name='Metric', value_name='Value')

    # Create layered chart with separate y-axes
    base = alt.Chart(perf_curve_melted).encode(x='RPM:Q')
    line = base.mark_line().encode(
        y=alt.Y('Value:Q', axis=alt.Axis(title='')),
        color='Engine:N',
        strokeDash='Engine:N'
    )

    chart = line.facet(
        row=alt.Row('Metric:N', title='').sort(['BHP', 'Torque (N·m)'])
    ).resolve_scale(
        y='independent'
    )
    st.altair_chart(chart, use_container_width=True)

with chart_col2:
    st.subheader("Efficiency Analysis")
    # Efficiency Curves
    rpm_range_eff = np.arange(1000, rpm_redline + 1, 250)
    eff_data = []
    for r in rpm_range_eff:
        res = EngineSimulator(
            num_cylinders, bore_mm, stroke_mm, compression_ratio, r, bsfc_g_kwh, afr, fuel_type, rpm_redline,
            rho_air, manifold_pressure_ratio, throttle_scaler
        ).get_results()
        
        eff_data.append({
            'RPM': r,
            'Volumetric Efficiency (%)': res['volumetric_efficiency_percent'],
            'Mechanical Efficiency (%)': res['mechanical_efficiency_percent']
        })
    eff_df = pd.DataFrame(eff_data)
    eff_melted = eff_df.melt('RPM', var_name='Efficiency Type', value_name='Value')
    
    eff_chart = alt.Chart(eff_melted).mark_line().encode(
        x='RPM',
        y=alt.Y('Value', title='Efficiency (%)', scale=alt.Scale(zero=False)),
        color='Efficiency Type'
    ).properties(
        title='Efficiency vs. RPM'
    )
    st.altair_chart(eff_chart, use_container_width=True)

    # BMEP Curve
    st.subheader("BMEP Curve")
    
    # Create a dataframe with BMEP data for both engines
    bmep_data = []
    for r in rpm_range:
        res_a = EngineSimulator(
            num_cylinders, bore_mm, stroke_mm, compression_ratio, r, bsfc_g_kwh, afr, fuel_type, rpm_redline,
            rho_air, manifold_pressure_ratio, throttle_scaler
        ).get_results()
        bmep_data.append({'Engine': 'A', 'RPM': r, 'BMEP (kPa)': res_a['bmep_kpa']})
        
        if compare_enabled:
            res_b = EngineSimulator(
                num_cylinders_b, bore_mm_b, stroke_mm_b, compression_ratio_b, r, bsfc_g_kwh_b, afr, fuel_type, rpm_redline_b,
                rho_air, manifold_pressure_ratio, throttle_scaler
            ).get_results()
            bmep_data.append({'Engine': 'B', 'RPM': r, 'BMEP (kPa)': res_b['bmep_kpa']})

    bmep_df = pd.DataFrame(bmep_data)

    bmep_chart = alt.Chart(bmep_df).mark_line().encode(
        x='RPM',
        y=alt.Y('BMEP (kPa)', title='Brake Mean Effective Pressure (kPa)'),
        color='Engine:N',
        strokeDash='Engine:N'
    ).properties(
        title='BMEP vs. RPM'
    )
    st.altair_chart(bmep_chart, use_container_width=True)


# --- Assumptions and Notes ---
st.info(
    """
    **Assumptions & Model Notes:**
    - **Physics Model:** Engine performance is calculated using a physics-based model for air/fuel flow combined with empirical curves for major efficiencies. It now accounts for ambient conditions, boost, and throttle.
    - **Data Maps:** If a `./maps/ve_bsfc.csv` file is present, the simulator will override the analytical curves with interpolated data from the file, allowing for simulation of specific, real-world engines.
    - **Efficiencies:** The curves are designed to peak near the engine's torque peak and fall off at lower and higher RPMs, simulating real-world engine breathing and friction characteristics.
    - **Engine Visualizer:** The visualizer shows a simplified 3D representation. Firing order is evenly spaced for visualization purposes.
    """
)

if run_animation:
    # This loop runs to animate the engine
    time_step = 0.033 # Aim for ~30 FPS
    # Degrees of rotation per second = rpm * 360 / 60 = rpm * 6
    crank_angle_increment = rpm * 6 * time_step
    st.session_state.crank_angle_deg = (st.session_state.crank_angle_deg + crank_angle_increment) % 720
    time.sleep(time_step)
    st.rerun() 