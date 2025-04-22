
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
#? Name:        WCA.py
#? Purpose:     Conduct Worst case analysis.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------  
#? ------------------------------------------------------------------------------- 

from PyLTSpice import AscEditor, SimRunner  
from PyLTSpice.sim.tookit.worst_case import WorstCaseAnalysis

import os
import json
import numpy as np
import matplotlib.pyplot as plt
import subprocess
import re
from typing import Dict, List, Tuple, Optional
import shutil
import tempfile

class LTspiceWorstCaseAnalyzer:
    def __init__(self, ltspice_circuit_path: str, json_config_path: str):
        """
        Initialize the analyzer with LTspice circuit and JSON configuration.
        
        Args:
            ltspice_circuit_path: Path to the .asc LTspice circuit file
            json_config_path: Path to the JSON configuration file
        """
        self.circuit_path = ltspice_circuit_path
        self.json_config_path = json_config_path
        self.temp_dir = tempfile.mkdtemp()
        self.load_config()
        
    def load_config(self):
        """Load the JSON configuration file."""
        with open(self.json_config_path, 'r') as f:
            self.config = json.load(f)
        
        # Validate config
        required_keys = ['component_name', 'nominal_value', 'tolerance', 
                         'analysis_type', 'simulation_command']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required key in config: {key}")
    
    def parse_circuit(self) -> Dict[str, str]:
        """Parse the LTspice circuit file and extract components."""
        components = {}
        with open(self.circuit_path, 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            if line.startswith(('R', 'C', 'L', 'D', 'Q')):  # Add other components as needed
                parts = line.strip().split()
                if len(parts) >= 4:
                    comp_id = parts[0]
                    comp_value = parts[3]
                    components[comp_id] = comp_value
        
        return components
    
    def modify_component_value(self, value: float) -> str:
        """
        Modify the circuit file with the new component value.
        
        Args:
            value: New value for the component
            
        Returns:
            Path to the modified circuit file
        """
        modified_path = os.path.join(self.temp_dir, os.path.basename(self.circuit_path))
        
        with open(self.circuit_path, 'r') as f_in, open(modified_path, 'w') as f_out:
            for line in f_in:
                if line.startswith(self.config['component_name']):
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        parts[3] = str(value)
                        line = ' '.join(parts) + '\n'
                f_out.write(line)
        
        return modified_path
    
    def run_ltspice_simulation(self, circuit_file: str) -> str:
        """
        Run LTspice simulation and return the path to the output file.
        
        Args:
            circuit_file: Path to the circuit file to simulate
            
        Returns:
            Path to the .raw output file
        """
        # Get LTspice executable path (modify as needed for your system)
        ltspice_exe = "C:\\Program Files\\LTC\\LTspiceXVII\\XVIIx64.exe"
        
        # Create output directory
        output_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        
        # Run LTspice in batch mode
        cmd = f'"{ltspice_exe}" -Run -b "{circuit_file}"'
        try:
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"LTspice simulation failed: {e.stderr.decode()}")
            raise
        
        # Find the output .raw file
        base_name = os.path.splitext(os.path.basename(circuit_file))[0]
        raw_file = os.path.join(os.path.dirname(circuit_file), f"{base_name}.raw")
        
        if not os.path.exists(raw_file):
            raise FileNotFoundError(f"Simulation output file not found: {raw_file}")
        
        # Move to output directory
        dest_raw = os.path.join(output_dir, os.path.basename(raw_file))
        shutil.move(raw_file, dest_raw)
        
        return dest_raw
    
    def parse_simulation_results(self, raw_file: str) -> Dict[str, np.ndarray]:
        """
        Parse LTspice .raw output file.
        
        Args:
            raw_file: Path to the .raw file
            
        Returns:
            Dictionary with variable names as keys and numpy arrays as values
        """
        # This is a simplified parser - consider using PyLTSpice or other libraries for robust parsing
        results = {}
        
        with open(raw_file, 'rb') as f:
            # Skip header (this is a simplified approach)
            for line in f:
                if line.startswith(b'Variables:'):
                    break
            
            # Read variable names
            variables = []
            for line in f:
                if line.startswith(b'Values:'):
                    break
                parts = line.strip().split()
                if len(parts) >= 3:
                    variables.append(parts[2].decode())
            
            # Read data (simplified - assumes binary format)
            # In practice, you'd need to properly parse the binary format
            data = np.fromfile(f, dtype=np.float64)
            
        # Reshape data based on number of variables
        # This is very simplified - actual parsing would need to handle the .raw format properly
        num_points = len(data) // len(variables)
        data = data.reshape((num_points, len(variables)))
        
        for i, var in enumerate(variables):
            results[var] = data[:, i]
        
        return results
    
    def calculate_worst_case_values(self) -> Tuple[float, float]:
        """
        Calculate worst case values based on nominal value and tolerance.
        
        Returns:
            Tuple of (min_value, max_value)
        """
        nominal = float(self.config['nominal_value'])
        tolerance = float(self.config['tolerance'])
        
        if self.config['analysis_type'] == 'passive':
            min_val = nominal * (1 - tolerance/100)
            max_val = nominal * (1 + tolerance/100)
        elif self.config['analysis_type'] == 'active':
            # Different calculation for active components
            min_val = nominal - tolerance
            max_val = nominal + tolerance
        else:
            raise ValueError(f"Unknown analysis type: {self.config['analysis_type']}")
        
        return min_val, max_val
    
    def analyze_results(self, nominal_results: Dict[str, np.ndarray],
                      min_results: Dict[str, np.ndarray],
                      max_results: Dict[str, np.ndarray]) -> Dict[str, Dict[str, float]]:
        """
        Analyze simulation results and calculate variations.
        
        Args:
            nominal_results: Results from nominal value simulation
            min_results: Results from minimum value simulation
            max_results: Results from maximum value simulation
            
        Returns:
            Dictionary with analysis results
        """
        analysis = {}
        
        # Get the output variable(s) to analyze from config
        output_vars = self.config.get('output_variables', ['V(out)'])
        
        for var in output_vars:
            if var not in nominal_results:
                continue
                
            nominal = nominal_results[var]
            min_val = min_results[var]
            max_val = max_results[var]
            
            # Calculate key metrics
            max_diff_pos = np.max(np.abs(max_val - nominal))
            max_diff_neg = np.max(np.abs(min_val - nominal))
            worst_case = max(max_diff_pos, max_diff_neg)
            
            analysis[var] = {
                'nominal_peak': np.max(np.abs(nominal)),
                'min_case_peak': np.max(np.abs(min_val)),
                'max_case_peak': np.max(np.abs(max_val)),
                'worst_case_variation': worst_case,
                'percent_variation': (worst_case / np.max(np.abs(nominal))) * 100
            }
        
        return analysis
    
    def plot_results(self, nominal_results: Dict[str, np.ndarray],
                    min_results: Dict[str, np.ndarray],
                    max_results: Dict[str, np.ndarray]):
        """
        Plot simulation results for comparison.
        """
        output_vars = self.config.get('output_variables', ['V(out)'])
        
        for var in output_vars:
            if var not in nominal_results:
                continue
                
            plt.figure(figsize=(10, 6))
            
            # Assume time is the first variable (simplified)
            time = nominal_results.get('time', np.arange(len(nominal_results[var])))
            
            plt.plot(time, nominal_results[var], label='Nominal', linewidth=2)
            plt.plot(time, min_results[var], '--', label='Min Case')
            plt.plot(time, max_results[var], '--', label='Max Case')
            
            plt.title(f'Worst Case Analysis: {var}')
            plt.xlabel('Time (s)')
            plt.ylabel(var)
            plt.legend()
            plt.grid(True)
            
            plot_path = os.path.join(self.temp_dir, f"{var.replace('(', '_').replace(')', '_')}_plot.png")
            plt.savefig(plot_path)
            plt.close()
            
            print(f"Plot saved to {plot_path}")
    
    def run_analysis(self):
        """Run the complete worst case analysis workflow."""
        print("Starting worst case analysis...")
        
        # 1. Calculate worst case values
        min_val, max_val = self.calculate_worst_case_values()
        print(f"Component: {self.config['component_name']}")
        print(f"Nominal value: {self.config['nominal_value']}")
        print(f"Min case value: {min_val}")
        print(f"Max case value: {max_val}")
        
        # 2. Run simulations for all cases
        print("\nRunning simulations...")
        
        # Nominal case
        print("- Running nominal case...")
        nominal_circuit = self.modify_component_value(self.config['nominal_value'])
        nominal_raw = self.run_ltspice_simulation(nominal_circuit)
        nominal_results = self.parse_simulation_results(nominal_raw)
        
        # Min case
        print("- Running min case...")
        min_circuit = self.modify_component_value(min_val)
        min_raw = self.run_ltspice_simulation(min_circuit)
        min_results = self.parse_simulation_results(min_raw)
        
        # Max case
        print("- Running max case...")
        max_circuit = self.modify_component_value(max_val)
        max_raw = self.run_ltspice_simulation(max_circuit)
        max_results = self.parse_simulation_results(max_raw)
        
        # 3. Analyze results
        print("\nAnalyzing results...")
        analysis = self.analyze_results(nominal_results, min_results, max_results)
        
        for var, stats in analysis.items():
            print(f"\nVariable: {var}")
            for stat, value in stats.items():
                print(f"{stat.replace('_', ' ').title()}: {value:.4f}")
        
        # 4. Plot results
        print("\nGenerating plots...")
        self.plot_results(nominal_results, min_results, max_results)
        
        print("\nAnalysis complete!")
    
    def cleanup(self):
        """Clean up temporary files."""
        shutil.rmtree(self.temp_dir)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='LTspice Worst Case Analysis Tool')
    parser.add_argument('circuit_file', help='Path to LTspice .asc circuit file')
    parser.add_argument('config_file', help='Path to JSON configuration file')
    
    args = parser.parse_args()
    
    analyzer = LTspiceWorstCaseAnalyzer(args.circuit_file, args.config_file)
    try:
        analyzer.run_analysis()
    finally:
        analyzer.cleanup()
        

