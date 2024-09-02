
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

from PyLTSpice import SimRunner
from PyLTSpice import AscEditor
import itertools
import tkinter as tk

def generate_component_tuples(**components):
    """
    Generate a list of tuples for each component and its values.

    This function accepts multiple lists as keyword arguments, where each argument name 
    represents a component (e.g., 'R1', 'C3') and the argument value is a list of 
    possible values for that component. It returns a dictionary where the keys are 
    the component names and the values are lists of tuples containing the component 
    name and each possible value.

    Parameters:
    -----------
    **components : dict
        Keyword arguments where the keys are component names (str) and the values 
        are lists of component values.

    Returns:
    --------
    dict
        A dictionary where each key is a component name and the value is a list of 
        tuples (component_name, value) for each possible value.
    """
    
    result = {}
    
    # Iterate over each component and its corresponding values
    for component_name, values in components.items():
        # Create a list of tuples for the component
        result[component_name] = [(component_name, value) for value in values]
    
    return result

def generate_all_combinations(**components):
    """
    Generate all possible combinations of component names and their values.

    This function accepts multiple lists as keyword arguments, where each argument name 
    represents a component (e.g., 'R1', 'C3') and the argument value is a list of 
    possible values for that component. It returns a list of lists, where each inner 
    list contains tuples representing one possible combination of component names and values.

    Parameters:
    -----------
    **components : dict
        Keyword arguments where the keys are component names (str) and the values 
        are lists of component values.

    Returns:
    --------
    list of lists
        A list where each element is a list of tuples representing one possible combination 
        of the components and their values.
    """
    
    # Create a list of all component names
    component_names = list(components.keys())
    
    # Create a list of all value lists for the components
    value_lists = list(components.values())
    
    # Generate the Cartesian product of all the value lists
    all_combinations = list(itertools.product(*value_lists))
    
    # Convert the Cartesian product into a list of lists of tuples
    result = []
    for combination in all_combinations:
        result.append(list(zip(component_names, combination)))
    
    return result

def LTC_runner(output_dir):
    """
    Initialize the LTSpice simulation runner with the specified output directory.

    This function creates and returns a `SimRunner` object configured to store 
    simulation results in the given output directory.

    Parameters:
    -----------
    output_dir : str
        The directory where the simulation results will be saved.

    Returns:
    --------
    SimRunner
        An instance of the `SimRunner` class, initialized with the specified output directory.
    """
    # Initialize the simulation runner with the specified output directory
    LTC = SimRunner(output_folder=output_dir)
    
    # Return the initialized SimRunner object
    return LTC

def sim_run(LTC, netlist):
    """
    Run the LTSpice simulation with the provided netlist.

    This function takes an initialized `SimRunner` object and a modified netlist, 
    then executes the simulation.

    Parameters:
    -----------
    LTC : SimRunner
        An instance of the `SimRunner` class used to run the simulation.
    netlist : AscEditor
        A modified LTSpice netlist that specifies the components and simulation settings.

    Returns:
    --------
    None
    """
    # Run the simulation with the modified netlist
    LTC.run(netlist)

def set_general_params(netlist, component_list):
    """
    Set general parameters for components in the LTSpice netlist.

    This function iterates over a list of component names and their corresponding values,
    setting these values in the provided LTSpice netlist.

    Parameters:
    -----------
    netlist : AscEditor
        An instance of the `AscEditor` class representing the LTSpice netlist.
    component_list : list of tuples
        A list of tuples where each tuple contains:
        - key : str : The parameter name of the component in the netlist.
        - value : str or float : The value to set for the parameter.

    Returns:
    --------
    netlist
    """
    # Iterate over the component list and set each component's parameter in the netlist
    for key, value in component_list:
        netlist.set_parameters(key=value)  # Set the parameter value for the component
        print(f"First item: {key}, Second item: {value}")  # Print the component name and its new value
    return netlist

def set_components_params(netlist, component_list):
    """
    Set component values in the LTSpice netlist.

    This function iterates over a list of component names and their corresponding values,
    setting these values in the provided LTSpice netlist. The modified netlist is returned.

    Parameters:
    -----------
    netlist : AscEditor
        An instance of the `AscEditor` class representing the LTSpice netlist.
    component_list : list of tuples
        A list of tuples where each tuple contains:
        - key : str : The name of the component in the netlist (e.g., 'R1', 'C2').
        - value : str or float : The new value to set for the component (e.g., '10k', 100e-6).

    Returns:
    --------
    AscEditor
        The modified netlist with updated component values.
    """
    
    # Iterate over the component list and set each component's value in the netlist
    for key, value in component_list:
        netlist.set_component_value(key, value)  # Set the value for the specified component
        print(f"First item: {key}, Second item: {value}")  # Print the component name and its new value for verification
    
    # Return the modified netlist
    return netlist

