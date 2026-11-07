#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                        ______      _ __
#?                       / ____/___ _(_) /_  __________  _____
#?                      / /_  / __ `/ / / / / / ___/ _ \/ ___/
#?                     / __/ / /_/ / / / /_/ / /  /  __(__  )
#?                    /_/    \__,_/_/_/\__,_/_/   \___/____/
#?
#? Name:        failures.py
#? Purpose:     Failure modes, mechanisms, effects and mode distributions per component class.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""Failure-mode knowledge base.

For each component class: the failure modes, their share of the component
failure rate (``distribution`` in %, sums to 100), the physical mechanism and
the general (local) effect.

Distributions follow published failure-mode/mechanism data:

* RIAC FMD-2016 *Failure Mode / Mechanism Distributions* (successor of FMD-91/97)
* MIL-HDBK-338B *Electronic Reliability Design Handbook*, failure mode tables
* ISO 26262-5:2018 Annex D (failure modes to consider per element class) and
  ISO 26262-11:2018 (fault models for semiconductor components)

Where a source gives a single "parameter change" share, it is split into
drift high / drift low; those splits and classes without a published table
are marked ``derived``. Replace the values with your own field / supplier
data when available (ISO 26262-5 §8.4.3 accepts any justified source).
"""

from __future__ import annotations

from dataclasses import dataclass

FMD     = 'RIAC FMD-2016'
MIL338  = 'MIL-HDBK-338B'
ISO5    = 'ISO 26262-5:2018 Annex D'
ISO11   = 'ISO 26262-11:2018'
DERIVED = 'derived'


#? -------------------------------------------------------------------------------
@dataclass(frozen=True)
class FailureMode:
    name            : str
    distribution    : float     # % of the component failure rate
    mechanism       : str
    effect          : str


#? -------------------------------------------------------------------------------
@dataclass(frozen=True)
class ComponentClass:
    description     : str
    source          : str
    modes           : tuple[FailureMode, ...]


#? -------------------------------------------------------------------------------
def _c(description: str, source: str, *modes: tuple[str, float, str, str]) -> ComponentClass:
    return ComponentClass(description, source, tuple(FailureMode(*m) for m in modes))


FAILURE_MODES: dict[str, ComponentClass] = {

    #? sources                                                                        
    'voltage': _c('Voltage source / supply rail', f'{ISO5} (power supply) / {DERIVED} split',
        ('over-voltage',        20, 'Regulator loss of control, load dump, short to higher rail',
                                    'Over-stress of supplied parts, possible permanent damage'),
        ('under-voltage',       30, 'Regulator dropout, increased source impedance, brown-out',
                                    'Undefined logic levels, resets, reduced output swing'),
        ('loss of supply',      30, 'Open supply path, blown fuse, regulator shutdown',
                                    'Loss of function of all supplied parts'),
        ('drift / oscillation', 15, 'Reference drift, loop instability',
                                    'Accuracy loss of supply-referenced measurements, noise injection'),
        ('power spikes',         5, 'Transients, insufficient decoupling',
                                    'Glitches, spurious resets, latch-up risk')),

    'current': _c('Current source', f'{ISO5} / {DERIVED}',
        ('current high',        35, 'Reference or sense resistor drift',      'Over-drive of the load, over-temperature'),
        ('current low',         35, 'Compliance loss, reference drift',       'Under-drive of the load, loss of function'),
        ('open (no current)',   30, 'Open output path, internal failure',     'Loss of function of the driven load')),

    'battery': _c('Battery / cell (Li-ion)', FMD,
        ('degraded output',     78, 'Capacity fade, SEI growth, increased internal resistance',
                                    'Reduced autonomy, voltage sag under load'),
        ('start-up delay',      14, 'Passivation layer, low-temperature impedance',
                                    'Delayed or failed power-up'),
        ('internal short',       6, 'Separator breakdown, dendrite growth',
                                    'Thermal runaway, venting / fire hazard (safety critical)'),
        ('open circuit',         2, 'Tab / weld fracture, CID activation',
                                    'Loss of supply')),

    #? passives                                                                       
    'resistor': _c('Fixed film resistor (chip)', f'{FMD} (open 59 / change 36 / short 5)',
        ('open circuit',        59, 'Film cracking, sulfur corrosion of Ag termination, solder joint fatigue',
                                    'Interrupted current path; pull-ups float, dividers saturate to a rail'),
        ('drift high',          24, 'Film oxidation, overload, moisture',
                                    'Shifted bias / divider ratio, timing or gain error'),
        ('drift low',           12, 'Partial short of film, ESD, overload',
                                    'Shifted bias / divider ratio, higher current'),
        ('short circuit',        5, 'Conductive contamination, metal migration',
                                    'Bypassed resistance: over-current, loss of current limiting')),

    'capacitor': _c('Ceramic capacitor (MLCC)', f'{FMD} (short 49 / change 29 / open 22)',
        ('short circuit',       49, 'Flex / thermal cracking, dielectric breakdown, Ag migration',
                                    'Short of the supply or signal node, over-current, possible fuse / rail collapse'),
        ('open circuit',        22, 'Termination crack, solder joint fatigue',
                                    'Loss of filtering / decoupling, ripple, EMC degradation, unstable loops'),
        ('drift low',           19, 'Ageing of class-II dielectric, DC-bias, temperature',
                                    'Reduced capacitance: higher ripple, shorter time constants'),
        ('drift high',          10, 'Temperature coefficient, moisture',
                                    'Increased capacitance: slower response, longer time constants')),

    'electrolytic capacitor': _c('Aluminium electrolytic capacitor', f'{MIL338} / {FMD}',
        ('short circuit',       53, 'Dielectric (oxide) breakdown, over-voltage, reverse polarity',
                                    'Rail short, over-current, venting'),
        ('open circuit',        35, 'Electrolyte dry-out, lead / tab corrosion',
                                    'Loss of bulk capacitance, high ripple, regulator instability'),
        ('ESR increase / leak', 10, 'Electrolyte evaporation, seal degradation',
                                    'Self-heating, ripple increase, contamination by electrolyte'),
        ('capacitance loss',     2, 'Wear-out (dry-out)',
                                    'Reduced hold-up time, increased ripple')),

    'inductor': _c('Inductor / coil', f'{MIL338} (short 42 / open 42 / change 16)',
        ('open circuit',        42, 'Wire break, termination crack, thermal stress',
                                    'Interrupted current path, loss of power conversion / filtering'),
        ('short circuit',       42, 'Insulation breakdown between turns',
                                    'Reduced inductance, over-current, converter instability'),
        ('drift low',           10, 'Core saturation, core cracking, temperature',
                                    'Higher ripple current, possible saturation'),
        ('drift high',           6, 'Core material ageing',
                                    'Slower current slope, changed filter corner')),

    'ferrite bead': _c('Ferrite bead', f'{DERIVED} (inductor data)',
        ('open circuit',        50, 'Termination crack, overload',          'Interrupted supply / signal path'),
        ('impedance drift',     40, 'Core saturation, temperature',         'Reduced EMI suppression'),
        ('short circuit',       10, 'Insulation breakdown',                 'Loss of filtering (bead bypassed)')),

    'transformer': _c('Transformer', f'{MIL338} / {DERIVED}',
        ('open winding',        42, 'Wire break, termination fatigue',
                                    'No energy transfer, loss of isolated supply / signal'),
        ('shorted turns',       42, 'Inter-turn insulation breakdown',
                                    'Reduced inductance, over-current, overheating'),
        ('parameter drift',     10, 'Core ageing, saturation, temperature',
                                    'Changed turns-ratio behaviour, output voltage error'),
        ('insulation failure',   6, 'Primary-secondary breakdown, partial discharge',
                                    'Loss of galvanic isolation (safety critical)')),

    'crystal': _c('Quartz crystal / resonator', f'{FMD} / {DERIVED}',
        ('no oscillation',      60, 'Crystal fracture, contamination, drive-level damage',
                                    'Clock loss, MCU / timing function stops'),
        ('frequency drift',     30, 'Ageing, mass loading, temperature',
                                    'Timing / communication errors'),
        ('short circuit',       10, 'Electrode migration',
                                    'Oscillator stage loaded, no clock')),

    'fuse': _c('Fuse', f'{MIL338} (fails to open 49 / slow 43 / premature 8)',
        ('fails to open',       49, 'Wrong rating, element alloy change',
                                    'No over-current protection, fire hazard on downstream fault'),
        ('slow to open',        43, 'Element degradation, ambient temperature',
                                    'Extended over-current stress of protected parts'),
        ('premature open',       8, 'Fatigue from inrush cycles, ageing',
                                    'Nuisance loss of supply')),

    #? discrete semiconductors                                                        
    'diode': _c('Rectifier / signal diode', f'{FMD} (short 49 / open 36 / change 15)',
        ('short circuit',       49, 'Junction breakdown, over-voltage, ESD',
                                    'Loss of rectification / reverse protection, rail short'),
        ('open circuit',        36, 'Bond wire lift, die crack, solder fatigue',
                                    'No conduction: loss of rectification / clamping / freewheeling'),
        ('reverse leakage',      9, 'Junction contamination, high temperature',
                                    'Leakage current, efficiency loss, thermal runaway risk'),
        ('forward voltage drift', 6, 'Die attach degradation',
                                    'Increased dissipation, threshold shift')),

    'zener': _c('Zener diode', f'{FMD} (change 69 / open 18 / short 13)',
        ('Vz drift high',       35, 'Junction degradation, temperature',
                                    'Clamp / reference voltage too high, protection margin lost'),
        ('Vz drift low',        34, 'Junction degradation, leakage',
                                    'Reference too low, excessive clamp current'),
        ('open circuit',        18, 'Bond wire lift, die crack',
                                    'No regulation / clamping: over-voltage on protected node'),
        ('short circuit',       13, 'Over-stress, ESD',
                                    'Protected node shorted, over-current')),

    'tvs': _c('TVS diode / varistor', f'{FMD} / {DERIVED}',
        ('short circuit',       55, 'Surge energy above rating',             'Line shorted to ground, loss of function, fuse blow'),
        ('open circuit',        25, 'Thermal disconnect, bond lift after surge', 'No transient protection (latent fault)'),
        ('leakage increase',    20, 'Repeated surge degradation',            'Loading of the line, offset error')),

    'schottky': _c('Schottky diode', f'{FMD} / {DERIVED}',
        ('short circuit',       45, 'Barrier breakdown, ESD, over-voltage',
                                    'Loss of rectification / reverse protection, rail short'),
        ('open circuit',        30, 'Bond wire lift, solder fatigue',
                                    'No conduction: loss of rectification / freewheeling'),
        ('reverse leakage',     20, 'High-temperature barrier degradation',
                                    'Leakage, thermal runaway risk at high temperature'),
        ('forward voltage drift', 5, 'Die attach degradation',
                                    'Increased dissipation')),

    'LED': _c('Light emitting diode', f'{FMD} / IEC 62717 wear-out',
        ('open circuit',        60, 'Bond wire break, die attach fatigue',
                                    'No light emission (indicator / illumination lost)'),
        ('short circuit',       25, 'ESD, electromigration',
                                    'No light, current path shorted'),
        ('light output degradation', 15, 'Phosphor / die degradation (wear-out)',
                                    'Insufficient luminance, colour shift')),

    'bjt': _c('Bipolar transistor', f'{FMD} (short 73 / open 27) + {ISO11}',
        ('C-E short',           50, 'Second breakdown, over-voltage, ESD',
                                    'Permanently on: load always driven'),
        ('open circuit',        27, 'Bond wire lift, die crack, solder fatigue',
                                    'Permanently off: load never driven'),
        ('B-E short',           13, 'Over-stress of base-emitter junction',
                                    'Transistor cannot turn on, base drive loaded'),
        ('gain / leakage drift', 10, 'Hot carrier, ionic contamination',
                                    'Bias point shift, gain error, leakage')),

    'mosfet': _c('MOSFET', f'{FMD} (short 51 / out-low 22 / change 17 / open 5 / out-high 5) + {ISO11}',
        ('D-S short',           51, 'Avalanche, SOA violation, gate oxide rupture',
                                    'Permanently on: load always driven, possible over-current'),
        ('stuck off',           22, 'Gate oxide damage, gate open',
                                    'Permanently off: load never driven'),
        ('Rds(on) / Vth drift', 17, 'Hot-carrier injection, BTI, bond degradation',
                                    'Increased dissipation, switching threshold shift'),
        ('open circuit',         5, 'Bond wire lift, solder fatigue',
                                    'Permanently off'),
        ('gate leakage',         5, 'Gate oxide degradation, ESD',
                                    'Gate driver loaded, partial turn-on')),

    'jfet': _c('JFET', f'{FMD} (FET data)',
        ('D-S short',           51, 'Over-stress, ESD',                     'Permanently conducting'),
        ('stuck off',           22, 'Gate junction damage',                 'No conduction'),
        ('parameter drift',     17, 'Idss / Vp drift',                      'Bias shift, gain error'),
        ('open circuit',        10, 'Bond wire lift',                       'No conduction')),

    'igbt': _c('IGBT', f'{FMD} / {ISO11}',
        ('C-E short',           55, 'Latch-up, SOA violation, short-circuit withstand exceeded',
                                    'Permanently on, possible shoot-through'),
        ('stuck off',           20, 'Gate oxide damage, gate open',         'Permanently off'),
        ('Vce(sat) / Vth drift', 15, 'Bond wire lift-off, solder fatigue (power cycling)',
                                    'Increased losses, thermal runaway risk'),
        ('open circuit',        10, 'Bond wire lift-off',                   'Permanently off')),

    'thyristor': _c('Thyristor / triac / diac', f'{FMD} / {DERIVED}',
        ('short circuit',       50, 'dv/dt or di/dt over-stress',           'Permanently conducting'),
        ('fails to trigger',    30, 'Gate damage, open',                    'No conduction'),
        ('spurious triggering', 20, 'Noise, leakage increase',              'Unintended conduction')),

    #? integrated circuits                                                            
    'op-amp': _c('Operational amplifier / comparator', f'{ISO11} (analogue fault model) / {FMD}',
        ('output stuck high/low', 30, 'Output stage damage, internal short, EOS',
                                    'Constant output regardless of input'),
        ('offset / gain drift',  35, 'Input stage degradation, trimming drift',
                                    'Accuracy error of the amplified / compared signal'),
        ('open input/output',    15, 'Bond wire lift, solder fatigue',
                                    'Floating or missing output'),
        ('supply short',         10, 'EOS, latch-up',
                                    'Supply rail loaded / shorted'),
        ('oscillation',          10, 'Loss of compensation, degraded phase margin',
                                    'Noise / ripple on output, EMC issues')),

    'IC': _c('Integrated circuit (generic)', f'{ISO11} (digital & mixed-signal fault models)',
        ('output stuck-at',     30, 'Transistor / via defects, EOS, electromigration',
                                    'Output fixed at 0/1 or rail'),
        ('functional failure',  30, 'Random hardware fault in logic / memory / analogue blocks',
                                    'Wrong output behaviour, possible safety-goal violation'),
        ('pin open',            15, 'Bond wire lift, solder joint crack',
                                    'Floating input / output, undefined state'),
        ('pin short',           15, 'EOS, ESD, latch-up, dendrites',
                                    'Neighbouring pin / supply short'),
        ('parameter drift',     10, 'NBTI / HCI ageing, temperature',
                                    'Timing, threshold or reference drift')),

    #? electromechanical                                                              
    'relay': _c('Electromechanical relay', f'{FMD} (fails to trip 55 / spurious 26 / short 19)',
        ('fails to switch',     55, 'Coil open, contact contamination / oxidation',
                                    'Load not switched on/off as commanded'),
        ('spurious switching',  26, 'Vibration, coil drive fault, contact bounce',
                                    'Unintended connection / disconnection of the load'),
        ('contact welding',     19, 'Inrush / arcing current',
                                    'Load cannot be disconnected (safety critical)')),

    'switch': _c('Switch', f'{FMD} / {DERIVED}',
        ('contact open / high resistance', 50, 'Oxidation, wear, contamination',
                                    'Command not executed, voltage drop'),
        ('stuck closed',        30, 'Contact welding, mechanical jam',      'Permanent connection'),
        ('intermittent / bounce', 20, 'Wear, vibration',                     'Spurious transitions')),

    'connector': _c('Connector', f'{MIL338} (open 61 / poor contact 23 / short 16)',
        ('open circuit',        61, 'Fretting corrosion, pin push-out, solder crack',
                                    'Loss of signal / supply on the affected pin'),
        ('intermittent contact', 23, 'Fretting, low contact force, vibration',
                                    'Intermittent signal, communication errors'),
        ('short circuit',       16, 'Contamination, moisture, bent pins',
                                    'Adjacent pins shorted')),
}


#? -------------------------------------------------------------------------------
#? derived views                                                                        
def modes(component_type: str) -> tuple[FailureMode, ...]:
    entry = FAILURE_MODES.get(component_type)
    return entry.modes if entry else ()


# Backwards compatible view: {type: {mode: effect}}
component_failures: dict[str, dict[str, str]] = {
    t: {m.name: m.effect for m in c.modes} for t, c in FAILURE_MODES.items()
}


#? -------------------------------------------------------------------------------
def check_distributions() -> dict[str, float]:
    """Return classes whose mode distributions do not sum to 100 %."""
    return {t: s for t, c in FAILURE_MODES.items() if abs((s := sum(m.distribution for m in c.modes)) - 100) > 1e-6}

#? -------------------------------------------------------------------------------
