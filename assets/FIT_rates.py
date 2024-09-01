
#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?
#?              ________________   ____  ___  _________________
#?             / ____/  _/_  __/  / __ \/   |/_  __/ ____/ ___/
#?            / /_   / /  / /    / /_/ / /| | / / / __/  \__ \ 
#?           / __/ _/ /  / /    / _, _/ ___ |/ / / /___ ___/ / 
#?          /_/   /___/ /_/    /_/ |_/_/  |_/_/ /_____//____/  
#?      
#?
#? Name:        FIT_rates.py
#? Purpose:     Define FIT Rates for various components
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------  
#? -------------------------------------------------------------------------------   

fit_rates = {
                'voltage'                           : {
                    'value change'                  : 5  
                                                    },
                'resistor'                          : {
                    'open circuit'                  : 15,
                    'short circuit'                 : 10,
                    'drift high'                    : 7,
                    'drift low'                     : 8
                                                    },
                'capacitor'                         : {
                    'open circuit'                  : 20,
                    'short circuit'                 : 12,
                    'drift high'                    : 9,
                    'drift low'                     : 10
                                                    },
                'inductor'                          : {
                    'value drift'                   : 11,
                    'drift high'                    : 6,
                    'drift low'                     : 7,
                    'open circuit'                  : 16,
                    'short circuit'                 : 13
                                                    },
                'diode'                             : {
                    'short circuit'                 : 14,
                    'open circuit'                  : 9,
                    'reverse leakage'               : 8
                                                    },
                'zener'                             : {
                    'short circuit'                 : 12,
                    'open circuit'                  : 11,
                    'drift high'                    : 5,
                    'drift low'                     : 6
                                                    },
                'schottky'                          : {
                    'short circuit'                 : 15,
                    'open circuit'                  : 10,
                    'reverse leakage'               : 9
                                                    },
                'transistor'                        : {
                    'open circuit'                  : 18,
                    'short circuit'                 : 14,
                    'gain degradation'              : 6,
                    'drift high'                    : 7,
                    'drift low'                     : 8
                                                    },
                'IC'                                : {
                    'random hardware failure'       : 22,
                    'thermal failure'               : 17,
                    'ESD damage'                    : 13,
                    'pin floating'                  : 11,
                    'drift high'                    : 9,
                    'drift low'                     : 10
                                                    },
                'transformer'                       : {
                    'open winding'                  : 14,
                    'shorted turns'                 : 12,
                    'core saturation'               : 8,
                    'insulation failure'            : 11,
                    'drift high'                    : 6,
                    'drift low'                     : 7
                                                    },
                'op-amp'                            : {
                    'open loop gain degradation'    : 8,
                    'input offset drift'            : 9,
                    'short circuit'                 : 12,
                    'open circuit'                  : 11
                                                    },
                'fuse'                              : {
                    'open circuit'                  : 16,
                    'nuisance tripping'             : 10,
                    'failure to open'               : 15
                                                    },
                'relay'                             : {
                    'contact sticking'              : 18,
                    'contact welding'               : 14,
                    'coil failure'                  : 12,
                    'contact bounce'                : 9
                                                    },
                'connector'                         : {
                    'contact resistance increase'   : 13,
                    'pin misalignment'              : 11,
                    'pin corrosion'                 : 10,
                    'mechanical failure'            : 14
                                                    },
                'LED'                               : {
                    'open circuit'                  : 9,
                    'lumen degradation'             : 8,
                    'short circuit'                 : 11,
                    'color shift'                   : 7
                }
            }
#? ------------------------------------------------------------------------------- 
