
#?---------------------------------------------------------------------------------------------------------------------------
import parse_ltspice_file 
import FMEDA
import tkinter as tk
from tkinter import filedialog
import pandas as pd
import time
from pathlib import Path
import sys ,os
import FTA
import FIT_rates
import clear
import genreport
import WCA
#?---------------------------------------------------------------------------------------------------------------------------
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
#?---------------------------------------------------------------------------------------------------------------------------
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
    clear.delete_files_in_folder(res_dir)

    file_name               = f"FMEDA_{Path(schematic_file_path).stem}_{int(time.time())}.xlsx"
    file_path               = os.path.join(res_dir, file_name)
    
    df.to_excel(file_path, index=False, engine='openpyxl')
    
    fmeda_report            = pd.read_excel(file_path)  # Update with actual path if needed
    fault_tree              = FTA.build_fault_tree(circuit_data, fmeda_report)
    fta_results             = FTA.analyze_fault_tree(fault_tree,FIT_rates.fit_rates)
    raw_file                = "D:/4 WORKSPACE/FASTER/FASTER/assets/Test.raw"
    FTA.save_fta_results(fta_results, "Test")  
    genreport.generate_report(raw_file,schematic_file_path)
    netlist_path                = "D:/4 WORKSPACE/FASTER/FASTER/RES/tempo"
    results_path                = "D:/4 WORKSPACE/FASTER/FASTER/assets/Test.csv"
    netlist_file                = "D:/4 WORKSPACE/FASTER/FASTER/RES/tempo/Test_wc.asc"
    WCA.worst_case(schematic_file_path,netlist_path,results_path,netlist_file)
    # FTA.visualize_fta(fta_results, output_file='FTA_diagram')
#?---------------------------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    main()
#?---------------------------------------------------------------------------------------------------------------------------
