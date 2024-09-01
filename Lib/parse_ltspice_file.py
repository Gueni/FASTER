
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
#? Name:        parse_ltspice_file.py
#? Purpose:     Parse LTspice circuit files.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------  
#? ------------------------------------------------------------------------------- 

import re
import assets.patterns as patterns  

def parse_ltspice_file(file_path):
    
    circuit_data = {
        'components'        : [],   # List to store components
        'connections'       : {}    # Dictionary to map nodes to connected components
    }

    # Regular expression patterns for various components
    symbol_patterns     = patterns.symbol_patterns
    value_pattern       = re.compile(r'SYMATTR Value ([\w\(\)\s\.\-μu\[\]]+)')
    name_pattern        = re.compile(r'SYMATTR InstName (\w+)')

    with open(file_path, 'r') as file:
        temp_component  = None
        for line in file:
            line        = line.strip()  # Remove leading/trailing whitespace
            # Check if line matches any symbol pattern
            for symbol_pattern in symbol_patterns:
                symbol_match    = symbol_pattern.match(line)
                if symbol_match:
                    x, y        = symbol_match.groups()
                    temp_component = {
                        'type'      : None,  # Will be set later
                        'name'      : None,
                        'value'     : None,
                        'position'  : (x, y)
                    }
                    # Determine the type based on the symbol pattern
                    # Inside your function, replace the multiple if-elif statements with:
                    for keyword, comp_type in patterns.component_type_map.items():
                        if keyword in line:
                            temp_component['type'] = comp_type
                            break
            
            # Check for value and name attributes if a component is being processed
            if temp_component:
                value_match = value_pattern.match(line)
                name_match = name_pattern.match(line)
                
                if value_match:
                    temp_component['value'] = value_match.group(1)
                
                if name_match:
                    temp_component['name'] = name_match.group(1)
                
                # If all necessary attributes are found, add the component
                if temp_component['name'] and temp_component['value']:
                    circuit_data['components'].append(temp_component)
                    temp_component = None

            # Handle connections separately
            if line.startswith('WIRE'):
                parts = line.split()
                if len(parts) >= 4:
                    node1, node2 = parts[2], parts[3]
                    if node1 not in circuit_data['connections']:
                        circuit_data['connections'][node1] = []
                    if node2 not in circuit_data['connections']:
                        circuit_data['connections'][node2] = []
                    circuit_data['connections'][node1].append(node2)
                    circuit_data['connections'][node2].append(node1)
    
    return circuit_data
#? ------------------------------------------------------------------------------- 
