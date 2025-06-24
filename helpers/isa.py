import numpy as np

def get_isa_rho(altitude_m, temp_c):
    """
    Calculates air density (rho) at a given altitude and temperature based on the
    International Standard Atmosphere (ISA) model, with temperature correction.

    Args:
        altitude_m (float): Altitude in meters.
        temp_c (float): Ambient temperature in Celsius.

    Returns:
        float: Air density in kg/m^3.
    """
    # ISA constants
    P0 = 101325  # Sea-level standard pressure (Pa)
    T0 = 288.15   # Sea-level standard temperature (K)
    g = 9.80665   # Gravitational acceleration (m/s^2)
    L = 0.0065    # Temperature lapse rate (K/m)
    R = 287.058   # Specific gas constant for dry air (J/(kg·K))

    # Convert input temperature to Kelvin
    temp_k = temp_c + 273.15

    # ISA temperature at altitude
    T_isa = T0 - L * altitude_m
    
    # Pressure at altitude using the barometric formula
    pressure_pa = P0 * (1 - L * altitude_m / T0)**(g * 0.0289644 / (R * L))

    # Density using the ideal gas law with the user-provided temperature
    rho = pressure_pa / (R * temp_k)
    
    return rho 