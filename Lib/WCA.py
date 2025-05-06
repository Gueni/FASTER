#!/usr/bin/env python
# coding=utf-8

import os
import json
import numpy as np
import matplotlib.pyplot as plt
from typing import Any, Tuple
import subprocess
import tempfile
import shutil
import ltspice

class LTspiceWCA:
    def __init__(self, ltspice_path=None):
        self.ltspice_path = ltspice_path or self._find_ltspice()
        self.temp_dir = tempfile.mkdtemp(prefix="wca_")
        self.results = {}
        
    def _find_ltspice(self):
        paths = [
            os.path.expandvars("%LOCALAPPDATA%/Programs/ADI/LTspice/LTspice.exe"),
            "C:/Program Files/ADI/LTspice/LTspice.exe",
            "C:/Program Files (x86)/ADI/LTspice/LTspice.exe"
        ]
        for path in paths:
            if os.path.exists(path):
                return os.path.normpath(path)
        raise FileNotFoundError("LTspice executable not found")

    def _parse_raw(self, raw_file: str) -> ltspice.Ltspice:
        """Parse LTspice raw file using ltspice library"""
        try:
            l = ltspice.Ltspice(raw_file)
            l.parse()  # Data loading sequence
            return l
        except Exception as e:
            print(f"Error parsing raw file with ltspice: {str(e)}")
            raise

    def run_analysis(self, circuit_path, config_path, show_plots=False):
        try:
            config = self._load_config(config_path)
            print(f"Analyzing {config['component_name']} (Nominal: {config['nominal_value']}, Tol: {config['tolerance']}%)")
            
            min_val, max_val = self._calc_limits(float(config['nominal_value']), 
                                               float(config['tolerance']), 
                                               config['analysis_type'])
            
            cases = {
                'nominal': config['nominal_value'],
                'min_case': min_val,
                'max_case': max_val
            }
            
            for case, value in cases.items():
                print(f"\nRunning {case} case ({value})...")
                mod_circuit = self._modify_circuit(circuit_path, config['component_name'], value)
                raw_file = self._run_simulation(mod_circuit)
                self.results[case] = self._parse_raw(raw_file)
            
            self._analyze_results(config.get('output_variables', ['V(out)']))
            self._generate_plots(show=show_plots)
            
            print("\nAnalysis complete!")
            return self.results
            
        except Exception as e:
            print(f"\nError 1: {str(e)}")
            raise
        finally:
            self.cleanup()

    def _load_config(self, config_path: str) -> dict[str, Any]:
        """Load and validate configuration file."""
        with open(config_path) as f:
            config = json.load(f)
        required = ['component_name', 'nominal_value', 'tolerance', 'analysis_type']
        if not all(key in config for key in required):
            raise ValueError("Missing required config keys")
        return config

    def _calc_limits(self, nominal: float, tolerance: float, analysis_type: str) -> Tuple[float, float]:
        """Calculate min/max values based on tolerance and analysis type."""
        if analysis_type == 'passive':
            return (nominal * (1 - tolerance/100), nominal * (1 + tolerance/100))
        elif analysis_type == 'active':
            return (nominal - tolerance, nominal + tolerance)
        raise ValueError("Invalid analysis_type")

    def _modify_circuit(self, circuit_path: str, component: str, value: float) -> str:
        """Modify component value in circuit file."""
        mod_path = os.path.join(self.temp_dir, os.path.basename(circuit_path))
        with open(circuit_path) as fin, open(mod_path, 'w') as fout:
            for line in fin:
                if line.startswith(component):
                    parts = line.split()
                    if len(parts) >= 4:
                        parts[3] = str(value)
                        line = ' '.join(parts) + '\n'
                fout.write(line)
        return mod_path

    def _run_simulation(self, circuit_path: str, timeout: float = 30.0) -> str:
        """Run LTspice simulation with timeout."""
        cmd = f'"{self.ltspice_path}" -Run -b "{circuit_path}"'
        try:
            subprocess.run(cmd, shell=True, check=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Simulation timed out after {timeout} seconds")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Simulation failed with return code {e.returncode}")
            
        raw_file = os.path.splitext(circuit_path)[0] + '.raw'
        if not os.path.exists(raw_file):
            raise FileNotFoundError(f"No output file: {raw_file}")
        return raw_file

    def _analyze_results(self, output_vars: list):
        """Analyze and compare simulation results."""
        analysis = {}
        for var in output_vars:
            nom = self.results['nominal'].get_data(var)
            min_d = self.results['min_case'].get_data(var)
            max_d = self.results['max_case'].get_data(var)

            # Compute deviations per sample
            delta_min = np.abs(min_d - nom)
            delta_max = np.abs(max_d - nom)

            # Identify worst-case
            if np.max(delta_min) > np.max(delta_max):
                worst_case = 'min_case'
                worst_variation = np.max(delta_min)
            else:
                worst_case = 'max_case'
                worst_variation = np.max(delta_max)

            nom_peak = np.max(np.abs(nom))
            analysis[var] = {
                'nominal_peak': nom_peak,
                'worst_variation': worst_variation,
                'percent_variation': (worst_variation / nom_peak * 100) if nom_peak != 0 else 0,
                'worst_case_source': worst_case
            }

            # Logging
            print(f"\n{var}:")
            print(f"  Nominal peak: {nom_peak:.4f}")
            print(f"  Worst variation: {worst_variation:.4f}")
            print(f"  Percentage: {analysis[var]['percent_variation']:.2f}%")
            print(f"  Caused by: {worst_case}")
            print(f"  Max |V_nom - V_max|: {np.max(np.abs(max_d - nom)):.16e}")
            print(f"  Max |V_nom - V_min|: {np.max(np.abs(min_d - nom)):.16e}")

        self.results['analysis'] = analysis

    def _generate_plots(self, show: bool = False):
        """Generate comparison plots."""
        if 'analysis' not in self.results:
            return
            
        for var in self.results['analysis']:
            plt.figure(figsize=(10, 5))
            
            # Get time vector if available
            time = self.results['nominal'].get_time() if self.results['nominal'].get_time() is not None else \
                   np.arange(len(self.results['nominal'].get_data(var)))
            
            plt.plot(time, self.results['nominal'].get_data(var), label='Nominal')
            plt.plot(time, self.results['min_case'].get_data(var), '--', label='Min Case')
            plt.plot(time, self.results['max_case'].get_data(var), '--', label='Max Case')
            
            plt.title(f'WCA: {var}')
            plt.xlabel('Time' if self.results['nominal'].get_time() is not None else 'Points')
            plt.ylabel(var)
            plt.legend()
            plt.grid(True)
            
            plot_path = os.path.join(self.temp_dir, f"{var.replace('(', '_').replace(')', '_')}.png")
            plt.savefig(plot_path)
            if show:
                plt.show()
            else:
                plt.close()
            print(f"Saved plot: {plot_path}")

    def cleanup(self):
        """Clean up temporary files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
