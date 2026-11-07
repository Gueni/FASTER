#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                    ________________   ____        __
#?                   / ____/  _/_  __/  / __ \____ _/ /____  _____
#?                  / /_   / /  / /    / /_/ / __ `/ __/ _ \/ ___/
#?                 / __/ _/ /  / /    / _, _/ /_/ / /_/  __(__  )
#?                /_/   /___/ /_/    /_/ |_|\__,_/\__/\___/____/
#?
#? Name:        fit_rates.py
#? Purpose:     Base FIT rates and mission-profile (temperature / environment) adjustment.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Failure-rate knowledge base.

``BASE_FIT`` holds a typical component failure rate in FIT (failures per
1e9 device-hours) at **reference conditions**: 40 °C, ground benign (GB),
nominal stress, automotive-grade (AEC-Q qualified) parts. Values are typical
of the handbooks accepted by ISO 26262-5 §8.4.3: SN 29500 (Siemens), IEC 61709
(successor of IEC TR 62380) and MIL-HDBK-217F.

Mission-profile adjustment::

    FIT = base FIT * pi_T * pi_E
    pi_T = exp(Ea / k * (1 / T_ref - 1 / T))          Arrhenius, as in IEC 61709
    pi_E = MIL-HDBK-217F environment factor, normalised to GB = 1

A single activation energy per class is a simplification of the IEC 61709
models. Replace with supplier data, field data or your company handbook when
available.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .failures import FAILURE_MODES

BOLTZMANN_EV = 8.617333e-5      # eV/K
T_REF_C      = 40.0              # reference temperature of BASE_FIT


#? -------------------------------------------------------------------------------
@dataclass(frozen=True)
class FitData:
    fit     : float     # FIT at reference conditions
    ea      : float     # activation energy (eV) for the temperature factor
    source  : str


BASE_FIT: dict[str, FitData] = {
    'voltage'               : FitData(10.0, 0.40, 'Regulated supply (LDO / DC-DC) - SN 29500-2 / IEC 61709'),
    'current'               : FitData(10.0, 0.40, 'Current source / regulator - SN 29500-2 / IEC 61709'),
    'battery'               : FitData(50.0, 0.50, 'Li-ion cell - typical field data / FIDES'),
    'resistor'              : FitData(0.3,  0.15, 'Chip thick-film resistor - SN 29500-7 / IEC 61709'),
    'capacitor'             : FitData(0.5,  0.35, 'MLCC class II (X7R) - SN 29500-4 / IEC 61709'),
    'electrolytic capacitor': FitData(5.0,  0.50, 'Aluminium electrolytic - SN 29500-4 / IEC 61709'),
    'inductor'              : FitData(1.0,  0.15, 'SMD power inductor - SN 29500-8 / IEC 61709'),
    'ferrite bead'          : FitData(0.5,  0.15, 'Ferrite bead - SN 29500-8'),
    'transformer'           : FitData(5.0,  0.15, 'Signal / power transformer - SN 29500-8 / IEC 61709'),
    'crystal'               : FitData(5.0,  0.30, 'Quartz crystal - SN 29500-9 / IEC 61709'),
    'fuse'                  : FitData(2.0,  0.15, 'SMD fuse - SN 29500-11 / MIL-HDBK-217F'),
    'diode'                 : FitData(1.0,  0.40, 'Signal / rectifier diode - SN 29500-3 / IEC 61709'),
    'zener'                 : FitData(1.5,  0.40, 'Zener diode - SN 29500-3 / IEC 61709'),
    'tvs'                   : FitData(2.0,  0.40, 'TVS diode - SN 29500-3'),
    'schottky'              : FitData(1.5,  0.40, 'Schottky diode - SN 29500-3 / IEC 61709'),
    'LED'                   : FitData(3.0,  0.40, 'Indicator LED - SN 29500-12 / IEC 61709'),
    'bjt'                   : FitData(1.5,  0.50, 'Small-signal BJT - SN 29500-3 / IEC 61709'),
    'mosfet'                : FitData(10.0, 0.55, 'Power MOSFET - SN 29500-3 / IEC 61709'),
    'jfet'                  : FitData(3.0,  0.50, 'JFET - SN 29500-3'),
    'igbt'                  : FitData(30.0, 0.55, 'IGBT - SN 29500-3 / IEC 61709'),
    'thyristor'             : FitData(10.0, 0.50, 'Thyristor / triac - SN 29500-3'),
    'op-amp'                : FitData(10.0, 0.45, 'Op-amp / comparator - SN 29500-2 / IEC 61709'),
    'IC'                    : FitData(20.0, 0.45, 'Mixed-signal IC - SN 29500-2 / IEC 61709 (use supplier FIT)'),
    'relay'                 : FitData(40.0, 0.25, 'Signal relay, low cycling - SN 29500-10 / MIL-HDBK-217F'),
    'switch'                : FitData(10.0, 0.25, 'Switch / push-button - SN 29500-10'),
    'connector'             : FitData(5.0,  0.20, 'Connector (~10 contacts) - SN 29500-13 / MIL-HDBK-217F'),
}

