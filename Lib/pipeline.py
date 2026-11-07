#!/usr/bin/env python
# coding=utf-8

#? -------------------------------------------------------------------------------
#?                          ____  _            ___
#?                         / __ \(_)___  ___  / (_)___  ___
#?                        / /_/ / / __ \/ _ \/ / / __ \/ _ \
#?                       / ____/ / /_/ /  __/ / / / / /  __/
#?                      /_/   /_/ .___/\___/_/_/_/ /_/\___/
#?                             /_/
#?
#? Name:        pipeline.py
#? Purpose:     Run the complete FASTER analysis flow.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/01/2024
#? Updated:     07/11/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------

"""parse -> FMEDA -> FTA -> nominal simulation -> WCA -> Monte Carlo -> report."""

from __future__ import annotations

import copy
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .analysis.fmeda import build_fmeda_table, save_fmeda
from .analysis.iso26262 import hardware_metrics
from .analysis.fta import (analyze_fault_tree, build_fault_tree, fault_tree_figure, fta_to_dataframes,
                           save_fta_results)
from .analysis.montecarlo import MonteCarloSimulation
from .analysis.wca import WorstCaseAnalysis, parse_tolerances
from .core import cleanup, config as cfg_mod
from .knowledge.fit_rates import ENVIRONMENTS, T_REF_C
from .reporting.report import Report
from .reporting.runlog import RunLog
from .schematic.asc_parser import parse_ltspice_file
from .schematic.renderer import render_schematic
from .simulation.runner import SimJob, Simulator
from .simulation.waveforms import trace_figures, trace_statistics

log = logging.getLogger(__name__)


#? -------------------------------------------------------------------------------
@dataclass
class PipelineResult:
    run_dir : Path
    outputs : dict[str, Path] = field(default_factory=dict)
    errors  : dict[str, str] = field(default_factory=dict)


#? -------------------------------------------------------------------------------
def copy_circuit(schematic: Path, out_dir: Path) -> Path:
    """Copy the analysed schematic into the run folder (results stay traceable to the exact circuit)."""
    target = out_dir / schematic.name
    shutil.copy2(schematic, target)
    log.info('Circuit copied to %s', target)
    return target


#? -------------------------------------------------------------------------------
def circuit_image(schematic: Path, out_dir: Path, override: str | os.PathLike | None = None) -> Path | None:
    """User image if given, otherwise export the schematic itself to SVG."""
    if override:
        return Path(override)
    try:
        svg = out_dir / f'schematic_{schematic.stem}.svg'
        render_schematic(schematic, svg)
        return svg
    except Exception:
        log.exception('Schematic export failed')
        return None


#? -------------------------------------------------------------------------------
def run_pipeline(schematic: str | os.PathLike, config: dict | None = None, *,
                 output_root: str | os.PathLike | None = None, simulate: bool = True,
                 run_wca: bool | None = None, run_mc: bool | None = None, mc_runs: int | None = None,
                 image: str | os.PathLike | None = None, keep_sims: bool = False,
                 terminal_tables: bool = True) -> PipelineResult:
    """Run every analysis; results, report and ``log.log`` go to a new run folder."""
    schematic = Path(schematic).resolve()
    if not schematic.is_file():
        raise FileNotFoundError(f'Schematic not found: {schematic}')
    config = copy.deepcopy(config or cfg_mod.load_config())
    if run_wca is not None:
        config['wca']['enabled'] = run_wca
    if run_mc is not None:
        config['montecarlo']['enabled'] = run_mc
    if mc_runs is not None:
        config['montecarlo']['runs'] = mc_runs

    result = PipelineResult(cfg_mod.new_run_dir(schematic.stem, output_root))
    with RunLog(result.run_dir, terminal=terminal_tables) as rl:
        rl.header(schematic, result.run_dir, config, cfg_mod.find_ltspice(config['ltspice_path']))
        _run(schematic, config, result, rl, simulate, image, keep_sims)
        rl.outputs(result.outputs, result.errors)
    result.outputs['log'] = rl.path
    return result


