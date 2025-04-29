#!/usr/bin/env python
# coding=utf-8

import os
import json
import numpy as np
import matplotlib.pyplot as plt
import subprocess
import tempfile
import shutil

class LTspiceWCA:
    def __init__(self, ltspice_path=None):
        self.ltspice_path = ltspice_path or self._find_ltspice()
        self.temp_dir = tempfile.mkdtemp(prefix="wca_")
        self.results = {}
        
    def _find_ltspice(self):
        paths = [
            "C:/Users/Mohamed Gueni/AppData/Local/Programs/ADI/LTspice/LTspice.exe",
            "C:/Program Files/ADI/LTspice/LTspice.exe"
        ]
        for path in paths:
            if os.path.exists(path):
                return path
        raise FileNotFoundError("LTspice executable not found")

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
            print(f"\nError: {str(e)}")
            raise
        finally:
            self.cleanup()

    def _load_config(self, config_path):
        with open(config_path) as f:
            config = json.load(f)
        required = ['component_name', 'nominal_value', 'tolerance', 'analysis_type']
        if not all(key in config for key in required):
            raise ValueError("Missing required config keys")
        return config

    def _calc_limits(self, nominal, tolerance, analysis_type):
        if analysis_type == 'passive':
            return (nominal * (1 - tolerance/100), nominal * (1 + tolerance/100))
        elif analysis_type == 'active':
            return (nominal - tolerance, nominal + tolerance)
        raise ValueError("Invalid analysis_type")

    def _modify_circuit(self, circuit_path, component, value):
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

    def _run_simulation(self, circuit_path):
        cmd = f'"{self.ltspice_path}" -Run -b "{circuit_path}"'
        try:
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Simulation failed: {e.stderr.decode()}")
            raise
            
        raw_file = os.path.splitext(circuit_path)[0] + '.raw'
        if not os.path.exists(raw_file):
            raise FileNotFoundError(f"No output file: {raw_file}")
        return raw_file

    def _parse_raw(self, raw_file):
        data = {}
        with open(raw_file, 'rb') as f:
            while not f.readline().startswith(b'Variables:'):
                pass
                
            vars = []
            while True:
                line = f.readline()
                if line.startswith(b'Binary:') or not line.strip():
                    break
                parts = line.split()
                if len(parts) >= 3:
                    vars.append((int(parts[0]), parts[1].decode(), parts[2].decode()))
            
            arr = np.frombuffer(f.read(), dtype=np.float64)
            arr = arr.reshape((len(arr)//len(vars), len(vars)))
            for i, var in enumerate(vars):
                data[var[1]] = arr[:, i]
        return data

    def _analyze_results(self, output_vars):
        analysis = {}
        for var in output_vars:
            if var not in self.results['nominal']:
                continue
                
            nom = self.results['nominal'][var]
            min_d = self.results['min_case'][var]
            max_d = self.results['max_case'][var]
            
            diff = max(np.max(np.abs(max_d - nom)), np.max(np.abs(min_d - nom)))
            
            analysis[var] = {
                'nominal': np.max(np.abs(nom)),
                'variation': max(diff),
                'percent': max(diff)/np.max(np.abs(nom))*100 if np.max(np.abs(nom)) != 0 else 0
            }
            
            print(f"\n{var}:")
            print(f"  Nominal peak: {analysis[var]['nominal']:.4f}")
            print(f"  Worst variation: {analysis[var]['variation']:.4f}")
            print(f"  Percentage: {analysis[var]['percent']:.2f}%")
        
        self.results['analysis'] = analysis

    def _generate_plots(self, show=False):
        if 'analysis' not in self.results:
            return
            
        for var in self.results['analysis']:
            plt.figure(figsize=(10, 5))
            x = self.results['nominal'].get('time', range(len(self.results['nominal'][var])))
            
            plt.plot(x, self.results['nominal'][var], label='Nominal')
            plt.plot(x, self.results['min_case'][var], '--', label='Min Case')
            plt.plot(x, self.results['max_case'][var], '--', label='Max Case')
            
            plt.title(f'WCA: {var}')
            plt.xlabel('Time' if 'time' in self.results['nominal'] else 'Points')
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
        shutil.rmtree(self.temp_dir, ignore_errors=True)

def main():
    circuit = "D:/WORKSPACE/FASTER/FASTER/assets/testfiles/Test.asc"
    config = "D:/WORKSPACE/FASTER/FASTER/Lib/cmpt.json"
    ltspice = "C:/Users/Mohamed Gueni/AppData/Local/Programs/ADI/LTspice/LTspice.exe"
    
    analyzer = LTspiceWCA(ltspice)
    try:
        results = analyzer.run_analysis(circuit, config, show_plots=True)
    except Exception as e:
        print(f"Analysis failed: {e}")

if __name__ == "__main__":
    main()