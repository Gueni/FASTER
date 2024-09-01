
#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?
#?                                   __  __
#?                      ____  ____ _/ /_/ /____  _________  _____
#?                     / __ \/ __ `/ __/ __/ _ \/ ___/ __ \/ ___/
#?                    / /_/ / /_/ / /_/ /_/  __/ /  / / / (__  )
#?                   / .___/\__,_/\__/\__/\___/_/  /_/ /_/____/
#?                  /_/
#?                  
#? Name:        patterns.py
#? Purpose:     Define regular expression patterns for various components
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------  
#? ------------------------------------------------------------------------------- 

import re

symbol_patterns = [

    re.compile(r'SYMBOL voltage (-?\d+) (-?\d+) R0'),               # Voltage Source
    re.compile(r'SYMBOL res (-?\d+) (-?\d+) R90'),                  # Resistor
    re.compile(r'SYMBOL cap (-?\d+) (-?\d+) R0'),                   # Capacitor
    re.compile(r'SYMBOL ind (-?\d+) (-?\d+) R0'),                   # Inductor
    re.compile(r'SYMBOL diode (-?\d+) (-?\d+) R90'),                # Diode
    re.compile(r'SYMBOL zener (-?\d+) (-?\d+) R90'),                # Zener Diode
    re.compile(r'SYMBOL schottky (-?\d+) (-?\d+) R90'),             # Schottky Diode
    re.compile(r'SYMBOL pnp (-?\d+) (-?\d+) R0'),                   # PNP Transistor
    re.compile(r'SYMBOL npn (-?\d+) (-?\d+) R0'),                   # NPN Transistor
    re.compile(r'SYMBOL opamp (-?\d+) (-?\d+) R0'),                 # Operational Amplifier
    re.compile(r'SYMBOL relay (-?\d+) (-?\d+) R0'),                 # Relay
    re.compile(r'SYMBOL led (-?\d+) (-?\d+) R0'),                   # LED
    re.compile(r'SYMBOL fuse (-?\d+) (-?\d+) R0'),                  # Fuse
    re.compile(r'SYMBOL connector (-?\d+) (-?\d+) R0'),             # Connector
    re.compile(r'SYMBOL transformer (-?\d+) (-?\d+) R0'),           # Transformer
    re.compile(r'SYMBOL Misc\\cell (-?\d+) (-?\d+) R0'),            # Battery Cell
    re.compile(r'SYMBOL [^\s]+ (-?\d+) (-?\d+) R0')                 # Generic symbol pattern
]
#? ------------------------------------------------------------------------------- 

component_type_map = {      # Define a dictionary to map keywords to component types
    'voltage'           : 'voltage'             ,
    'res'               : 'resistor'            ,
    'cap'               : 'capacitor'           ,
    'ind'               : 'inductor'            ,
    'diode'             : 'diode'               ,
    'zener'             : 'zener'               ,
    'schottky'          : 'schottky'            ,
    'pnp'               : 'transistor'          ,
    'npn'               : 'transistor'          ,
    'opamp'             : 'op-amp'              ,
    'relay'             : 'relay'               ,
    'led'               : 'LED'                 ,
    'fuse'              : 'fuse'                ,
    'connector'         : 'connector'           ,
    'transformer'       : 'transformer'         ,
    'U'                 : 'IC'                  ,   
    'cell'              : 'battery'                 
}
#? ------------------------------------------------------------------------------- 
