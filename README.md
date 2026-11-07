# FASTER (Failure Analysis, Simulation, Testing, and Evaluation Report)

FASTER automates reliability analysis of LTspice circuits. From a single `.asc`
schematic it produces:

- **FMEDA** – failure modes, mechanisms, effects and mission-profile FIT of every component
- **ISO 26262 metrics** – SPFM, LFM and PMHF against the ASIL targets of ISO 26262-5
- **FTA** – fault tree, system FIT, MTTF and failure probability over a mission time
- **Nominal simulation** – every voltage/current trace
- **WCA** – worst-case (corner) analysis of toleranced components
- **Monte Carlo** – statistical tolerance analysis with real LTspice runs
- **HTML report** – one self-contained, interactive (Plotly) page with all of the above

Simulations run in parallel through PyLTSpice.

## Table of Contents

1. [Installation](#installation)
2. [Usage](#usage)
3. [Configuration](#configuration)
4. [Reliability data](#reliability-data)
5. [ISO 26262 hardware metrics](#iso-26262-hardware-metrics)
6. [Outputs](#outputs)
7. [Project structure](#project-structure)
8. [Using the library](#using-the-library)
9. [License](#license)

## Installation

Requirements: Python ≥ 3.10 and [LTspice](https://www.analog.com/ltspice) (only for simulations).

```bash
git clone https://github.com/yourusername/FASTER.git
cd FASTER
pip install -r requirements.txt
```

LTspice is found automatically in the usual install folders. Otherwise set
`"ltspice_path"` in `config.json` or the `FASTER_LTSPICE` environment variable.

## Usage

```bash
python main.py tests/Test.asc        # full analysis
python main.py                                  # pick the schematic in a file dialog
python main.py circuit.asc --no-sim             # FMEDA + FTA only (no LTspice needed)
python main.py circuit.asc --mc-runs 500 --open # more Monte Carlo runs, open the report
```

| Option | Description |
|---|---|
| `-c, --config FILE` | configuration file (default `config.json`) |
| `-o, --output DIR` | output root (default `data/`) |
| `--image FILE` | use this picture instead of the automatic schematic export |
| `--mc-runs N` | override the Monte Carlo run count |
| `--no-sim`, `--no-wca`, `--no-mc` | skip all simulations / WCA / Monte Carlo |
| `--keep-sims` | keep the generated netlists and `.raw` files |
| `--open` | open the report in the browser when done |
| `--no-tables` | do not print result tables in the terminal (`log.log` still has them) |
| `-v, --verbose` | debug logging |

## Configuration

`config.json` (all keys optional, defaults in [Lib/core/config.py](Lib/core/config.py)):

```json
{
    "ltspice_path": null,
    "parallel_sims": 4,
    "sim_timeout": 600,
    "reliability": { "temperature_c": 55, "environment": "GM", "fit_overrides": { "U1": 12.5 } },
    "iso26262": {
        "target_asil": "B",
        "not_safety_related": ["R7"],
        "safe_fraction":       { "resistor": { "drift high": 0.5 } },
        "diagnostic_coverage": { "Vin": { "*": "high" }, "resistor": { "open circuit": "medium" } },
        "latent_coverage":     { "*": { "*": 0.9 } }
    },
    "fta":  { "mission_hours": 8000 },
    "wca": {
        "analysis_type": "passive",
        "components": { "R1": 12, "R2": { "tolerance": 1, "nominal": "11.5k" } },
        "output_variables": ["V(out)", "I(R1)"],
        "max_corner_components": 8
    },
    "montecarlo": {
        "runs": 50,
        "distribution": "uniform",
        "seed": 42,
        "output_variable": "V(out)",
        "tolerances": { "R1": 5, "R2": 10 }
    }
}
```

- Tolerances are in **percent**. In WCA, `"analysis_type": "active"` means the
  tolerance is an absolute value (nominal ± tolerance).
- `nominal` is optional: by default it is read from the schematic. SPICE suffixes
  (`k`, `meg`, `u`, `n` ...) are accepted.
- WCA simulates all 2^N corners up to `max_corner_components`, and varies one
  component at a time above that.
- Monte Carlo `distribution`: `uniform`, or `gaussian` with 3σ = tolerance.
- The old single-component `cmpt.json` format is still accepted.

## Reliability data

The knowledge base lives in `Lib/knowledge/` and covers 26 component classes
(sources, battery, resistor, MLCC, electrolytic, inductor, ferrite bead,
transformer, crystal, fuse, diode, zener, TVS, Schottky, LED, BJT, MOSFET,
JFET, IGBT, thyristor, op-amp/comparator, IC, relay, switch, connector).

- **Failure modes** (`failures.py`): each mode has its share of the component
  failure rate, the physical mechanism and the local effect. Distributions follow
  RIAC FMD-2016 and MIL-HDBK-338B; failure modes to consider follow ISO 26262-5
  Annex D and ISO 26262-11 (semiconductor fault models). Splits that are not in a
  published table are marked `derived` in the `Mode Source` column.
- **FIT rates** (`fit_rates.py`): typical base FIT at reference conditions
  (40 °C, ground benign, automotive-grade parts) from the handbooks ISO 26262-5
  §8.4.3 accepts: SN 29500, IEC 61709 and MIL-HDBK-217F.
- **Mission profile**: `FIT = base × π_T × π_E`, with π_T an Arrhenius factor
  (IEC 61709 approach, one activation energy per class) and π_E the
  MIL-HDBK-217F environment factor (`GB`, `GF`, `GM` = automotive, `NS`, `AIC`,
  `AUF`, `SF`, `ML` ...).
- `fit_overrides` replaces the base FIT of a type or of one designator (e.g. a
  supplier FIT for an IC).

These are generic values. For a safety case, replace them with supplier data,
field data or your company's reliability handbook.

## ISO 26262 hardware metrics

`Lib/analysis/iso26262.py` classifies every FMEDA failure mode
(ISO 26262-5 Annex B) and computes the hardware architectural metrics:

| Metric | Formula | ASIL B | ASIL C | ASIL D |
|---|---|---|---|---|
| SPFM | 1 − Σ(λ_SPF + λ_RF) / Σλ | ≥ 90 % | ≥ 97 % | ≥ 99 % |
| LFM | 1 − Σλ_MPF,latent / Σ(λ − λ_SPF − λ_RF) | ≥ 60 % | ≥ 80 % | ≥ 90 % |
| PMHF | ≈ Σ(λ_SPF + λ_RF) | < 100 FIT | < 100 FIT | < 10 FIT |

The **safe fraction**, **diagnostic coverage** and **latent coverage** depend on
the system and its safety mechanisms, so they come from `config.json`. Keys are a
designator, a component type or `*`; inner keys a failure mode or `*`; the most
specific match wins. Values accept `none` / `low` (60 %) / `medium` (90 %) /
`high` (99 %), a fraction (`0.9`) or a percentage (`90`). Without any entry
every dangerous fault is a single-point fault (SPFM = 0 %).

## Outputs

Each run creates `data/<circuit>_<timestamp>/`:

| File | Content |
|---|---|
| `FMEDA_<circuit>.xlsx` | FMEDA (modes, distribution, mechanism, effect, base FIT, π_T, π_E, FIT, sources), ISO 26262 metrics, λ per component, failure-mode classification |
| `FTA_<circuit>.xlsx` | summary (system FIT, MTTF, probability) and per-failure-mode details |
| `WCA_<circuit>.xlsx` | worst deviation per output, tolerances, simulated cases |
| `montecarlo_<circuit>_waveforms.csv` | output waveform of every run on a common time axis |
| `montecarlo_<circuit>_samples.csv` | component values and peak/min/max/mean/RMS per run |
| `schematic_<circuit>.svg` | schematic image exported from the `.asc` |
| `report_<circuit>.html` | interactive report (works offline) |
| `log.log` | full run log: banner, run info, package versions, config, every log message (DEBUG and up, incl. LTspice runs) and all result tables |

## Project structure

```
main.py                 command line entry point
config.json             analysis settings
Lib/
  core/                 config.py (paths, LTspice discovery, config) · cleanup.py · banner.py
  knowledge/            components.py (type detection) · failures.py · fit_rates.py
  schematic/            asc_parser.py · symbols.py (.asy library) · renderer.py (SVG export)
  simulation/           runner.py (LTspice runner, sweeps) · waveforms.py (.raw helpers, plots)
  analysis/             fmeda.py · iso26262.py · fta.py · wca.py · montecarlo.py
  reporting/            report.py (HTML report) · runlog.py (log.log with rich tables)
  pipeline.py           full analysis flow
tests/                  example circuit (Test.asc + simulation results)
data/                   analysis results
```

To add a component type, add its failure modes to `Lib/knowledge/failures.py`, its
FIT rates to `Lib/knowledge/fit_rates.py` and its symbol / designator to
`Lib/knowledge/components.py`.

Code style: every module starts with the `#?` header (slant figlet of the module
name, Name / Purpose / Author / Created / Licence), top-level blocks are separated
by `#? ---` lines and assignment blocks are column-aligned.

## Schematic image

The circuit picture in the report is exported automatically from the loaded
`.asc` file. LTspice has no command-line image export, so FASTER draws the
schematic itself (wires, junctions, flags, directives and every symbol taken
from the LTspice `.asy` library in `%LOCALAPPDATA%\LTspice\lib\sym`, or from
the schematic's own folder). Symbols that cannot be found or are encrypted are
drawn as a dashed red box. Standalone use:

```bash
python -m Lib.schematic.renderer circuit.asc circuit.svg
```

## Using the library

```python
from Lib.schematic.asc_parser import parse_ltspice_file
from Lib.schematic.renderer import render_schematic
from Lib.simulation.runner import Simulator, SimJob, values_sweep_sim
from Lib.simulation.waveforms import show_raw
from Lib.analysis.wca import WorstCaseAnalysis, parse_tolerances
from Lib.analysis.montecarlo import MonteCarloSimulation

circuit = parse_ltspice_file('tests/Test.asc')
render_schematic('tests/Test.asc', 'data/Test.svg')

# value sweep: every combination, run in parallel
raws = values_sweep_sim('tests/Test.asc', 'data/sweep', R1=['1k', '10k'], R2=['1k', '2k'])

sim = Simulator('tests/Test.asc', 'data/sims')
wca = WorstCaseAnalysis(sim, parse_tolerances({'R1': 5}, sim), ['V(out)']).run()
mc  = MonteCarloSimulation(sim, {'R1': 5, 'R2': 10}, runs=100, seed=1).run()
print(wca.summary, mc.statistics())

show_raw(raws['sweep_0000'], ['V(out)'])     # or: python -m Lib.simulation.waveforms file.raw V(out)
```

Also available in `Lib.simulation.runner`: `single_sim`, `param_sweep_sim` (`.param` values)
and `model_sweep_sim` (component models, e.g. `D1=['1N4148', '1N914']`).

## License

GNU General Public License v3.0 – see the LICENSE file.
