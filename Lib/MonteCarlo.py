import random
import subprocess
import os
import plotly.graph_objects as go
import csv
from datetime import datetime
from PyLTSpice import SimRunner, AscEditor

class MonteCarloSimulation:
    def __init__(self, circuit_file, output_dir, **component_tolerances):
        self.circuit_file = circuit_file
        self.output_dir = output_dir
        self.component_tolerances = component_tolerances
        self.LTC = self._initialize_sim_runner(output_dir)

    def _initialize_sim_runner(self, output_dir):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        return SimRunner(output_folder=output_dir)

    def _run_simulation(self, modified_circuit_file):
        try:
            cmd = f'"C:/Users/Mohamed Gueni/AppData/Local/Programs/ADI/LTspice/LTspice.exe" -Run -b "{modified_circuit_file}"'
            subprocess.run(cmd, shell=True, check=True, timeout=600)
            return modified_circuit_file
        except subprocess.CalledProcessError as e:
            print(f"Simulation failed: {e}")
            return None

    def _generate_random_component_value(self, nominal_value, tolerance):
        min_value = nominal_value * (1 - tolerance)
        max_value = nominal_value * (1 + tolerance)
        return random.uniform(min_value, max_value)

    def monte_carlo_simulation(self, num_simulations=1000):
        all_results = []

        for i in range(num_simulations):
            print(f"Running simulation {i + 1}/{num_simulations}...")

            modified_circuit_file = self._modify_circuit_file()

            if self._run_simulation(modified_circuit_file):
                result_data = self._extract_result_data(modified_circuit_file)
                all_results.append(result_data)

        self._save_to_csv(all_results)
        return all_results

    def _modify_circuit_file(self):
        netlist = AscEditor(self.circuit_file)
        component_list = []

        for component, tolerance in self.component_tolerances.items():
            nominal = self._get_nominal_value_for_component(component)
            value = self._generate_random_component_value(nominal, tolerance)
            component_list.append((component, value))

        for component, value in component_list:
            netlist.set_component_value(component, value)

        temp_file = f"C:/Users/Mohamed Gueni/AppData/Local/Temp/{os.path.basename(self.circuit_file)}"
        netlist.save_netlist(temp_file)
        return temp_file

    def _get_nominal_value_for_component(self, component):
        nominal_values = {
            "R1": 1000,
            "R2": 100,
        }
        return nominal_values.get(component, 0)

    def _extract_result_data(self, result_file):
        # Placeholder: Replace this with real data extraction
        time = [i * 0.01 for i in range(100)]
        voltage = [random.uniform(0, 10) for _ in range(100)]
        return {'time': time, 'voltage': voltage}

    def _save_to_csv(self, all_results):
        utc_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(self.output_dir, f"montecarlo_results_{utc_str}.csv")

        if not all_results:
            print("No results to save.")
            return

        # Assume all have the same time axis
        time = all_results[0]['time']
        header = ['Time'] + [f"Simulation_{i+1}" for i in range(len(all_results))]
        rows = zip(
            time,
            *[res['voltage'] for res in all_results]
        )

        with open(filename, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

        print(f"Results saved to {filename}")

    def plot_simulation_results(self, results):
        fig = go.Figure()

        for i, result in enumerate(results):
            fig.add_trace(go.Scatter(
                x=result['time'],
                y=result['voltage'],
                mode='lines',
                name=f"Simulation {i + 1}"
            ))

        fig.update_layout(
            title="Monte Carlo Simulation Results",
            xaxis_title="Time (s)",
            yaxis_title="Voltage (V)",
            legend_title="Simulations",
        )
        return fig

