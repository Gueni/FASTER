
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
#? Name:        main.py
#? Purpose:     Define the main routine.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------  
#? ------------------------------------------------------------------------------- 

import sys
import os

# Add the parent directory (project_root) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import parse_ltspice_file 
import FMEDA
import tkinter as tk
from tkinter import filedialog
import pandas as pd
import time
from pathlib import Path
import FTA
from assets import FIT_rates
import clear
import genreport
from WCA import LTspiceWCA  # Import LTspiceWCA from the appropriate module
from MonteCarlo import MonteCarloSimulation

def select_file():
    root            = tk.Tk()
    root.withdraw()  
    file_path       = filedialog.askopenfilename(
        title       ="Select a .asc File",
        filetypes   =[("SPICE Files", "*.asc"), ("All Files", "*.*")]
    )
    if not file_path:  # User canceled the dialog
        print("No file selected.")
        sys.exit()
    return file_path

def main():
    """
    Runs FMEDA analysis based on the LTSpice schematic file and saves results to an Excel file.
    """
    
    schematic_file_path     = select_file()
    circuit_data            = parse_ltspice_file.parse_ltspice_file(schematic_file_path) # Parse the schematic file
    components              = circuit_data['components']
    failure_modes           = FMEDA.analyze_failure_modes(components) # Analyze failure modes
    data                    = [] # Prepare data for Excel

    for component, modes in failure_modes.items():
        for mode, impact in modes.items():
            data.append([component, mode, impact])
    
    df                      = pd.DataFrame(data, columns=['Component', 'Failure Mode', 'General Failure Effect'])
    current_dir             = os.getcwd()
    res_dir                 = os.path.join(current_dir, 'RES')
    
    if not os.path.exists(res_dir):
        os.makedirs(res_dir)
    clear.clear_all()

    file_name               = f"FMEDA_{Path(schematic_file_path).stem}_{int(time.time())}.xlsx"
    file_path               = os.path.join(res_dir, file_name)
    
    df.to_excel(file_path, index=False, engine='openpyxl')
    
    fmeda_report            = pd.read_excel(file_path)  # Update with actual path if needed
    fault_tree              = FTA.build_fault_tree(circuit_data, fmeda_report)
    fta_results             = FTA.analyze_fault_tree(fault_tree,FIT_rates.fit_rates)
    raw_file                = "D:/WORKSPACE/FASTER/FASTER/assets/testfiles/Test.raw"
    FTA.save_fta_results(fta_results, "Test")  
    try:
        circuit = os.path.normpath("D:/WORKSPACE/FASTER/FASTER/assets/testfiles/Test.asc")
        config = os.path.normpath("D:/WORKSPACE/FASTER/FASTER/Lib/cmpt.json")
        
        analyzer = LTspiceWCA()
        results = analyzer.run_analysis(circuit, config, show_plots=True)
    except Exception as e:
        print(f"Analysis failed: {e}")
        return 1
    output_dir = r'D:\WORKSPACE\FASTER\FASTER\RES'

    component_tolerances = {
        "R1": 0.05,
        "R2": 0.10,
    }

    mc_sim = MonteCarloSimulation(circuit, output_dir, **component_tolerances)
    results = mc_sim.monte_carlo_simulation(num_simulations=10)
    fig = mc_sim.plot_simulation_results(results)
    genreport.generate_report(fig,raw_file,schematic_file_path)
#? ------------------------------------------------------------------------------- 
if __name__ == '__main__':
    main()
#? ------------------------------------------------------------------------------- 
