"""Audit complete saved Forte runs, draw figures and package reproducible records."""
from __future__ import annotations
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import argparse
from collections import Counter
import csv
from datetime import datetime
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import zipfile
import numpy as np
from scipy.linalg import solve_triangular
from threadpoolctl import threadpool_limits
from aeqga_ionq_cloud import digest,marginal,write_json
from aeqga_profiled_pantheon import ProfiledPantheon
from aeqga import AEQGA
from run_ionq_forte_study import SOURCES,csv_write,sha
from run_pantheon_aeqga import make_model

ROOT=Path(__file__).resolve().parent
COLORS={3:'#2563eb',4:'#0f766e',5:'#b45309',6:'#9333ea',7:'#be123c',8:'#475569'}


def load_lines(path):
    with gzip.open(path,'rt',encoding='utf-8') as file:
        return [json.loads(line) for line in file]


def replay_candidates(histories,executions,summary):
    """Replay search with saved counts and independently checked objective values."""
    problem=ProfiledPantheon()
    class Replay(AEQGA):
        def _evaluate_candidates(self,candidates,inputs,targets,scale,cholesky):
            generation=len(self.history_)
            population=histories[generation]['population']
            shape=(self.parallel_circuits,self.population_per_circuit)
            params=np.array([p['p'] for p in population]).reshape(*shape,2)
            scores=np.array([p['chi2'] for p in population]).reshape(shape)
            start=self.elite_count if generation else 0
            np.testing.assert_array_equal(candidates,params[:,start:])
            self.n_evaluations_+=scores[:,start:].size
            return scores[:,start:].copy()
        def _measure_circuits(self,circuits,seed,rng):
            e=executions[self.n_generations_]
            assert seed==e['execution_seed']
            self.execution_history_.append(json.loads(json.dumps(e)))
            result=[]
            for group in range(self.parallel_circuits):
                values=np.zeros(self.shots,dtype=np.uint64)
                for stage in range(4):
                    counts=marginal(e['packed_stage_results'][stage]['histogram'],self.qubits_per_circuit,group)
                    values |= np.repeat(np.arange(len(counts),dtype=np.uint64),counts) << (stage*self.qubits_per_circuit)
                result.append({format(v,f'0{4*self.qubits_per_circuit}b'):n for v,n in Counter(map(int,values)).items()})
            return result
        def _record_subpopulations(self,population,losses,generation,verbose):
            expected=histories[generation]
            np.testing.assert_array_equal(population.reshape(-1,2),np.array([p['p'] for p in expected['population']]))
            np.testing.assert_allclose(losses.ravel(),[p['chi2'] for p in expected['population']],atol=1e-8,rtol=0)
            super()._record_subpopulations(population,losses,generation,False)
            problem.retain(population)
    a=Replay(problem.predict,[70.,.3],bounds=problem.bounds,vectorized=True,
        active_qubits=summary['used_qubits'],parallel_circuits=summary['parallel_circuits'],
        shots=summary['shots'],seed=summary['config']['seed'])
    a.train(problem.x,problem.y,covariance=problem.covariance,generations=summary['generations'])


def scalar_profile(problem, model, parameters):
    prediction=model(problem.x,[*parameters,0.])
    residual=solve_triangular(problem.cholesky,problem.y-prediction,lower=True)
    unconstrained=float(problem.ones_white@residual/problem.m_denominator)
    magnitude=float(np.clip(unconstrained,*problem.magnitude_bounds))
    residual-=problem.ones_white*magnitude
    return float(residual@residual),magnitude,unconstrained


