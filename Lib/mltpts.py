



import ltspice
import matplotlib.pyplot as plt
import numpy as np
import os

# Load your simulation .raw file
raw_path = "D:/WORKSPACE/FASTER/FASTER/assets/testfiles/Test.raw"  # Adjust name if needed

import ltspice
import matplotlib.pyplot as plt
import numpy as np
import os

l = ltspice.Ltspice(raw_path) 
# Make sure that the .raw file is located in the correct path
l.parse() 

time = l.get_time()
V_source = l.get_data('I(R1)')
V_cap_max = []

plt.plot(time, V_source)
for i in range(l.case_count): # Iteration in simulation cases 
    time = l.get_time(i)
    # Case number starts from zero
    # Each case has different time point numbers
    V_cap = l.get_data('I(R1)',i)
    V_cap_max.append(max(V_cap))
    plt.plot(time, V_cap)

print(np.float64(V_cap_max))


plt.grid()
plt.show()
