
#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?
#?          ____      _ __                                       __
#?         / __/___ _(_) /_  __________     ____ ___  ____  ____/ /__  _____
#?        / /_/ __ `/ / / / / / ___/ _ \   / __ `__ \/ __ \/ __  / _ \/ ___/
#?       / __/ /_/ / / / /_/ / /  /  __/  / / / / / / /_/ / /_/ /  __(__  ) 
#?      /_/  \__,_/_/_/\__,_/_/   \___/  /_/ /_/ /_/\____/\__,_/\___/____/  
#?      
#?
#? Name:        Failures.py
#? Purpose:     Define failure modes for various components
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------  
#? -------------------------------------------------------------------------------  

component_failures = {                  
   
    'voltage': {
        'value change'                  : 'Incorrect input voltage affects operation, may trigger safety mechanisms (ISO 26262 SPFM)'
    },

    'resistor': {
        'open circuit'                  : 'No current flow, circuit malfunction (MIL-HDBK-217 base failure mode)',
        'short circuit'                 : 'Potential overcurrent, possible damage, can lead to system failure if not detected (ISO 26262 LFM)',
        'drift high'                    : 'Increased resistance due to aging or stress, may lead to reduced current and circuit malfunction (Birolini Weibull model)',
        'drift low'                     : 'Decreased resistance, potential for overcurrent and overheating (Birolini Weibull model)'
    },

    'capacitor': {
        'open circuit'                  : 'Loss of capacitance, failure to filter or store energy (MIL-HDBK-217 base failure mode)',
        'short circuit'                 : 'Direct current flow, potential damage to power supply or other components (ISO 26262 Residual Risk)',
        'drift high'                    : 'Increased capacitance, may cause timing issues or resonate with inductance (Birolini Markov model)',
        'drift low'                     : 'Decreased capacitance, may reduce filtering effectiveness or storage capacity (Birolini Markov model)'
    },

    'inductor': {
        'value drift'                   : 'Inductance change due to core saturation or aging, impacts performance (Birolini Reliability Model)',
        'drift high'                    : 'Increased inductance may affect circuit timing or filtering (Birolini Reliability Model)',
        'drift low'                     : 'Decreased inductance may reduce energy storage and affect circuit operation (Birolini Reliability Model)',
        'open circuit'                  : 'Loss of inductance, circuit malfunction or reduced efficiency (MIL-HDBK-217 base failure mode)',
        'short circuit'                 : 'Low impedance path, potential for overcurrent and damage (ISO 26262 safety impact)'
    },

    'diode': {
        'short circuit'                 : 'Bypass current path, potential for circuit failure or damage (ISO 26262 SPFM)',
        'open circuit'                  : 'No current flow, failure to rectify or clamp voltage (MIL-HDBK-217 base failure mode)',
        'reverse leakage'               : 'Increased leakage current, impacts efficiency and may lead to overheating (Birolini exponential distribution)'
    },

    'zener': {
        'short circuit'                 : 'Zener breakdown fails, leading to overvoltage protection loss (ISO 26262 Residual Risk)',
        'open circuit'                  : 'No voltage regulation, potential overvoltage condition (MIL-HDBK-217 base failure mode)',
        'drift high'                    : 'Zener voltage increases, may cause improper regulation or protection (Birolini Reliability Model)',
        'drift low'                     : 'Zener voltage decreases, leading to lower regulation point (Birolini Reliability Model)'
    },

    'schottky': {
        'short circuit'                 : 'Loss of rectification, potential circuit damage due to high reverse current (ISO 26262 SPFM)',
        'open circuit'                  : 'No current flow, failure to rectify or protect circuit (MIL-HDBK-217 base failure mode)',
        'reverse leakage'               : 'Higher leakage current, can lead to efficiency loss and overheating (Birolini exponential distribution)'
    },

    'transistor': {
        'open circuit'                  : 'Failure to switch, circuit malfunction (MIL-HDBK-217 base failure mode)',
        'short circuit'                 : 'Constant conduction, potential overcurrent, and damage (ISO 26262 LFM)',
        'gain degradation'              : 'Reduced performance due to aging or stress, impacts amplification (Birolini Reliability Model)',
        'drift high'                    : 'Increased gain, may cause overstressed circuit or incorrect amplification (Birolini Reliability Model)',
        'drift low'                     : 'Decreased gain, may result in insufficient signal amplification (Birolini Reliability Model)'
    },

    'IC': {
        'random hardware failure'       : 'Unexpected behavior due to material defects, may trigger safety mechanisms (ISO 26262)',
        'thermal failure'               : 'Overheating leads to degradation or permanent damage (Birolini Weibull model)',
        'ESD damage'                    : 'Electrostatic discharge causes permanent damage or malfunction (MIL-HDBK-217 base failure mode)',
        'pin floating'                  : 'Unconnected pin may cause unpredictable behavior or susceptibility to noise, leading to malfunction (ISO 26262)',
        'drift high'                    : 'Parameter drift (e.g., timing, threshold voltage) leading to improper operation (Birolini Reliability Model)',
        'drift low'                     : 'Parameter drift leading to reduced performance or incorrect functionality (Birolini Reliability Model)'
    },

    'transformer': {
        'open winding'                  : 'Loss of inductance and energy transfer, causing circuit malfunction or failure (MIL-HDBK-217 base failure mode)',
        'shorted turns'                 : 'Reduced inductance, increased current, potential overheating, and damage (ISO 26262 Residual Risk)',
        'core saturation'               : 'Increased magnetization, leading to waveform distortion and reduced efficiency (Birolini Reliability Model)',
        'insulation failure'            : 'Short circuits between windings or to core, leading to catastrophic failure (ISO 26262 safety impact)',
        'drift high'                    : 'Increased turns ratio or inductance, may affect voltage levels and circuit operation (Birolini Reliability Model)',
        'drift low'                     : 'Decreased turns ratio or inductance, may lead to insufficient voltage transformation and power delivery (Birolini Reliability Model)'
    },

    'op-amp': {
        'open loop gain degradation'    : 'Reduced gain affects the accuracy of amplification (ISO 26262 SPFM)',
        'input offset drift'            : 'Changes in input offset voltage lead to inaccuracies in output (Birolini Reliability Model)',
        'short circuit'                 : 'Potential damage to power supply or other components due to excessive current (MIL-HDBK-217 base failure mode)',
        'open circuit'                  : 'Loss of amplification, circuit malfunction (MIL-HDBK-217 base failure mode)'
    },

    'fuse': {
        'open circuit'                  : 'Protective function activated, breaking the circuit to prevent damage (MIL-HDBK-217 base failure mode)',
        'nuisance tripping'             : 'Premature opening due to transient conditions, leading to unnecessary downtime (ISO 26262 Residual Risk)',
        'failure to open'               : 'Fuse fails to break the circuit under fault conditions, leading to potential damage or fire (ISO 26262 safety impact)'
    },

    'relay': {
        'contact sticking'              : 'Contacts fail to open, causing continuous circuit connection and potential system failure (ISO 26262 Residual Risk)',
        'contact welding'               : 'High current causes contacts to weld together, leading to a permanent closed state (MIL-HDBK-217 base failure mode)',
        'coil failure'                  : 'Coil fails to energize, leading to a failure to switch the contacts (Birolini Reliability Model)',
        'contact bounce'                : 'Repeated opening and closing of contacts, causing erratic circuit behavior (ISO 26262 SPFM)'
    },

    'connector': {
        'contact resistance increase'   : 'Oxidation or contamination increases resistance, leading to voltage drops or overheating (MIL-HDBK-217 base failure mode)',
        'pin misalignment'              : 'Improper connection leads to open circuits or intermittent operation (ISO 26262 Residual Risk)',
        'pin corrosion'                 : 'Environmental factors cause corrosion, leading to poor contact and potential failure (Birolini Weibull model)',
        'mechanical failure'            : 'Physical damage or wear leads to loss of connectivity (MIL-HDBK-217 base failure mode)'
    },
    
    'LED': {
        'open circuit'                  : 'Loss of light emission, indicating a failure in the circuit (MIL-HDBK-217 base failure mode)',
        'lumen degradation'             : 'Gradual decrease in light output over time, leading to insufficient illumination (Birolini Weibull model)',
        'short circuit'                 : 'Excessive current may flow, causing damage to the LED or power supply (ISO 26262 SPFM)',
        'color shift'                   : 'Change in emitted color due to aging or temperature effects (Birolini Reliability Model)'
    }
}
#? -------------------------------------------------------------------------------  
