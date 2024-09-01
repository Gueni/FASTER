
import Failures 

def analyze_failure_modes(components):
    """
    Analyzes the failure modes based on the given components.
    """
    failure_modes       = {}
    # Define failure modes for the components
    component_failures  = Failures.component_failures
    for comp in components:
        comp_name       = comp['name']
        comp_type       = comp['type']
        if comp_type in component_failures:
            failure_modes[comp_name] = component_failures[comp_type]

    return failure_modes

