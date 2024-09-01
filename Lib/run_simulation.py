
#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                                  _______________ 
#?                                 / ____/_  __/   |
#?                                / /_    / / / /| |
#?                               / __/   / / / ___ |
#?                              /_/     /_/ /_/  |_|
#?                              
#?
#? Name:        run_simulation.py
#? Purpose:     Run simulation.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------  
#? ------------------------------------------------------------------------------- 

from PyLTSpice import SpiceEditor
ltspice_file = 'D:/4 WORKSPACE/FASTER/FASTER/assets/DC sweep.asc'
se = SpiceEditor(ltspice_file)

se.set_component_value('R1', 11000)


se.save_netlist("./testfiles/Noise_updated.net")
se.run()
    
#? ------------------------------------------------------------------------------- 
   