"""
temperature.py

Helper methods for measuring temperature

Copyright (C) 2022 Nick Whalen (benumbed@projectneutron.com)

The Steinhart-Hart equations were pulled from
https://www.allaboutcircuits.com/industry-articles/how-to-obtain-the-temperature-value-from-a-thermistor-measurement/
"""
import micropython
from math import log, pow

TEMPERATURE_C = 0
TEMPERATURE_F = 1

# https://www.alphacool.com/download/kOhm_Sensor_Table_Alphacool.pdf
ALPHACOOL_SHH_COEFS = (0.0008659402243206102, 0.00025547032882431244, 1.7292289771201514e-07)
ALPHACOOL_BETA_VALUE = 3435

@micropython.native
def computeResistance(adc_voltage: float, adc_vref: float = 3.31175, pair_resistor=10_000):
    return (adc_voltage * pair_resistor) / (adc_vref - adc_voltage)


def computeTemperature(adc_voltage: float, shh_A: float, shh_B: float, shh_C: float, adc_vref: float = 3.31175,
                       pair_resistance=10_000, units: int = TEMPERATURE_C) -> float:
    """
    Wrapper to allow for both Celsius and Fahrenheit values to be returned (based on `units`)
    :param adc_voltage: The voltage measured by the ADC across the thermistor
    :param shh_A: Steinhart-Hart coefficient A
    :param shh_B: Steinhart-Hart coefficient B
    :param shh_C: Steinhart-Hart coefficient C
    :param adc_vref: The ADC reference voltage
    :param pair_resistance: The resistance of the other resistor (not the sensor) in the voltage divider
                       (10kOhms for 10K thermistors)
    :param units: TEMPERATURE_C or TEMPERATURE_F
    :return:
    """
    if units == TEMPERATURE_F:
        return kelvinToFahrenheit(computeKelvin(adc_voltage, shh_A, shh_B, shh_C, adc_vref, pair_resistance))
    else:
        return kelvinToCelsius(computeKelvin(adc_voltage, shh_A, shh_B, shh_C, adc_vref, pair_resistance))

@micropython.native
def computeKelvin(adc_voltage: float, shh_A: float, shh_B: float, shh_C: float, adc_vref: float = 3.31175,
                       pair_resistance=10_000) -> float:
    """
    Compute temperature in Kelvin from the voltage drop. See `computeSHHCoefficients` to compute the coefficients for
    a new sensor. Save the values somewhere permanent, they do not change and should not be recomputed.

    :param adc_voltage: The voltage measured by the ADC across the thermistor
    :param shh_A: Steinhart-Hart coefficient A
    :param shh_B: Steinhart-Hart coefficient B
    :param shh_C: Steinhart-Hart coefficient C
    :param adc_vref: The ADC reference voltage
    :param pair_resistance: The resistance of the other resistor (not the sensor) in the voltage divider
                       (10kOhms for 10K thermistors)

    :return: Temperature in Kelvin
    """
    # Hello Steinhart-Hart
    return (1 / (shh_A + shh_B * log(computeResistance(adc_voltage, adc_vref, pair_resistance)) + shh_C *
                 pow(log(computeResistance(adc_voltage, adc_vref, pair_resistance)), 3)))

@micropython.native
def computeBetaTemperature(adc_voltage, beta_val, adc_vref = 3.31175, divider_resist = 10_000) -> float:
    """
    Beta calculation for thermistors, this is just experimental

    :param adc_voltage:
    :param beta_val:
    :param adc_vref:
    :param divider_resist:

    :return: Celsius
    """
    return (1/((1/298.15)+(1/beta_val)*
               (log(computeResistance(adc_voltage, adc_vref, divider_resist)/10_000))) - 273.15)

@micropython.native
def kelvinToFahrenheit(k_val: float) -> float:
    """
    Converts a Kelvin value to a Fahrenheit value

    :param k_val: Kelvin value

    :return: Fahrenheit value
    """
    return (k_val * (9/5))-459.67

@micropython.native
def kelvinToCelsius(k_val: float) -> float:
    """
    Converts a Kelvin value to a Celsius value

    :param k_val: Kelvin value

    :return: Celsius value
    """
    return k_val - 273.15 # 0C is 273.15K

@micropython.native
def celsiusToKelvin(c_val: float) -> float:
    """
   Converts a Celsius value to a Kelvin value

   :param c_val: Celsius value

   :return: Kelvin value
   """
    return 273.15 + c_val

@micropython.native
def computeSHHCoefficients(low_R, mid_R, high_R, high_Temp = 150, mid_Temp = 25, low_Temp = -40) -> tuple:
    """
    Standard implementation of the Steinhart-Hart coefficient equations. You only need to run this once for a sensor,
    the values are permanent. See the sensor manufacturer's R-T table for the sensor for the appropriate values.

    :param low_R:  The lowest resistance the thermistor supports (R-T Table)
    :param mid_R:  The mid-range resistance the thermistor supports (R-T Table 10_000 ohms for standard 10K thermistors)
    :param high_R: The highest resistance the thermistor supports (R-T Table)
    :param high_Temp: Highest temperature value for the sensor in Celsius (Y3 of SHH)   (usually 125C or 150C)
    :param mid_Temp: Mid-range temperature value for the sensor in Celsius (Y2 of SHH)  (usually 25C)
    :param low_Temp: Lowest temperature value for the sensor in Celsius (Y1 of SHH)     (usually -40C)

    :return: (A, B, C) Steinhart-Hart Coefficients
    """
    R1 = high_R
    R2 = mid_R
    R3 = low_R

    Y1 = 1 / celsiusToKelvin(low_Temp)
    Y2 = 1 / celsiusToKelvin(mid_Temp)
    Y3 = 1 / celsiusToKelvin(high_Temp)

    L1 = log(R1)
    L2 = log(R2)
    L3 = log(R3)

    g2 = (Y2 - Y1) / (L2 - L1)
    g3 = (Y3 - Y1) / (L3 - L1)

    C = ((g3 - g2) / (L3 - L2)) * (pow((L1 + L2 + L3), -1))
    B = g2 - C * (pow(L1, 2) + (L1 * L2) + pow(L2, 2))
    A = Y1 - (B + pow(L1, 2) * C) * L1

    return A, B, C