# def worst_case(asc_file,netlist_path,results_path,netlist_file):

#     asc_file    = AscEditor(asc_file)                       # Reads the asc file into memory
#     runner      = SimRunner(output_folder=netlist_path)     # Instantiates the runner class, with the output folder already set
#     wca         = WorstCaseAnalysis(asc_file, runner)       # Instantiates the Worst Case Analysis class

#     # Set the default tolerances for the components
#     wca.set_tolerance('R', 0.01)  # 1% tolerance
#     wca.set_tolerance('C', 0.1)  # 10% tolerance
#     # wca.set_tolerance('V', 0.1)  # 10% tolerance. For Worst Case analysis, the distribution is irrelevant

#     # Some components can have a different tolerance
#     # wca.set_tolerance('R1', 0.05)  # 5% tolerance for R1 only. This only overrides the default tolerance for R1

#     # Tolerances can be set for parameters as well.
#     # wca.set_parameter_deviation('Vos', 3e-4, 5e-3)

#    # Finally the netlist is saved to a file
#     wca.save_netlist(netlist_file)

#     wca.run_testbench()  # Runs the simulation with splits of 100 runs each

#     logs = wca.read_logfiles()   # Reads the log files and stores the results in the results attribute
#     logs.export_data(results_path)  # Exports the data to a csv file

#     # print("Worst case results:")
#     # for param in ('fcut', 'fcut_FROM'):
#     #     print(f"{param}: min:{logs.min_measure_value(param)} max:{logs.max_measure_value(param)}")

#     wca.cleanup_files()  # Deletes the temporary files
    
#? ------------------------------------------------------------------------------- 
