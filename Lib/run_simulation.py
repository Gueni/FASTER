from PyLTSpice import SpiceEditor
ltspice_file = 'D:/4 WORKSPACE/FASTER/FASTER/assets/Test.asc'
se = SpiceEditor(ltspice_file)

se.set_component_value('R1', 11000)


se.save_netlist("./testfiles/Noise_updated.net")
se.run()
    
   