def audit_case(folder,summary,problem):
    extension_file=folder/'execution_extension.json'
    if extension_file.exists():
        extension=json.loads(extension_file.read_text())
        assert sha(ROOT/extension['source'])==extension['source_sha256']
    histories=load_lines(folder/'training_history.jsonl.gz')
    executions=load_lines(folder/'execution_history.jsonl.gz')
    q=summary['width']; k=summary['parallel_circuits']; n=1<<q
    generations=summary['generations']; shots=summary['shots']
    assert len(histories)==generations+1 and len(executions)==generations
    jobs=set(); maximum_chi=maximum_m=0.; rows=0
    scalar_rechecks=0
    model=make_model(problem.order)
    resource_rows=[]
    for generation,h in enumerate(histories):
        assert h['generation']==generation and len(h['population'])==k*n
        assert h==json.loads((folder/'generations'/f'g{generation:03d}.json').read_text())
        params=np.array([p['p'] for p in h['population']])
        losses=np.array([p['chi2'] for p in h['population']])
        magnitudes=np.array([p['M_profiled'] for p in h['population']])
        values=problem.evaluate(params)
        suspect=(~np.all(np.isfinite(values),axis=1) | (np.abs(values[:,0]-losses)>=1e-6)
                 | (np.abs(values[:,1]-magnitudes)>=1e-8))
        for i in np.flatnonzero(suspect):
            checked=scalar_profile(problem,model,params[i])
            problem.cache[tuple(params[i])]=checked
            values[i]=checked
            scalar_rechecks+=1
        maximum_chi=max(maximum_chi,float(np.max(np.abs(values[:,0]-losses))))
        maximum_m=max(maximum_m,float(np.max(np.abs(values[:,1]-magnitudes))))
        if (not np.all(np.isfinite(losses)) or not np.all(np.isfinite(magnitudes))
                or not np.all(np.isfinite(values)) or maximum_chi>=1e-6 or maximum_m>=1e-8):
            raise AssertionError(
                f'{folder.name} generation {generation}: numerical audit discrepancy '
                f'(chi2={maximum_chi:.12g}, M={maximum_m:.12g}).'
            )
        assert h['best_index']==int(np.argmin(losses)) and h['loss']==float(losses.min())
        assert h['fitness_evaluations']==k*n+generation*k*(3*n//4)
        for i,p in enumerate(h['population']):
            group,individual=divmod(i,n)
            assert (p['circuit_index'],p['individual'])==(group,individual)
            expected_origin='initial' if not generation else 'elite' if individual<n//4 else 'local' if individual<n//2 else 'global'
            assert p['origin']==expected_origin
            assert p['all_parameters']==[*p['p'],p['M_profiled']]
        if generation:
            previous=histories[generation-1]
            previous_losses=np.array([p['chi2'] for p in previous['population']])
            selected=np.argsort(previous_losses,kind='stable')[:k*n//4]
            assert h['elite_selection']['global_elite_indices']==selected.tolist()
            assigned=selected.reshape(n//4,k).T
            for group in range(k):
                assert h['elite_selection']['assignments'][group]['source_indices']==assigned[group].tolist()
                for individual,index in enumerate(assigned[group]):
                    assert h['population'][group*n+individual]['all_parameters']==previous['population'][index]['all_parameters']
            assert h['loss']<=previous['loss']+1e-10
        rows+=len(h['population'])
        problem.retain(params)
    with gzip.open(folder/'population_history.csv.gz','rt',encoding='utf-8') as stream:
        csv_rows=list(csv.DictReader(stream))
    assert len(csv_rows)==rows
    for row,p in zip(csv_rows,(p for h in histories for p in h['population'])):
        assert [float(row[key]) for key in ('H0','Omega_m','M')]==p['all_parameters']
        assert float(row['chi2'])==p['chi2']
    for generation,e in enumerate(executions,1):
        assert e==json.loads((folder/'executions'/f'g{generation:03d}.json').read_text())
        assert e['generation']==generation and len(e['stage_measurements'])==4*k
        ideals=np.load(folder/'ideal_probabilities'/f'g{generation:03d}.npz')['probabilities']
        assert ideals.shape==(k,4,n) and np.allclose(ideals.sum(axis=-1),1,atol=1e-10)
        for stage,r in enumerate(e['packed_stage_results']):
            histogram=r['histogram']
            assert sum(histogram.values())==shots
            if summary['mode']=='noisy':
                cloud=folder/'cloud'/f'g{generation:03d}'/f's{stage}'
                request=json.loads((cloud/'request.json').read_text())
                result=json.loads((cloud/'result.json').read_text())
                job=json.loads((cloud/'job.json').read_text())
                native=json.loads((cloud/'compiled_native.json').read_text())
                assert request['backend']=='simulator' and request['noise']['model']=='forte-1'
                assert request['input']['qubits']==summary['used_qubits'] and request['shots']==shots
                assert request['noise']['seed']==e['stage_noise_seeds'][stage]
                assert result['request_sha256']==digest(request)==r['request_sha256']
                assert result['histogram']==histogram and job['status']=='completed'
                assert job['id']==result['job_id']==r['job_id'] and r['job_id'] not in jobs
                assert job['backend']=='simulator' and job['noise']['model']=='forte-1'
                jobs.add(r['job_id'])
                counts=Counter(g['gate'] for g in native['circuit'])
                touched=set()
                for gate in native['circuit']:
                    for key in ('target','control'):
                        if key in gate:touched.add(gate[key])
                    for key in ('targets','controls'):touched.update(gate.get(key,[]))
                resource_rows.append({'generation':generation,'stage':stage,'job_id':r['job_id'],
                    'requested_register_qubits':summary['used_qubits'],'native_register_qubits':native['qubits'],
                    'native_touched_wires':len(touched),'native_gpi':counts['gpi'],
                    'native_gpi2':counts['gpi2'],'native_zz':counts['zz'],
                    'submitted_at':job['submitted_at'],'started_at':job.get('started_at'),
                    'completed_at':job.get('completed_at'),'local_job_wall_seconds':result['wall_seconds']})
            for group in range(k):
                measured=marginal(histogram,q,group)
                recorded=e['stage_measurements'][group*4+stage]
                assert (recorded['subpopulation_index'],recorded['stage_index'])==(group,stage)
                other=np.zeros(n,dtype=int)
                for bits,count in recorded['counts'].items():other[int(bits,2)]+=count
                np.testing.assert_array_equal(measured,other)
                diagnostic=e['stage_diagnostics'][group*4+stage]
                assert abs(np.abs(measured/shots-ideals[group,stage]).sum()/2-diagnostic['counts_vs_ideal_tvd'])<1e-10
    cloud_elapsed=None
    if resource_rows:
        csv_write(folder/'cloud_resources.csv',resource_rows)
        stamp=lambda value:datetime.fromisoformat(value.replace('Z','+00:00'))
        first=min(stamp(r['submitted_at']) for r in resource_rows)
        cloud_elapsed=(max(stamp(r['completed_at']) for r in resource_rows)-first).total_seconds()
        csv_write(folder/'cloud_timing_history.csv',[
            {'generation':g,'cloud_calendar_elapsed_seconds':(
                max(stamp(r['completed_at']) for r in resource_rows if r['generation']<=g)-first).total_seconds()}
            for g in range(1,generations+1)])
    replay_candidates(histories,executions,summary)
    return {'case':folder.name,'candidate_rows':rows,'stage_histograms':generations*k*4,
            'cloud_jobs':len(jobs),'max_64_node_chi2_difference':maximum_chi,
            'cloud_first_submit_to_last_completion_seconds':cloud_elapsed,
            'max_64_node_profiled_M_difference':maximum_m,
            'scalar_audit_rechecks':scalar_rechecks,
            'exact_preparation_fallbacks':sum('state_preparation_fallback' in d for e in executions for d in e['stage_diagnostics']),
            'all_candidate_parameters_reproduced_from_saved_counts':True,'status':'passed'}


def read_csv(path):
    with Path(path).open(newline='',encoding='utf-8') as file:
        return [{key:float(value) for key,value in row.items()} for row in csv.DictReader(file)]


def figures(output,summaries,plan):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    noisy=sorted([s for s in summaries if s['mode']=='noisy'],key=lambda s:s['width'])
    ideal=sorted([s for s in summaries if s['mode']=='ideal'],key=lambda s:s['width'])
    histories={(s['width'],s['mode']):read_csv(output/f'q{s["width"]}_{s["mode"]}'/'best_history.csv') for s in summaries}
    fig=Figure(figsize=(16,10),layout='constrained');FigureCanvasAgg(fig)
    axes=fig.subplots(2,3)
    for group,color,label in [(noisy,'#b91c1c','Official Forte-1 noise'),(ideal,'#64748b','Local ideal, 100 shots')]:
        axes[0,0].plot([s['width'] for s in group],[max(s['delta_chi2'],1e-10) for s in group],'o-',color=color,label=label)
    axes[0,0].set(xlabel='Qubits per subpopulation',ylabel='Final excess chi-square',yscale='log',title='A. Final fit after 100 generations')
    axes[0,0].legend(fontsize=9)
    for s in noisy:
        h=histories[(s['width'],'noisy')]
        axes[0,1].plot([r['generation'] for r in h],[max(r['delta_chi2'],1e-10) for r in h],color=COLORS[s['width']],label=f'{s["width"]}q')
        axes[0,2].plot([r['fitness_evaluations'] for r in h],[max(r['delta_chi2'],1e-10) for r in h],color=COLORS[s['width']],label=f'{s["width"]}q')
    axes[0,1].set(xlabel='Generation (0 = initialization)',ylabel='Excess chi-square',yscale='log',title='B. Noisy training progress')
    axes[0,1].legend(ncol=3,fontsize=9)
    axes[0,2].set(xlabel='Cumulative candidate evaluations',ylabel='Excess chi-square',yscale='log',title='C. Search effort')
    for j,(key,label) in enumerate([('mean_counts_vs_ideal_tvd','Observed-to-ideal TVD'),('mean_zero_fraction','Zero-count fraction of candidate bins')]):
        for group,color,name in [(noisy,'#b91c1c','Forte-1'),(ideal,'#64748b','Ideal + sampling')]:
            axes[1,j].plot([s['width'] for s in group],[s['mean_metrics'][key] for s in group],'o-',color=color,label=name)
        axes[1,j].set(xlabel='Qubits per subpopulation',ylabel=label,title=['D. Noise + sampling + compiler effects','E. Finite-shot sparsity'][j])
        axes[1,j].legend(fontsize=9)
    zz=[]
    for s in noisy:
        with (output/f'q{s["width"]}_noisy'/'cloud_resources.csv').open() as f:r=list(csv.DictReader(f))
        zz.append(sum(int(x['native_zz']) for x in r)/(s['generations']*s['parallel_circuits']))
    axes[1,2].plot([s['width'] for s in noisy],zz,'o-',color='#2563eb')
    axes[1,2].set(xlabel='Qubits per subpopulation',ylabel='Mean native ZZ gates / group / generation',title='F. Official compiled circuit cost')
    for ax in axes.flat:ax.grid(alpha=.2)
    fig.suptitle('Official IonQ Forte-1 simulator | 29-qubit budget | 100 generations | 100 shots per stage | seed 7',fontsize=14)
    fig.savefig(output/'training_comparison.png',dpi=180);fig.savefig(output/'training_comparison.svg')
    final=Figure(figsize=(15,4.6),layout='constrained');FigureCanvasAgg(final)
    ff=final.subplots(1,3)
    for j,label in enumerate(['H0 [km/s/Mpc]','Omega_m','Profiled M [mag]']):
        for group,color,name in [(noisy,'#b91c1c','Forte-1'),(ideal,'#64748b','Ideal + sampling')]:
            ff[j].plot([s['width'] for s in group],[s['best_parameters'][j] for s in group],'o-',color=color,label=name)
        ff[j].axhline(plan['reference']['p'][j],color='#0f766e',ls='--',label='Classical reference')
        ff[j].set(xlabel='Qubits per subpopulation',ylabel=label,title=label)
        ff[j].ticklabel_format(axis='y',style='plain',useOffset=False);ff[j].grid(alpha=.2)
    ff[0].legend(fontsize=8)
    final.suptitle('Final fitted parameters versus circuit width (generation 100)',fontsize=15)
    final.savefig(output/'final_parameters_vs_qubits.png',dpi=180)
    for s in noisy:
        q=s['width'];f=Figure(figsize=(12,8),layout='constrained');FigureCanvasAgg(f);aa=f.subplots(2,2)
        for mode,color,name in [('noisy','#b91c1c','Forte-1'),('ideal','#64748b','Ideal + sampling')]:
            h=histories[(q,mode)]
            for ax,key in zip(aa.flat,['H0','Omega_m','M','delta_chi2']):
                ax.plot([r['generation'] for r in h],[max(r[key],1e-10) if key=='delta_chi2' else r[key] for r in h],label=name,color=color)
        for j,(ax,key) in enumerate(zip(aa.flat,['H0','Omega_m','M','delta_chi2'])):
            ax.set(xlabel='Generation',ylabel=key,title=key);ax.grid(alpha=.2)
            if key=='delta_chi2':ax.set_yscale('log')
            else:ax.axhline(plan['reference']['p'][j],ls='--',color='#0f766e');ax.ticklabel_format(axis='y',useOffset=False)
        aa[0,0].legend(fontsize=9)
        f.suptitle(f'{q} qubits/group | {s["parallel_circuits"]} groups | {s["used_qubits"]}/29 qubits | {s["total_population"]} candidates',fontsize=14)
        f.savefig(output/f'q{q}_parameter_histories.png',dpi=160)


def report(output,summaries,plan,audits):
    noisy=sorted([s for s in summaries if s['mode']=='noisy'],key=lambda s:s['width'])
    ideal={s['width']:s for s in summaries if s['mode']=='ideal'}
    rows=[]
    for s in noisy:
        t=s['thresholds']['0.001']
        rows.append({'qubits_per_subpopulation':s['width'],'parallel_subpopulations':s['parallel_circuits'],
            'used_qubits':s['used_qubits'],'discarded_qubits':s['discarded_qubits'],
            'total_candidates':s['total_population'],'H0':s['best_parameters'][0],
            'Omega_m':s['best_parameters'][1],'M':s['best_parameters'][2],
            'noisy_chi2':s['chi2'],'noisy_delta_chi2':s['delta_chi2'],
            'ideal_delta_chi2':ideal[s['width']]['delta_chi2'],
            'first_generation_delta_le_0_001':None if t is None else t['generation'],
            'evaluations_at_delta_le_0_001':None if t is None else t['fitness_evaluations'],
            'total_evaluations':s['fitness_evaluations'],
            'mean_observed_vs_ideal_tvd':s['mean_metrics']['mean_counts_vs_ideal_tvd'],
            'mean_zero_count_fraction':s['mean_metrics']['mean_zero_fraction'],
            'latest_runner_pass_wall_seconds':s['training_wall_seconds'],
            'cloud_first_submit_to_last_completion_seconds':next(a['cloud_first_submit_to_last_completion_seconds'] for a in audits if a['case']==f'q{s["width"]}_noisy')})
    csv_write(output/'comparison.csv',rows)
    lines=['IONQ FORTE-1 NOISE WIDTH STUDY','',
        'Execution: official IonQ Quantum Cloud backend=simulator, noise.model=forte-1.',
        'No quantum hardware was used. Official model internals are not downloaded or reproduced locally.',
        '100 evolutionary updates plus generation 0; 100 shots for EACH of four stages per generation.',
        'Four stages = H0/local, H0/global, Omega_m/local, Omega_m/global.',
        'Each submitted stage packs all subpopulations onto disjoint logical wires.',
        'The 29-qubit budget is truncated to floor(29/q)*q; no heterogeneous remainder group.',
        'Declared/allocated wires can differ from wires touched after compiler optimization.',
        'Native compiled gate lists and actual touched-wire counts are archived.',
        'All cloud outcomes are genuine returned finite-shot histograms, not locally generated noise.',
        '', 'METHOD',
        'Same Pantheon+SH0ES selection and full covariance as the Marrakesh experiment (1657 observations).',
        'H0 bounds [60,80], Omega_m bounds [0.1,0.5], M bounds [-19.6,-19.0].',
        'M is profiled for EVERY candidate: clip((1^T C^-1 (m-mu))/(1^T C^-1 1), M bounds).',
        'Each group has 2^q candidates, with elite:local:global counts 1:1:2.',
        'Each generation selects global elites and deals them to groups round-robin by rank.',
        'Same crossover probability 0.5, mutation probability 0.5, local padding 0.5, minimum width 0.01.',
        'Seed 7; separate deterministic cloud noise seeds recorded for every stage.',
        'Preparation is synthesized into rx/ry/rz/cnot QIS gates at optimization level 1.',
        'If isometry synthesis changes probabilities by TVD > 2e-6, an exact real-amplitude rotation tree at optimization level 0 is used.',
        'This numerical fallback retains the original 2e-6 validation bound and is recorded per stage.',
        'IonQ then applies its official compiler to Forte native GPi/GPi2/ZZ gates.',
        'The previous repeated reset/measure sequence is split into independent initialized jobs.',
        'Sorted pairing across stage histograms is an internal adapter only; it is NOT measured cross-stage correlation.',
        'Only the stage marginal counts are used in candidate decoding.',
        'Ideal controls are locally sampled from exact QIS statevectors with 100 shots, not cloud ideal probabilities.',
        'No local substitute is used for official noise. Ideal/noisy runs start from identical populations.',
        '', 'CLASSICAL REFERENCE',json.dumps(plan['reference']), '', 'RESULTS',
        'q | groups | used wires | candidates | final noisy delta chi2 | final ideal delta chi2 | first generation delta<=0.001']
    for r in rows:
        lines.append(f"{r['qubits_per_subpopulation']} | {r['parallel_subpopulations']} | {r['used_qubits']} | {r['total_candidates']} | {r['noisy_delta_chi2']:.10g} | {r['ideal_delta_chi2']:.10g} | {r['first_generation_delta_le_0_001']}")
    best=min(noisy,key=lambda s:s['delta_chi2'])
    lines += ['',f'Among these single-seed noisy runs, the lowest final chi-square occurred at q={best["width"]}: {best["chi2"]:.12f}.',
        '', 'INTERPRETATION LIMITS',
        'One seed per configuration; there are no confidence intervals or claims of an optimal width.',
        'Width changes candidates per group, number of groups, proposal distributions, circuit gates, and sampling sparsity.',
        'Observed-to-ideal TVD combines hardware-model noise, finite-shot variation, and official compiler approximation.',
        'Exact noisy probabilities are unavailable; this metric does not isolate noise from sampling.',
        'More candidate evaluations are classical likelihood evaluations; fewer generations do not establish quantum speedup.',
        'Checkpoint and summary wall times describe the latest runner pass; replaying cached generations does not wait again.',
        'cloud_timing_history.csv reconstructs elapsed calendar time from original cloud submissions and completions, including interruptions.',
        'Cloud calendar time includes scheduling, simulation and gaps; local runner time also includes preparation and objective calculation.',
        'It is not a measurement of QPU gate execution time or physical gate parallelism.',
        'Changing the budget from Marrakesh 156 to IonQ 29 changes total candidate counts; raw outcomes do not isolate vendor noise.',
        'The decoder replaces lower-bound/zero-bin outcomes with classical uniform draws, as in the original implementation.',
        'For wider circuits this can increase random exploration; a lower chi-square alone does not demonstrate improved quantum sampling.',
        'IonQ describes its noise model as approximate and not a guarantee of specific real-device performance.',
        'The current Forte model is a versioned cloud service and may change; request seeds alone do not freeze future results.',
        'Saved responses, task metadata, compiled artifacts and file hashes preserve the evidence from this run.',
        '', 'VALIDATION',f'Total candidate rows: {sum(a["candidate_rows"] for a in audits)}',
        f'Total training cloud jobs: {sum(a["cloud_jobs"] for a in audits)} (plus one asymmetric preflight).',
        'All generations, elite transfers, 100-shot sums, packed-to-group marginals, and CSV/JSON parameter records checked.',
        'Every candidate likelihood and profiled M checked using 64-node quadrature; training used 32 nodes.',
        'Candidate parameters reproduced from seed 7, saved stage counts, and independently checked objective values.',
        f'Scalar recalculations for rows exceeding the initial batch tolerance: {sum(a["scalar_audit_rechecks"] for a in audits)}.',
        f'Exact state-preparation fallbacks: {sum(a["exact_preparation_fallbacks"] for a in audits)}.',
        '', 'SOURCES',
        'https://docs.ionq.com/features/simulation-with-noise-models',
        'https://docs.ionq.com/features/getting-started-with-native-gates',
        'https://docs.ionq.com/api-reference/v0.4/jobs/create-job',
        'https://docs.ionq.com/api-reference/v0.4/jobs/get-job-artifact']
    (output/'findings.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def package(output,plan):
    reproduction=output/'reproduction';reproduction.mkdir(exist_ok=True)
    for name in SOURCES+['test_ionq_forte.py','analyze_ionq_forte_study.py','resume_ionq_precision.py','run_ionq_forte_precision_study.py','monitor_ionq_forte_study.py','run_ionq_forte_resilient.py','test_ionq_transport_recovery.py','supervise_ionq_forte.py','test_ionq_supervisor.py','keep_ionq_training_awake.py']:
        shutil.copy2(ROOT/name,reproduction/name)
    data_dir=reproduction/'Pantheon+_Data'/'4_DISTANCES_AND_COVAR';data_dir.mkdir(parents=True,exist_ok=True)
    for name in ('Pantheon+SH0ES.dat','Pantheon+SH0ES_STAT+SYS.cov'):
        shutil.copy2(ROOT/'Pantheon+_Data'/'4_DISTANCES_AND_COVAR'/name,data_dir/name)
    for name in ('README.md','LICENSE','LICENSE.txt'):
        if (ROOT/'Pantheon+_Data'/name).exists():shutil.copy2(ROOT/'Pantheon+_Data'/name,reproduction/'Pantheon+_Data'/name)
    versions=plan['provenance']['versions']
    (reproduction/'requirements.txt').write_text('\n'.join(f'{k}=={v}' for k,v in versions.items())+'\nthreadpoolctl=='+importlib.metadata.version('threadpoolctl')+'\n',encoding='utf-8')
    (output/'README.txt').write_text(
        'Official IonQ Forte-1 study: full training records and runnable code.\n\n'
        'Start with findings.txt, comparison.csv, training_comparison.png and final_parameters_vs_qubits.png.\n'
        'Each qN_noisy / qN_ideal folder includes all candidates in population_history.csv.gz and training_history.jsonl.gz,\n'
        'all stage measurements in execution_history.jsonl.gz, and per-generation checkpoints.\n'
        'Noisy cloud/ folders contain every exact submission, job ID, native compiled circuit and returned histogram.\n'
        'cloud_timing_history.csv uses original server timestamps; runner wall times reflect the latest pass after cache replay.\n'
        'ideal_probabilities/ are local logical QIS references, NOT exact Forte noisy probabilities.\n\n'
        'Reproduction (Python 3.11):\n'
        '  cd reproduction\n'
        '  python -m pip install -r requirements.txt\n'
        '  python -m unittest -v test_ionq_forte\n'
        '  Set IONQ_API_KEY as an environment variable (do not place it in source or result files).\n'
        '  python supervise_ionq_forte.py --output output/ionq_forte_29q --workers 6\n'
        '  For separate offline analysis: python analyze_ionq_forte_study.py --output output/ionq_forte_29q\n\n'
        'Default run uses the official free simulator only, never a QPU. Cloud access and availability are required.\n'
        'Run the same command again to replay saved completed requests and continue unfinished cases.\n'
        'A timed-out POST is not automatically repeated because the service might have accepted it.\n'
        'The supervisor retries recoverable process failures after 60--300 seconds, using the same saved job IDs.\n'
        'Set training_control.json desired_state to paused to stop the supervisor and its training child.\n'
        'The supervisor does not register an automatic startup task after a Windows reboot.\n'
        'Do not change code/configuration in an existing run directory; source hashes are checked.\n'
        'Cloud service model/compiler updates can change future results despite identical seeds.\n'
        'Stored records support offline audit; the original run is fully archived here.\n'
        'API credentials are not included.\n',encoding='utf-8')
    manifest=output/'SHA256SUMS.txt'
    files=sorted(p for p in output.rglob('*') if p.is_file() and p!=manifest
                 and p.name not in ('runner_status.json','progress.json','progress.png','progress.txt','progress_snapshot.json',
                    'supervisor_status.json','supervisor_events.jsonl','supervisor.lock','supervisor_helpers.log','training_control.json')
                 and 'supervisor_logs' not in p.parts
                 and p.suffix!='.tmp' and '__pycache__' not in p.parts)
    manifest.write_text(''.join(f'{sha(p)}  {p.relative_to(output).as_posix()}\n' for p in files),encoding='utf-8')
    archive=output.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[manifest]:z.write(p,Path(output.name)/p.relative_to(output))
    with zipfile.ZipFile(archive) as z:
        bad=z.testzip()
        if bad:raise AssertionError('ZIP CRC failure: '+bad)
    archive.with_suffix('.zip.sha256').write_text(f'{sha(archive)}  {archive.name}\n',encoding='utf-8')
    print(f'ARCHIVE {archive} {archive.stat().st_size} bytes',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'output'/'ionq_forte_29q')
    args=parser.parse_args();output=args.output.resolve()
    plan=json.loads((output/'study_plan.json').read_text())
    summaries=json.loads((output/'study_summary.json').read_text())
    assert len(summaries)==len(plan['widths'])*len(plan['modes'])
    for name,expected in plan['provenance']['source_sha256'].items():assert sha(ROOT/name)==expected
    audits=[]
    with threadpool_limits(limits=1):
        problem=ProfiledPantheon(order=64)
        for s in summaries:
            case=output/f'q{s["width"]}_{s["mode"]}'
            audits.append(audit_case(case,s,problem))
            print('AUDITED',case.name,flush=True)
    for q in plan['widths']:
        assert json.loads((output/f'q{q}_noisy/generations/g000.json').read_text())['population']==json.loads((output/f'q{q}_ideal/generations/g000.json').read_text())['population']
    write_json(output/'audit.json',{'status':'passed','cases':audits})
    figures(output,summaries,plan)
    report(output,summaries,plan,audits)
    package(output,plan)


if __name__=='__main__':main()