# MIL-HDBK-217F environment factors (microcircuit table, normalised to GB = 1)
ENVIRONMENTS: dict[str, tuple[float, str]] = {
    'GB'    : (1.0,   'Ground benign (lab, office)'),
    'GF'    : (4.0,   'Ground fixed (industrial cabinet)'),
    'GM'    : (8.0,   'Ground mobile (automotive / vehicle mounted)'),
    'NS'    : (8.0,   'Naval sheltered'),
    'NU'    : (12.0,  'Naval unsheltered'),
    'AIC'   : (8.0,   'Airborne inhabited cargo'),
    'AIF'   : (10.0,  'Airborne inhabited fighter'),
    'AUC'   : (10.0,  'Airborne uninhabited cargo'),
    'AUF'   : (16.0,  'Airborne uninhabited fighter'),
    'ARW'   : (16.0,  'Airborne rotary wing'),
    'SF'    : (1.0,   'Space flight'),
    'MF'    : (10.0,  'Missile flight'),
    'ML'    : (24.0,  'Missile launch'),
    'CL'    : (440.0, 'Cannon launch'),
}


#? -------------------------------------------------------------------------------
def temperature_factor(ea: float, temperature_c: float, t_ref_c: float = T_REF_C) -> float:
    """Arrhenius acceleration factor between reference and operating temperature."""
    t, t_ref = temperature_c + 273.15, t_ref_c + 273.15
    return math.exp(ea / BOLTZMANN_EV * (1.0 / t_ref - 1.0 / t))


#? -------------------------------------------------------------------------------
def environment_factor(environment: str) -> float:
    try:
        return ENVIRONMENTS[environment.upper()][0]
    except KeyError:
        raise ValueError(f"Unknown environment '{environment}'. Use one of {', '.join(ENVIRONMENTS)}") from None


#? -------------------------------------------------------------------------------
def component_fit(component_type: str, temperature_c: float = T_REF_C, environment: str = 'GB',
                  overrides: dict[str, float] | None = None) -> dict[str, float]:
    """Return base FIT, factors and adjusted FIT of a component class."""
    data = BASE_FIT.get(component_type)
    if data is None:
        return {'base': 0.0, 'pi_T': 1.0, 'pi_E': 1.0, 'fit': 0.0}
    base = (overrides or {}).get(component_type, data.fit)
    pi_t = temperature_factor(data.ea, temperature_c)
    pi_e = environment_factor(environment)
    return {'base': base, 'pi_T': pi_t, 'pi_E': pi_e, 'fit': base * pi_t * pi_e}


# Backwards compatible view at reference conditions: {type: {mode: FIT}}
fit_rates: dict[str, dict[str, float]] = {
    t: {m.name: BASE_FIT[t].fit * m.distribution / 100.0 for m in c.modes}
    for t, c in FAILURE_MODES.items() if t in BASE_FIT
}

#? -------------------------------------------------------------------------------
