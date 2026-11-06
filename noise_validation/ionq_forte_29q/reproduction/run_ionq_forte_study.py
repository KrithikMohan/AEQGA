"""Run the official Forte-1 width study. IONQ_API_KEY is environment-only.

python run_ionq_forte_study.py --workers 6
Reruns replay saved cloud histograms without resubmitting completed jobs.
"""
from __future__ import annotations
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name] = '1'
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time
import numpy as np
from threadpoolctl import threadpool_limits

from aeqga_ionq_cloud import ProfiledIonQAEQGA, IonQCloud, write_json
from aeqga_profiled_pantheon import ProfiledPantheon

ROOT = Path(__file__).resolve().parent
SOURCES = ['aeqga.py','aeqga_legacy.py','aeqga_parallel.py','aeqga_profiled_pantheon.py',
           'aeqga_ionq_cloud.py','run_ionq_forte_study.py','run_pantheon_aeqga.py']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def csv_write(path,rows):
    with Path(path).open('w',newline='',encoding='utf-8') as file:
        writer = csv.DictWriter(file,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def run_case(spec):
    output,width,mode,generations,shots,seed,budget,reference,provenance = spec
    directory = Path(output)/f'q{width}_{mode}'
    config = {'width':width,'mode':mode,'generations':generations,'shots':shots,'seed':seed,
              'qubit_budget':budget,'provenance':provenance}
    if (directory/'summary.json').exists():
        summary = json.loads((directory/'summary.json').read_text())
        if summary['config'] != config:
            raise ValueError('Existing case configuration differs.')
        print(f'SKIP q{width} {mode}',flush=True)
        return summary
    if (directory/'config.json').exists() and json.loads((directory/'config.json').read_text()) != config:
        raise ValueError(f'Existing {directory} configuration differs.')
    write_json(directory/'config.json',config)
    with threadpool_limits(limits=2):
        problem = ProfiledPantheon()
        optimizer = ProfiledIonQAEQGA(problem,width=width,qubit_budget=budget,mode=mode,
            record_directory=directory,shots=shots,seed=seed)
        optimizer.train(generations=generations)
        independent = [abs(problem.direct_check(h['p'],h['all_parameters'][2])-h['loss'])
                       for h in optimizer.history_]
    if max(independent) > 1e-7:
        raise AssertionError('Independent 64-node chi-square check failed.')
    rows = []
    for h in optimizer.history_:
        rows.append({'generation':h['generation'],'H0':h['all_parameters'][0],
            'Omega_m':h['all_parameters'][1],'M':h['all_parameters'][2],
            'chi2':h['loss'],'delta_chi2':h['loss']-reference['chi2'],
            'fitness_evaluations':h['fitness_evaluations'],'wall_seconds':h['elapsed_wall_seconds']})
    csv_write(directory/'best_history.csv',rows)
    with gzip.open(directory/'population_history.csv.gz','wt',newline='',encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['generation','circuit_index','individual','origin','H0','Omega_m','M',
                         'chi2','M_unconstrained','M_at_bound'])
        for h in optimizer.history_:
            for p in h['population']:
                writer.writerow([h['generation'],p['circuit_index'],p['individual'],p['origin'],
                    *p['all_parameters'],p['chi2'],p['M_unconstrained'],p['M_at_bound']])
    for name,histories in [('training_history',optimizer.history_),('execution_history',optimizer.execution_history_)]:
        with gzip.open(directory/f'{name}.jsonl.gz','wt',encoding='utf-8') as file:
            for record in histories:
                file.write(json.dumps(record,allow_nan=False)+'\n')
    metrics = []
    for record in optimizer.execution_history_:
        stages = record['stage_diagnostics']
        metrics.append({'generation':record['generation'],
            'mean_counts_vs_ideal_tvd':float(np.mean([d['counts_vs_ideal_tvd'] for d in stages])),
            'mean_zero_fraction':float(np.mean([d['zero_fraction_used_candidates'] for d in stages])),
            'mean_qis_cx_per_subpopulation':float(sum(d['qis_gate_counts'].get('cx',0) for d in stages)/optimizer.parallel_circuits),
            'max_synthesis_tvd':max(d['synthesis_tvd'] for d in stages)})
    csv_write(directory/'generation_metrics.csv',metrics)
    summary = {'config':config,'width':width,'mode':mode,'generations':generations,'shots':shots,
        'qubit_budget':budget,'used_qubits':optimizer.used_active_qubits,
        'discarded_qubits':optimizer.discarded_qubits,'parallel_circuits':optimizer.parallel_circuits,
        'population_per_circuit':optimizer.population_per_circuit,'total_population':optimizer.population_size,
        'elite_local_global_per_circuit':[optimizer.elite_count,optimizer.local_count,optimizer.random_count],
        'best_parameters':optimizer.history_[-1]['all_parameters'],'chi2':optimizer.loss_,
        'delta_chi2':optimizer.loss_-reference['chi2'],'reference':reference,
        'fitness_evaluations':optimizer.n_evaluations_,
        'candidate_rows':len(optimizer.history_)*optimizer.population_size,
        'cloud_jobs':4*generations if mode=='noisy' else 0,
        'training_wall_seconds':optimizer.history_[-1]['elapsed_wall_seconds'],
        'max_independent_chi2_error':max(independent),
        'mean_metrics':{key:float(np.mean([r[key] for r in metrics])) for key in metrics[0] if key!='generation'},
        'thresholds':{str(t):next((r for r in rows if r['delta_chi2']<=t),None) for t in (.1,.01,.001)},
        'validation':'passed'}
    write_json(directory/'summary.json',summary)
    print(f'COMPLETE q{width} {mode} delta_chi2={summary["delta_chi2"]:.9g}',flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'output'/'ionq_forte_29q')
    parser.add_argument('--widths',type=int,nargs='+',default=list(range(3,9)))
    parser.add_argument('--modes',nargs='+',choices=['noisy','ideal'],default=['noisy','ideal'])
    parser.add_argument('--generations',type=int,default=100)
    parser.add_argument('--shots',type=int,default=100)
    parser.add_argument('--seed',type=int,default=7)
    parser.add_argument('--qubit-budget',type=int,default=29)
    parser.add_argument('--workers',type=int,default=6)
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    provenance = {'source_sha256':{name:sha(ROOT/name) for name in SOURCES},
        'data_sha256':{name:sha(ROOT/'Pantheon+_Data'/'4_DISTANCES_AND_COVAR'/name)
                      for name in ('Pantheon+SH0ES.dat','Pantheon+SH0ES_STAT+SYS.cov')},
        'versions':{name:importlib.metadata.version(name) for name in
                    ('numpy','scipy','qiskit','qiskit-aer','requests','pandas','matplotlib')}}
    with threadpool_limits(limits=2):
        problem = ProfiledPantheon()
        reference = problem.reference()
    plan = {'widths':args.widths,'modes':args.modes,'generations':args.generations,'shots':args.shots,
        'seed':args.seed,'requested_qubit_budget':args.qubit_budget,
        'model':'official IonQ Cloud forte-1','backend':'simulator','reference':reference,
        'provenance':provenance,'four_stages_per_generation':True,
        'configuration':[{'width':q,'groups':args.qubit_budget//q,
                          'used_qubits':q*(args.qubit_budget//q),
                          'population':(args.qubit_budget//q)*(1 << q)} for q in args.widths]}
    plan_file = output/'study_plan.json'
    if plan_file.exists() and json.loads(plan_file.read_text()) != plan:
        raise ValueError('Study plan or source/data hashes changed; use a separate output directory.')
    write_json(plan_file,plan)
    if 'noisy' in args.modes:
        preflight = IonQCloud().run({'type':'ionq.circuit.v1','backend':'simulator',
            'name':'AEQGA asymmetric bit-order validation','shots':100,
            'noise':{'model':'forte-1','seed':91},'input':{'qubits':3,'gateset':'qis',
                'circuit':[{'gate':'x','target':0}]}},output/'preflight')
        if preflight['histogram'].get('1',0)<80:
            raise AssertionError('Cloud bit-order validation failed.')
        print('Cloud authentication, histogram counts and little-endian bit ordering verified.',flush=True)
    specs = [(str(output),q,mode,args.generations,args.shots,args.seed,args.qubit_budget,reference,provenance)
             for mode in args.modes for q in args.widths]
    summaries = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_case,s) for s in specs]
        for future in as_completed(futures):
            summaries.append(future.result())
            write_json(output/'progress.json',{'completed_cases':[(s['width'],s['mode']) for s in summaries]})
    summaries.sort(key=lambda s:(s['width'],s['mode']))
    write_json(output/'study_summary.json',summaries)
    print('ALL CASES COMPLETE',flush=True)


if __name__ == '__main__':
    main()