def single_sim(LTfile, output_dir, component_list):
    """
    Run a single LTSpice simulation with modified component values.

    This function modifies the component values in the given LTSpice netlist 
    file, adds specific simulation settings, and runs the simulation. The results 
    are stored in the specified output directory.

    Parameters:
    -----------
    LTfile          : str
        Path to the LTSpice netlist (.asc) file that will be modified and simulated.
    output_dir      : str
        Directory where the simulation results will be saved.
    component_list                  : list of tuples
        A list of tuples where each tuple contains:
        - key       : str           : The name of the component in the netlist (e.g., 'R1', 'C2').
        - value     : str or float  : The new value to set for the component (e.g., '10k', 100e-6).

    Returns:
    --------
    None
    """
    
    # Initialize the simulation runner with the specified output directory
    LTC     = LTC_runner(output_dir)
    # Load the LTSpice netlist file to modify
    netlist = AscEditor(LTfile)
    # Iterate over the component list and set each component's value in the netlist
    netlist = set_components_params(netlist, component_list)
    # Add specific simulation settings to the netlist
    netlist.add_instructions(
        "; Simulation settings",  # Comment indicating the start of simulation settings
        ";.param run = 0"         # Add a parameter setting with a default value of 0
    )
    # Set the 'run' parameter in the netlist to 0
    netlist.set_parameter('run', 0)
    # Run the simulation with the modified netlist
    sim_run(LTC,netlist)

def cpt_sweep_sim(LTfile, output_dir, component_list):
    LTC     = LTC_runner(output_dir)
    netlist = AscEditor(LTfile)
    netlist = set_components_params(netlist, component_list)
    for key ,ref  in component_list:
        netlist.set_element_model(key , ref)
    netlist.add_instructions(
        "; Simulation settings",  # Comment indicating the start of simulation settings
        ";.param run = 0"         # Add a parameter setting with a default value of 0
    )
    netlist.set_parameter('run', 0)
    sim_run(LTC,netlist)

def values_sweep_sim(LTfile, output_dir, **value_lists):
    """
    Run a series of simulations by sweeping through various component values in an LTSpice netlist.

    This function initializes an LTSpice simulation runner, loads a netlist, and then generates 
    all possible combinations of the specified component values. It modifies the netlist for each 
    combination, adds specific simulation settings, and runs the simulation for each modified netlist.

    Parameters:
    -----------
    LTfile : str
        The path to the LTSpice netlist file (.asc) to be modified and simulated.
    output_dir : str
        The directory where the simulation results will be stored.
    **value_lists : dict
        Keyword arguments where each key is the name of a component (e.g., 'R1', 'C3') 
        and the value is a list of possible values for that component.

    Returns:
    --------
    None
    """

    # Initialize the simulation runner with the specified output directory
    LTC = LTC_runner(output_dir)
    
    # Load the LTSpice netlist file to modify
    netlist = AscEditor(LTfile)
    
    # Generate all possible combinations of the components and their values
    all_combinations = generate_all_combinations(**value_lists)
    
    # Iterate over each combination of component values
    for combination in all_combinations:
        for component_tuple in combination:
            # Modify the netlist by setting the component's value
            netlist = set_components_params(netlist, [component_tuple])
        
        # Add specific simulation settings to the netlist
        netlist.add_instructions(
            "; Simulation settings",  # Comment indicating the start of simulation settings
            ";.param run = 0"         # Add a parameter setting with a default value of 0
        )
        
        # Set the 'run' parameter in the netlist to 0
        netlist.set_parameter('run', 0)
        
        # Run the simulation with the modified netlist
        sim_run(LTC, netlist)

def clean_temps(LTC):
    """
    Clean up temporary files created during simulations using a Tkinter prompt.

    This function displays a Tkinter window with a prompt asking the user if they want to delete 
    the temporary files created by the simulation runner. If the user confirms, the function 
    triggers the cleanup process.

    Parameters:
    -----------
    LTC : SimRunner
        An instance of the `SimRunner` class used to manage the simulation process and its files.

    Returns:
    --------
    None
    """
    
    def on_cleanup():
        """
        Trigger the file cleanup process and close the Tkinter window.
        """
        LTC.file_cleanup()
        root.destroy()

    def on_cancel():
        """
        Close the Tkinter window without performing cleanup.
        """
        root.destroy()

    # Initialize the Tkinter window
    root = tk.Tk()
    root.title("Cleanup Confirmation")
    root.geometry("300x150")
    root.resizable(False, False)

    # Create a label with the prompt message
    label = tk.Label(root, text="Do you want to delete the temporary files?", padx=10, pady=10)
    label.pack()

    # Create a frame to hold the buttons
    button_frame = tk.Frame(root)
    button_frame.pack(pady=10)

    # Create the "Yes" button to trigger cleanup
    yes_button = tk.Button(button_frame, text="Yes", command=on_cleanup, width=10)
    yes_button.pack(side="left", padx=5)

    # Create the "No" button to cancel the operation
    no_button = tk.Button(button_frame, text="No", command=on_cancel, width=10)
    no_button.pack(side="right", padx=5)

    # Start the Tkinter event loop
    root.mainloop()

#? ------------------------------------------------------------------------------- 
# Examples:
# ltspice_file = 'D:/4 WORKSPACE/FASTER/FASTER/assets/testfiles/Test.asc'
# cpt = [('R1','10k'),('C1','100u')]
# output_folder='D:/4 WORKSPACE/FASTER/FASTER/RES/temp'

# R1 = ['1k', '10k', '10']
# C1 = ['1u', '10u', '10n']

# single_sim(ltspice_file, output_folder, cpt)
# values_sweep_sim(ltspice_file, output_folder, R1=R1, C1=C1)

#? ------------------------------------------------------------------------------- 
