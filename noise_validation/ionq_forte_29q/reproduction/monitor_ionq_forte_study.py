"""Refresh an explicitly provisional progress image and text while training runs."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from aeqga_ionq_cloud import write_json


def snapshot(output):
    plan=json.loads((output/'study_plan.json').read_text())
    reference=plan['reference']['chi2'];rows=[];histories={}
    for q in plan['widths']:
        row={'width':q,'groups':29//q,'used_qubits':q*(29//q)}
        for mode in plan['modes']:
            files=sorted((output/f'q{q}_{mode}'/'generations').glob('g*.json'))
            history=[json.loads(f.read_text()) for f in files]
            histories[(q,mode)]=history
            row[mode+'_generation']=history[-1]['generation'] if history else -1
            row[mode+'_delta_chi2']=history[-1]['loss']-reference if history else None
            row[mode+'_complete']=(output/f'q{q}_{mode}'/'summary.json').exists()
        rows.append(row)
    status_file=output/'runner_status.json'
    status=json.loads(status_file.read_text()) if status_file.exists() else {'status':'running'}
    now=datetime.now(timezone.utc).isoformat()
    write_json(output/'progress_snapshot.json',{'updated_utc':now,'runner':status,'rows':rows})
    lines=['IONQ FORTE-1 TRAINING PROGRESS (PROVISIONAL)',f'Updated UTC: {now}',
        f'Runner status: {status["status"]}',
        'q | packed groups | used qubits | noisy generation / 100 | ideal generation / 100 | current noisy excess chi2']
    for r in rows:
        delta=r['noisy_delta_chi2']
        lines.append(f'{r["width"]} | {r["groups"]} | {r["used_qubits"]} | {r["noisy_generation"]} | {r["ideal_generation"]} | {delta}')
    lines += ['','Intermediate values are not final width-comparison conclusions.',
        'Each completed generation is saved with all candidates and four 100-shot packed cloud histograms.',
        'Keep the computer running and connected for cloud polling and subsequent generations.',
        'Final files after completion: findings.txt, comparison.csv, training_comparison.png, final_parameters_vs_qubits.png.',
        'The full ZIP archive is written next to this result directory after validation.']
    (output/'progress.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    fig=Figure(figsize=(13,5),layout='constrained');FigureCanvasAgg(fig);axes=fig.subplots(1,2)
    widths=[r['width'] for r in rows]
    axes[0].bar([q-.18 for q in widths],[r['noisy_generation'] for r in rows],width=.35,color='#b91c1c',label='Forte-1 cloud noise')
    axes[0].bar([q+.18 for q in widths],[r['ideal_generation'] for r in rows],width=.35,color='#64748b',label='Local ideal control')
    axes[0].set(xlabel='Qubits per subpopulation',ylabel='Completed generations',ylim=(0,110),xticks=widths)
    axes[0].legend(fontsize=9)
    for q in widths:
        h=histories[(q,'noisy')]
        if h:axes[1].plot([r['generation'] for r in h],[max(r['loss']-reference,1e-10) for r in h],label=f'{q}q')
    axes[1].set(xlabel='Completed generation',ylabel='Excess chi-square',yscale='log',title='Noisy trajectories so far')
    axes[1].legend(ncol=3,fontsize=9)
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('PROVISIONAL - training in progress; not final width comparison',fontsize=14)
    path=output/'progress.png';temporary=output/'progress_image.tmp'
    fig.savefig(temporary,format='png',dpi=150);temporary.replace(path)
    return status['status']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'output'/'ionq_forte_29q')
    parser.add_argument('--interval',type=int,default=60)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    while True:
        status=snapshot(args.output)
        supervisor=args.output/'supervisor_status.json'
        supervised=json.loads(supervisor.read_text()).get('status') if supervisor.exists() else None
        if args.once or status in ('complete','paused_by_user'):break
        if status=='needs_attention' and supervised not in ('running','retry_wait'):break
        time.sleep(args.interval)


if __name__=='__main__':main()
