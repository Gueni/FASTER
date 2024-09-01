import os
import pandas as pd
from datetime import datetime
import mapping

def get_component_type(designator):
    
    prefix = designator[0]
    return mapping.component_mapping.get(prefix, 'Unknown')

def build_fault_tree(circuit_data, fmeda_report):
    fault_tree = {}
    for comp in circuit_data['components']:
        comp_name = comp['name']
        if comp_name in fmeda_report['Component'].values:
            failure_modes = fmeda_report.loc[fmeda_report['Component'] == comp_name, 'Failure Mode'].tolist()
            impacts = fmeda_report.loc[fmeda_report['Component'] == comp_name, 'General Failure Effect'].tolist()
            fault_tree[comp_name] = dict(zip(failure_modes, impacts))
    
    return fault_tree

def analyze_fault_tree(fault_tree, fit_rates):
    analysis_results = {}
    print(fault_tree)
    for component, failures in fault_tree.items():
        print(f"Processing component: {component}")  # Debugging
        component = get_component_type(component)
        print(str(component))
        component_fit_rates = fit_rates.get(component, {})
        
        if not component_fit_rates:
            print(f"No FIT rates found for component: {component}")  # Debugging
            continue
        
        total_fit = sum(component_fit_rates.values())
        
        if total_fit == 0:
            print(f"Total FIT rate is zero for component: {component}")  # Debugging
            continue
        
        failure_details = {}
        for failure_mode, impact in failures.items():
            print(f"Processing failure mode: {failure_mode}")  # Debugging
            failure_fit = component_fit_rates.get(failure_mode, 0)
            probability = failure_fit / total_fit if total_fit > 0 else 0
            percentage = probability * 100
            failure_details[failure_mode] = {
                'Impact': impact,
                'FIT Rate': failure_fit,
                'Probability': probability,
                'Percentage': percentage
            }
        
        analysis_results[component] = {
            'Component': component,
            'Total FIT': total_fit,
            'Failure Details': failure_details
        }
    
    # Adding overall FIT rate and percentage
    overall_fit = sum(fit for component_fit_rates in fit_rates.values() for fit in component_fit_rates.values())
    analysis_results['Overall'] = {
        'Total FIT': overall_fit,
        'Failure Modes': len(fault_tree),
        'Failure Details': 'N/A'
    }
    
    return analysis_results

def save_fta_results(fta_results, circuit_file_name):
    """
    Save the FTA results to an Excel file.

    Args:
        fta_results (dict): The FTA analysis results.
        circuit_file_name (str): The base name of the circuit file.
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_name = f"FTA_{circuit_file_name}_{timestamp}.xlsx"
   # Get the current working directory
    current_dir = os.getcwd()
    # Define the directory for saving files
    res_dir = os.path.join(current_dir, 'RES')
    if not os.path.exists(res_dir):
        os.makedirs(res_dir)
    
    file_path = os.path.join(res_dir, file_name)
    
    # Convert FTA results to a DataFrame
    fta_df = pd.DataFrame.from_dict(fta_results, orient='index')
    
    # Save to Excel
    fta_df.to_excel(file_path)
    print(f"FTA results saved to {file_path}")