
from PyLTSpice import AscEditor, SimRunner  
from PyLTSpice.sim.tookit.worst_case import WorstCaseAnalysis


def worst_case(asc_file,netlist_path,results_path,netlist_file):

    asc_file    = AscEditor(asc_file)                       # Reads the asc file into memory
    runner      = SimRunner(output_folder=netlist_path)     # Instantiates the runner class, with the output folder already set
    wca         = WorstCaseAnalysis(asc_file, runner)       # Instantiates the Worst Case Analysis class

    # Set the default tolerances for the components
    wca.set_tolerance('R', 0.01)  # 1% tolerance
    wca.set_tolerance('C', 0.1)  # 10% tolerance
    # wca.set_tolerance('V', 0.1)  # 10% tolerance. For Worst Case analysis, the distribution is irrelevant

    # Some components can have a different tolerance
    # wca.set_tolerance('R1', 0.05)  # 5% tolerance for R1 only. This only overrides the default tolerance for R1

    # Tolerances can be set for parameters as well.
    # wca.set_parameter_deviation('Vos', 3e-4, 5e-3)

   # Finally the netlist is saved to a file
    wca.save_netlist(netlist_file)

    wca.run_testbench()  # Runs the simulation with splits of 100 runs each

    logs = wca.read_logfiles()   # Reads the log files and stores the results in the results attribute
    logs.export_data(results_path)  # Exports the data to a csv file

    # print("Worst case results:")
    # for param in ('fcut', 'fcut_FROM'):
    #     print(f"{param}: min:{logs.min_measure_value(param)} max:{logs.max_measure_value(param)}")

    wca.cleanup_files()  # Deletes the temporary files