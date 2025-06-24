import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
import os

# --- Constants and Assumptions ---
# Standard sea-level air density (kg/m^3)
RHO_AIR_SL = 1.225
# Ratio of specific heats for air (dimensionless)
GAMMA = 1.4
# Watson-Heywood coefficients for FMEP (Pa) vs. mean piston speed (m/s)
# FMEP = C1 + C2*Sp + C3*Sp^2
FMEP_COEFFS_WH = (1.0e5, 600, 20) 

# Fuel Properties: LHV (MJ/kg), Density (kg/L), Stoichiometric AFR
FUEL_PROPERTIES = {
    'Gasoline': {'lhv_mj_kg': 44.0, 'density_kg_l': 0.75, 'stoich_afr': 14.7},
    'Diesel':   {'lhv_mj_kg': 42.5, 'density_kg_l': 0.85, 'stoich_afr': 14.5},
    'E85':      {'lhv_mj_kg': 27.0, 'density_kg_l': 0.78, 'stoich_afr': 9.7},
}

def _gauss(x, mu, sigma, floor=0.0):
    """Gaussian helper that never goes below `floor`."""
    return np.maximum(np.exp(-0.5*((x-mu)/sigma)**2), floor)

class EngineSimulator:
    """
    A class to simulate the performance of an internal combustion engine.
    All internal calculations are done in SI units.
    """
    def __init__(
        self,
        num_cylinders,
        bore_mm,
        stroke_mm,
        compression_ratio,
        rpm,
        bsfc_g_kwh,
        afr,
        fuel_type='Gasoline',
        rpm_redline=8500,
        # Phase 2 additions
        rho_air=1.225,
        manifold_pressure_ratio=1.0,
        throttle_scaler=1.0
    ):
        """
        Initializes the simulation with user-defined engine parameters.
        
        Args:
            num_cylinders (int): Number of cylinders.
            bore_mm (float): Cylinder bore in millimeters.
            stroke_mm (float): Piston stroke in millimeters.
            compression_ratio (float): Engine compression ratio.
            rpm (int): Engine speed in revolutions per minute.
            bsfc_g_kwh (float): Base brake-specific fuel consumption in g/kWh (at torque peak).
            afr (float): Air-fuel ratio.
            fuel_type (str): Type of fuel ('Gasoline' or 'Diesel').
            rpm_redline (int): The redline of the engine in RPM.
            rho_air (float): Ambient air density in kg/m^3.
            manifold_pressure_ratio (float): Ratio of manifold to ambient pressure (1.0 for NA).
            throttle_scaler (float): Scaler from 0.0 to 1.0 representing throttle position.
        """
        # --- Store and Convert Inputs to SI units ---
        self.num_cylinders = num_cylinders
        self.bore_m = bore_mm / 1000.0
        self.stroke_m = stroke_mm / 1000.0
        self.compression_ratio = compression_ratio
        self.rpm = rpm
        self.rpm_redline = rpm_redline
        self.bsfc_kg_j = bsfc_g_kwh / (1000 * 3.6e6) 
        self.afr = afr
        self.fuel_type = fuel_type
        self.rho_air = rho_air
        self.manifold_pressure_ratio = manifold_pressure_ratio
        self.throttle_scaler = throttle_scaler
        
        self.fuel_lhv_j_kg = FUEL_PROPERTIES[fuel_type]['lhv_mj_kg'] * 1e6
        self.fuel_density_kg_l = FUEL_PROPERTIES[fuel_type]['density_kg_l']

        # --- Load VE/BSFC maps if available ---
        self.ve_interp = None
        self.bsfc_interp = None
        self._load_maps()

        # --- Run Calculations on Initialization ---
        self.results = self._calculate_performance()

    def _load_maps(self):
        """Load VE and BSFC maps from a CSV file if it exists."""
        map_path = './maps/ve_bsfc.csv'
        if os.path.exists(map_path):
            try:
                df = pd.read_csv(map_path)
                # Create interpolation functions
                self.ve_interp = interp1d(df['RPM'], df['VE'], kind='cubic', fill_value="extrapolate")
                self.bsfc_interp = interp1d(df['RPM'], df['BSFC_g_kWh'], kind='cubic', fill_value="extrapolate")
            except (FileNotFoundError, pd.errors.EmptyDataError, KeyError):
                self.ve_interp = None
                self.bsfc_interp = None
    
    def _calculate_performance(self):
        """
        Performs all engine calculations based on the initialized parameters.
        This version uses empirically-shaped curves and a friction model
        to produce a realistic torque curve.
        """
        # --- 1. Displacement ----------------------------------------------------
        piston_area = np.pi * (self.bore_m / 2)**2
        Vd_m3 = piston_area * self.stroke_m * self.num_cylinders
        disp_L = Vd_m3 * 1000

        # --- 2. Efficiency Curves (RPM-dependent) -----------------------------
        if self.ve_interp:
             ve_curve = self.ve_interp(self.rpm) / 100 # CSV is in percent
        else:
            # Skewed Gaussian for Volumetric Efficiency (VE)
            rpm_peak_ve = self.rpm_redline * 0.6
            sigma_low = rpm_peak_ve * 0.4
            sigma_high = rpm_peak_ve * 0.6
            sigma = np.where(self.rpm < rpm_peak_ve, sigma_low, sigma_high)
            ve_curve = 0.75 + 0.25 * np.exp(-0.5 * ((self.rpm - rpm_peak_ve) / sigma)**2)

        if self.bsfc_interp:
            bsfc_g_kwh = self.bsfc_interp(self.rpm)
            bsfc_curve_kg_j = bsfc_g_kwh / (1000 * 3.6e6)
        else:
             # BSFC curve improves (reduces) at VE peak
            rpm_peak_ve = self.rpm_redline * 0.6 # Re-calc for clarity
            bsfc_multiplier = 1.4 - 0.5 * _gauss(self.rpm, rpm_peak_ve, rpm_peak_ve * 0.5)
            bsfc_curve_kg_j = self.bsfc_kg_j * bsfc_multiplier
            bsfc_g_kwh = bsfc_curve_kg_j * (1000 * 3.6e6)

        # --- 3. Air & Fuel Flow -------------------------------------------------
        m_dot_air_base = Vd_m3 * (self.rpm / 120) * self.rho_air * ve_curve
        m_dot_air = m_dot_air_base * self.manifold_pressure_ratio * self.throttle_scaler
        m_dot_fuel = m_dot_air / self.afr
        fuel_flow_lh = (m_dot_fuel / self.fuel_density_kg_l) * 3600

        # --- 4. Power, Torque, and Pressures ------------------------------------
        # Brake power is determined by fuel energy rate and BSFC
        P_brake_W = m_dot_fuel / bsfc_curve_kg_j if bsfc_curve_kg_j > 0 else 0.0
        omega = self.rpm * 2 * np.pi / 60
        torque_Nm = P_brake_W / omega if omega > 0 else 0.0
        
        # BMEP (Brake Mean Effective Pressure) in Pa for a 4-stroke engine
        bmep_pa = (torque_Nm * 2 * np.pi) / Vd_m3 if Vd_m3 > 0 else 0.0

        # --- 5. Frictional & Indicated Power/Pressures --------------------------
        mean_piston_speed = 2 * self.stroke_m * self.rpm / 60
        fmep_pa = (FMEP_COEFFS_WH[0] + 
                   FMEP_COEFFS_WH[1] * mean_piston_speed + 
                   FMEP_COEFFS_WH[2] * mean_piston_speed**2)
        
        P_friction_W = (fmep_pa * Vd_m3 * self.rpm) / 120 # For 4-stroke
        P_ind_W = P_brake_W + P_friction_W
        imep_pa = (P_ind_W / Vd_m3) * (4 * np.pi / (self.rpm / 60)) if Vd_m3 > 0 and self.rpm > 0 else 0.0

        # --- 6. Final Efficiencies ----------------------------------------------
        eta_mech = P_brake_W / P_ind_W if P_ind_W > 0 else 0.0
        eta_th_brake = P_brake_W / (m_dot_fuel * self.fuel_lhv_j_kg) if m_dot_fuel > 0 else 0.0
        eta_th_otto = 1 - (1 / self.compression_ratio**(GAMMA - 1))

        return {
            'displacement_l': disp_L,
            'air_mass_flow_kg_s': m_dot_air,
            'fuel_mass_flow_kg_s': m_dot_fuel,
            'fuel_flow_l_hr': fuel_flow_lh,
            'bhp': P_brake_W / 745.7,
            'ihp': P_ind_W / 745.7,
            'torque_nm': torque_Nm,
            'bmep_kpa': bmep_pa / 1000,
            'imep_kpa': imep_pa / 1000,
            'fmep_kpa': fmep_pa / 1000,
            'bsfc_g_kwh': bsfc_g_kwh,
            'mechanical_efficiency_percent': eta_mech * 100,
            'brake_thermal_efficiency_percent': eta_th_brake * 100,
            'thermal_efficiency_percent': eta_th_otto * 100, # Ideal Otto cycle
            'volumetric_efficiency_percent': ve_curve * 100,
        }

    def get_results(self):
        """Returns the calculated performance metrics."""
        return self.results 