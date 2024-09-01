

# Load data from Excel  G.draw('D:/4 WORKSPACE/Tree/RES/fta_tree.png')  # Replace with your desired output path

excel_file_path = 'D:/4 WORKSPACE/FASTER/FASTER/RES/FTA_circuit_file_20240829_233145.xlsx'  # Replace with your actual file path

import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import ast
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import textwrap
# Load data from Excel (adjust the path and sheet name if needed)
df = pd.read_excel(excel_file_path)





# Parse the data
fta_data = {}
for index, row in df.iterrows():
    component = row['Component']  # Update to match the actual column name
    failures = ast.literal_eval(row['Failure Details'])  # Convert string to dictionary
    fta_data[component] = failures

# Function to calculate height based on text length
def calculate_height(text, width=30):
    lines = textwrap.wrap(text, width=width)
    return 0.5 + 0.3 * len(lines)  # Base height + extra height per line

def add_rectangle(ax, text, xy, width=3.0, fontsize=10):
    height = calculate_height(text)
    rect = FancyBboxPatch(xy, width, height, boxstyle="round,pad=0.3", edgecolor='black', facecolor='lightyellow')
    ax.add_patch(rect)
    ax.text(xy[0] + width/2, xy[1] + height/2, text, ha="center", va="center", fontsize=fontsize, wrap=True)
    return height

def add_arrow(ax, start, end):
    arrow = FancyArrowPatch(start, end, arrowstyle='->', mutation_scale=15, color='black')
    ax.add_patch(arrow)

# Create figure and axes
fig, ax = plt.subplots(figsize=(12, 10))

# Positioning variables
x_start = 0
y_start = 0
x_step = 5
y_step = 2

# Iterate through the FTA data and create the diagram
current_y = y_start
for i, (component, failures) in enumerate(fta_data.items()):
    component_height = add_rectangle(ax, component, (x_start, current_y))
    
    failure_start_y = current_y - component_height - y_step
    current_x = x_start + x_step
    
    for j, (failure_mode, description) in enumerate(failures.items()):
        failure_text = f'{failure_mode}\n({description})'
        failure_height = add_rectangle(ax, failure_text, (current_x, failure_start_y))
        
        # Draw the arrow from component to the failure mode
        add_arrow(ax, (x_start + 3, current_y - component_height / 2), (current_x, failure_start_y + failure_height / 2))
        
        # Adjust next failure mode position
        failure_start_y -= (failure_height + y_step)
    
    # Adjust current_y for the next component block
    current_y = failure_start_y - y_step

# Set limits and hide axes
ax.set_xlim(-1, current_x + x_step)
ax.set_ylim(current_y - y_step, y_start + 2)
ax.axis('off')

# Display the diagram
plt.title("Fault Tree Analysis (FTA) Diagram", fontsize=16)
plt.show()
