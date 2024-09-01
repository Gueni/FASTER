
#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                          ________  _____________  ___ 
#?                         / ____/  |/  / ____/ __ \/   |
#?                        / /_  / /|_/ / __/ / / / / /| |
#?                       / __/ / /  / / /___/ /_/ / ___ |
#?                      /_/   /_/  /_/_____/_____/_/  |_|
#?                      
#?
#? Name:        FMEDA.py
#? Purpose:     Define failure modes for the components.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------  
#? ------------------------------------------------------------------------------- 

import assets.Failures as Failures 

def analyze_failure_modes(components):

    failure_modes       = {}
    component_failures  = Failures.component_failures
    for comp in components:
        comp_name       = comp['name']
        comp_type       = comp['type']
        if comp_type in component_failures:
            failure_modes[comp_name] = component_failures[comp_type]

    return failure_modes

#? ------------------------------------------------------------------------------- 
