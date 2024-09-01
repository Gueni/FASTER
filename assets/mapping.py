
#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?
#?                 ____ ___  ____ _____  ____  (_)___  ____ _
#?                / __ `__ \/ __ `/ __ \/ __ \/ / __ \/ __ `/
#?               / / / / / / /_/ / /_/ / /_/ / / / / / /_/ / 
#?              /_/ /_/ /_/\__,_/ .___/ .___/_/_/ /_/\__, /  
#?                             /_/   /_/            /____/    
#?      
#?
#? Name:        mapping.py
#? Purpose:     Define the mapping of designator prefixes to component types
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------  
#? -------------------------------------------------------------------------------  

component_mapping = {

                        'V'             : 'voltage',
                        'R'             : 'resistor',
                        'C'             : 'capacitor',
                        'L'             : 'inductor',
                        'D'             : 'diode',
                        'U'             : 'IC',
                        'Q'             : 'transistor',
                        'T'             : 'transformer',
                        'O'             : 'op-amp',
                        'F'             : 'fuse',
                        'M'             : 'relay',
                        'N'             : 'connector',
                        'LED'           : 'LED'
    }
#? -------------------------------------------------------------------------------  
