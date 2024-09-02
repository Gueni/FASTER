# FASTER (Failure Analysis, Simulation, Testing, and Evaluation Report)

FASTER (Failure Analysis, Simulation, Testing, and Evaluation Report) automates reliability analysis for LTspice circuits. It performs FMEDA (Failure Modes, Effects, and Diagnostic Analysis) and FTA (Fault Tree Analysis), simulating faults to assess impacts on circuit performance. The program generates detailed reports with plots of currents and voltages, providing insights to enhance circuit reliability and safety.

## Table of Contents

1. [Features](#features)
   - [Parameter Setting](#parameter-setting)
   - [Values Setting](#values-setting)
   - [Single Simulation](#single-simulation)
   - [Sweep Simulation](#sweep-simulation)
   - [Component Reference Sweep Simulation](#component-reference-sweep-simulation)
2. [Installation](#installation)
3. [Usage](#usage)
4. [Examples](#examples)
5. [Contributing](#contributing)
6. [License](#license)

## Features

### Parameter Setting

FASTER allows for easy configuration of simulation parameters directly within LTSpice netlists. You can set parameters using specific functions that modify the netlist and apply the necessary settings for accurate simulations.

### Values Setting

You can define and set component values dynamically. This feature supports updating values of components like resistors, capacitors, and other elements, ensuring that your simulations reflect the intended circuit configurations.

### Single Simulation

Perform a single simulation run with your LTSpice netlist. This feature allows you to test the circuit under a specific configuration and view the results immediately, including detailed reports and graphical plots of currents and voltages.

### Sweep Simulation

Conduct parameter sweeps to analyze how changes in component values affect circuit performance. This feature automates the process of varying component values across specified ranges and generates results that help identify performance trends and potential issues.

### Component Reference Sweep Simulation

Run simulations across a range of component values and configurations, with results organized by component type. This feature is useful for evaluating the impact of different component selections on overall circuit behavior.

## Installation

To install FASTER, clone the repository and install the required dependencies:

```bash
git clone https://github.com/yourusername/FASTER.git
cd FASTER
pip install -r requirements.txt