#? -------------------------------------------------------------------------------
def _run(schematic: Path, config: dict, result: PipelineResult, rl: RunLog,
         simulate: bool, image: str | os.PathLike | None, keep_sims: bool) -> None:
    wca_cfg, mc_cfg = config['wca'], config['montecarlo']
    stem, out = schematic.stem, result.run_dir
    t0     = time.perf_counter()
    report = Report(f'FASTER - {stem}', subtitle=str(schematic))

    # 1. Schematic ----------------------------------------------------------------
    rl.rule('1. Schematic')
    result.outputs['circuit'] = copy_circuit(schematic, out)
    circuit = parse_ltspice_file(schematic)
    comps   = circuit['components']
    log.info('Parsed %d components from %s', len(comps), schematic.name)
    comp_df = pd.DataFrame([{'Component': c['name'], 'Type': c['type'], 'Value': c['value'],
                             'Symbol': c['symbol'], 'Position': c['position'], 'Rotation': c['rotation'],
                             'Attributes': ', '.join(f'{k}={v}' for k, v in c['attributes'].items()
                                                     if k not in ('InstName', 'Value'))}
                            for c in comps])
    directives = pd.DataFrame({'Directive': circuit['directives']})
    flags      = pd.DataFrame([{'Net': n, 'X': x, 'Y': y} for (x, y), n in circuit['flags'].items()])
    rl.table(comp_df, 'Components', console=True)
    rl.table(flags, 'Net flags')
    rl.table(directives, 'SPICE directives')
    rl.mapping({'Components': len(comps), 'Wires': len(circuit['wires']),
                'Nets (flags)': len(set(circuit['flags'].values()))}, 'Schematic summary')

    image = circuit_image(schematic, out, image)
    if image is not None and not image.is_file():
        log.warning('Circuit image not found: %s', image)
        image = None
    if image is not None and image.parent == out:
        result.outputs['schematic'] = image
    log.info('Circuit image: %s', image)
    report.add_section('Circuit', image=image,
                       kpis={'Components': len(comps), 'Wires': len(circuit['wires']),
                             'Nets (flags)': len(set(circuit['flags'].values()))},
                       tables=[('Components', comp_df.drop(columns=['Position', 'Rotation', 'Attributes'])),
                               ('SPICE directives', directives)])

    # 2. FMEDA --------------------------------------------------------------------
    rl.rule('2. FMEDA / ISO 26262 hardware metrics')
    rel = config['reliability']
    rl.mapping({'Temperature (degC)': rel['temperature_c'],
                'Environment': f"{rel['environment']} - {ENVIRONMENTS.get(str(rel['environment']).upper(), (0, '?'))[1]}",
                'Reference': f'{T_REF_C:g} degC, GB', 'FIT overrides': rel.get('fit_overrides') or '-'},
               'Mission profile')
    fmeda = build_fmeda_table(comps, rel)
    hw    = hardware_metrics(fmeda, config['iso26262'])
    hw_summary, hw_lambda = hw.summary(), hw.lambda_summary()
    iso_cols = ['Component', 'Failure Mode', 'FIT', 'Safety Related', 'Safe Fraction', 'DC', 'DC Latent',
                'lambda safe', 'lambda SPF', 'lambda RF', 'lambda MPF', 'lambda MPF latent']
    result.outputs['fmeda'] = save_fmeda(fmeda, out / f'FMEDA_{stem}.xlsx', {
        'ISO 26262 metrics': hw_summary, 'Lambda per component': hw_lambda,
        'ISO 26262 failure modes': hw.table[iso_cols]})
    rl.table(fmeda[['Component', 'Type', 'Value', 'Failure Mode', 'Distribution (%)', 'Base FIT', 'pi_T',
                    'pi_E', 'Component FIT', 'FIT']], 'FMEDA - failure rates')
    rl.table(fmeda[['Component', 'Failure Mode', 'Mechanism', 'General Failure Effect']],
             'FMEDA - mechanisms and effects')
    rl.table(fmeda[['Type', 'Mode Source', 'FIT Source']].drop_duplicates(), 'FMEDA - data sources')
    rl.table(hw.table[iso_cols], 'ISO 26262 failure mode classification')
    rl.table(hw_lambda, 'Failure rates per component (FIT)')
    rl.table(hw_summary, f'ISO 26262-5 hardware metrics - target ASIL {hw.asil}', console=True)

    # 3. FTA ----------------------------------------------------------------------
    rl.rule('3. Fault Tree Analysis')
    fta = analyze_fault_tree(build_fault_tree(fmeda), config['fta']['mission_hours'])
    result.outputs['fta'] = save_fta_results(fta, out / f'FTA_{stem}.xlsx')
    ov = fta['overall']
    fta_detail, fta_summary = fta_to_dataframes(fta)
    comp_fit = pd.DataFrame([{'Component': n, 'Type': c['Type'], 'Total FIT': c['Total FIT'],
                              'Probability': c['Probability']} for n, c in fta['components'].items()])
    rl.table(fta_summary, 'FTA summary', console=True)
    rl.table(comp_fit, 'FIT per component')
    rl.table(fta_detail, 'FTA failure modes')
    report.add_section('FMEDA', text=(f"Mission profile: {rel['temperature_c']} degC, environment "
                                      f"{rel['environment']}. FIT = base FIT x pi_T x pi_E, split by failure-mode distribution."),
                       tables=[('', fmeda.drop(columns=['Mode Source', 'FIT Source', 'pi_T', 'pi_E']))])
    m = hw.metrics
    report.add_section('ISO 26262 hardware metrics', kpis={
        'Target': f'ASIL {hw.asil}',
        'SPFM': f"{m['SPFM']:.2%}" if m['lambda total (FIT)'] else 'n/a',
        'LFM': f"{m['LFM']:.2%}" if m['LFM'] == m['LFM'] else 'n/a',
        'PMHF (FIT)': f"{m['PMHF']:.4g}",
        'Result': 'PASS' if hw.passed else 'FAIL',
    }, tables=[('Metrics vs. ISO 26262-5 targets', hw_summary), ('Failure rates per component (FIT)', hw_lambda),
               ('Failure mode classification', hw.table[iso_cols])])
    report.add_section('Fault Tree Analysis', kpis={
        'System FIT': f"{ov['Total FIT']:.4g}",
        'MTTF (h)': f"{ov['MTTF (h)']:.4g}",
        f"P(fail) over {ov['Mission (h)']:g} h": f"{ov['Probability']:.3e}",
        'Failure modes': ov['Failure Modes'],
    }, figures=[fault_tree_figure(fta)], tables=[('Failure modes', fta_detail.drop(columns=['Impact']))])

    # 4. Simulations --------------------------------------------------------------
    if simulate:
        sim_dir = out / 'sims'
        try:
            rl.rule('4. Nominal simulation')
            sim = Simulator(schematic, sim_dir, parallel=config['parallel_sims'],
                            timeout=config['sim_timeout'], ltspice_path=config['ltspice_path'])
            nominal_raw = sim.run(SimJob('nominal'))
            if nominal_raw is None:
                raise RuntimeError('Nominal simulation failed - check the schematic and LTspice install')
            rl.table(trace_statistics(nominal_raw), 'Nominal traces', console=True)
            report.add_section('Nominal simulation', figures=trace_figures(nominal_raw))

            if wca_cfg.get('enabled', True) and wca_cfg.get('components'):
                rl.rule('5. Worst-Case Analysis')
                try:
                    tols = parse_tolerances(wca_cfg['components'], sim, wca_cfg.get('analysis_type', 'passive'))
                    wca = WorstCaseAnalysis(sim, tols, wca_cfg['output_variables'],
                                            wca_cfg.get('max_corner_components', 8)).run()
                    result.outputs['wca'] = wca.save(out / f'WCA_{stem}.xlsx')
                    rl.table(wca.tolerance_table(), 'WCA tolerances')
                    rl.table(wca.case_table(), 'WCA cases')
                    rl.table(wca.summary, 'WCA summary', console=True)
                    report.add_section('Worst-Case Analysis', text=f'{len(wca.cases)} simulations.',
                                       figures=wca.figures(), tables=[('Summary', wca.summary)])
                except Exception as exc:  # keep the rest of the report
                    log.exception('WCA failed')
                    result.errors['wca'] = str(exc)

            if mc_cfg.get('enabled', True) and mc_cfg.get('tolerances'):
                rl.rule('6. Monte Carlo')
                try:
                    mcs = MonteCarloSimulation(sim, mc_cfg['tolerances'], runs=mc_cfg['runs'],
                                               distribution=mc_cfg['distribution'], seed=mc_cfg.get('seed'),
                                               output_variable=mc_cfg['output_variable'])
                    rl.table(mcs.input_table(), 'Monte Carlo inputs')
                    mc = mcs.run()
                    wave_csv, sample_csv = mc.save_csv(out, f'montecarlo_{stem}')
                    result.outputs['montecarlo_waveforms'] = wave_csv
                    result.outputs['montecarlo_samples'] = sample_csv
                    stats = mc.statistics().reset_index().rename(columns={'index': 'Metric'})
                    rl.table(mc.samples.rename_axis('Run').reset_index(), 'Monte Carlo runs')
                    rl.table(stats, f'Monte Carlo statistics - {mc.output_variable}', console=True)
                    report.add_section('Monte Carlo', text=f"{mc_cfg['runs']} runs, {mc_cfg['distribution']} distribution.",
                                       figures=[mc.figure()], tables=[('Statistics', stats)])
                except Exception as exc:
                    log.exception('Monte Carlo failed')
                    result.errors['montecarlo'] = str(exc)
        except Exception as exc:
            log.exception('Simulation failed')
            result.errors['simulation'] = str(exc)
        finally:
            if not keep_sims:
                cleanup.remove_sim_dir(sim_dir)
    else:
        log.info('Simulations skipped (--no-sim)')

    if result.errors:
        report.add_section('Errors', tables=[('', pd.DataFrame(
            [{'Step': k, 'Error': v} for k, v in result.errors.items()]))])

    # 7. Report -------------------------------------------------------------------
    rl.rule('7. Report')
    result.outputs['report'] = report.write(out / f'report_{stem}.html')
    log.info('Done in %.1f s -> %s', time.perf_counter() - t0, out)

#? -------------------------------------------------------------------------------
