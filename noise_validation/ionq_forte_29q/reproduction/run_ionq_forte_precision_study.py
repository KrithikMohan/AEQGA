"""Complete/resume the Forte study with exact preparation fallback and analysis."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time
import traceback
import resume_ionq_precision  # installs deterministic guarded preparation fallback in every worker
from run_ionq_forte_study import run_case,SOURCES,sha
from aeqga_ionq_cloud import write_json,IonQCloud


def initialize_plan(output):
    """Create a fresh default study without first starting the legacy runner."""
    from aeqga_profiled_pantheon import ProfiledPantheon
    from threadpoolctl import threadpool_limits
    root=Path(__file__).resolve().parent
    with threadpool_limits(limits=2):reference=ProfiledPantheon().reference()
    provenance={'source_sha256':{name:sha(root/name) for name in SOURCES},
        'data_sha256':{name:sha(root/'Pantheon+_Data'/'4_DISTANCES_AND_COVAR'/name)
                      for name in ('Pantheon+SH0ES.dat','Pantheon+SH0ES_STAT+SYS.cov')},
        'versions':{name:importlib.metadata.version(name) for name in
                    ('numpy','scipy','qiskit','qiskit-aer','requests','pandas','matplotlib')}}
    plan={'widths':list(range(3,9)),'modes':['noisy','ideal'],'generations':100,'shots':100,
        'seed':7,'requested_qubit_budget':29,'model':'official IonQ Cloud forte-1',
        'backend':'simulator','reference':reference,'provenance':provenance,
        'four_stages_per_generation':True,'configuration':[
            {'width':q,'groups':29//q,'used_qubits':q*(29//q),'population':(29//q)*(1<<q)} for q in range(3,9)]}
    write_json(output/'study_plan.json',plan)
    preflight=IonQCloud().run({'type':'ionq.circuit.v1','backend':'simulator',
        'name':'AEQGA asymmetric bit-order validation','shots':100,
        'noise':{'model':'forte-1','seed':91},'input':{'qubits':3,'gateset':'qis',
            'circuit':[{'gate':'x','target':0}]}},output/'preflight')
    if preflight['histogram'].get('1',0)<80:raise AssertionError('Cloud bit-order validation failed.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'output'/'ionq_forte_29q')
    parser.add_argument('--workers',type=int,default=6)
    parser.add_argument('--analyze',action='store_true')
    args=parser.parse_args();output=args.output.resolve()
    if not (output/'study_plan.json').exists():initialize_plan(output)
    plan=json.loads((output/'study_plan.json').read_text())
    extension=Path(resume_ionq_precision.__file__)
    extension_identity={'source':extension.name,'source_sha256':hashlib.sha256(extension.read_bytes()).hexdigest(),
        'purpose':'Exact nonnegative-real UCRY preparation only if isometry probability TVD exceeds 2e-6.',
        'normal_path_unchanged':True,'cached_cloud_requests_compared_exactly_before_reuse':True}
    specs=[]
    for mode in plan['modes']:
        for q in plan['widths']:
            folder=output/f'q{q}_{mode}'
            if not (folder/'summary.json').exists():write_json(folder/'execution_extension.json',extension_identity)
            specs.append((str(output),q,mode,plan['generations'],plan['shots'],plan['seed'],
                          plan['requested_qubit_budget'],plan['reference'],plan['provenance']))
    write_json(output/'runner_status.json',{'status':'running','started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                                          'runner':Path(__file__).name})
    summaries=[];failures=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run_case,s):(s[1],s[2]) for s in specs}
        for future in as_completed(futures):
            case=futures[future]
            try:
                summaries.append(future.result())
            except Exception as error:
                # Report a failure immediately; keep all other independent cases running.
                failure={'width':case[0],'mode':case[1],'error':str(error),'traceback':traceback.format_exc()}
                failures.append(failure);print('CASE FAILED',case,str(error),flush=True)
            write_json(output/'progress.json',{'completed_cases':[(s['width'],s['mode']) for s in summaries],
                                               'failures':failures})
    if failures:
        write_json(output/'runner_status.json',{'status':'needs_attention','failures':failures})
        raise RuntimeError('Some cases failed; see progress.json. Completed cloud responses remain cached.')
    summaries.sort(key=lambda s:(s['width'],s['mode']))
    write_json(output/'study_summary.json',summaries)
    if args.analyze:
        from analyze_ionq_forte_study import main as analyze
        sys.argv=['analyze_ionq_forte_study.py','--output',str(output)]
        analyze()
    write_json(output/'runner_status.json',{'status':'complete','completed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    print('STUDY, VALIDATION, FIGURES AND ARCHIVE COMPLETE',flush=True)


if __name__=='__main__':main()
