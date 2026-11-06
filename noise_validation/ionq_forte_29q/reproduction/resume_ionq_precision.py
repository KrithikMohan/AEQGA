"""Resume a case with tighter isometry synthesis only after a TVD guard failure.

Original runner/core remain unchanged. This extension and its SHA256 are
recorded separately. Normal circuits and all cached cloud requests are unchanged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from qiskit import QuantumCircuit,transpile
from qiskit.circuit.library import UCRYGate
from qiskit.quantum_info import Statevector
import aeqga_ionq_cloud as core
from run_ionq_forte_study import run_case

original_compile=core.compile_qis


def precision_compile(stage,seed):
    try:
        return original_compile(stage,seed)
    except AssertionError as error:
        if not str(error).startswith('QIS synthesis changed probabilities:'):
            raise
        original_tvd=float(str(error).split('TVD=')[1])
    amplitudes=np.asarray(stage.data[0].operation.params,dtype=complex)
    amplitudes=amplitudes/np.linalg.norm(amplitudes)
    tail=QuantumCircuit(stage.num_qubits)
    for item in stage.data[1:]:
        tail.append(item.operation,[stage.find_bit(q).index for q in item.qubits])
    expected=Statevector(amplitudes).evolve(tail).probabilities()
    if np.max(np.abs(amplitudes.imag))>1e-14 or np.min(amplitudes.real)<0:
        raise ValueError('Exact rotation-tree fallback requires nonnegative real amplitudes.')
    # Explicit norm-tree loading avoids approximate identity elimination inside
    # the isometry synthesis. All amplitudes in this study are nonnegative.
    c=QuantumCircuit(stage.num_qubits)
    for target in range(stage.num_qubits-1,-1,-1):
        chunks=amplitudes.real.reshape(-1,2,1<<target)
        norms=np.linalg.norm(chunks,axis=2)
        angles=(2*np.arctan2(norms[:,1],norms[:,0])).tolist()
        c.append(UCRYGate(angles),[target,*range(target+1,stage.num_qubits)])
    c.compose(tail,inplace=True)
    compiled=transpile(c,basis_gates=['rx','ry','rz','cx'],optimization_level=0,seed_transpiler=seed)
    p=Statevector.from_instruction(compiled).probabilities()
    tvd=float(np.abs(p-expected).sum()/2)
    if tvd>2e-6:raise AssertionError('Rotation-tree preparation did not satisfy original TVD bound.')
    gates=[]
    for item in compiled.data:
        wires=[compiled.find_bit(q).index for q in item.qubits]
        if item.operation.name=='cx':gates.append({'gate':'cnot','control':wires[0],'target':wires[1]})
        else:
            assert item.operation.name in ('rx','ry','rz')
            gates.append({'gate':item.operation.name,'target':wires[0],'rotation':float(item.operation.params[0])})
    print(f'Exact rotation tree: original TVD={original_tvd:.9g}, new TVD={tvd:.9g}',flush=True)
    return gates,p,{'synthesis_tvd':tvd,'roundoff_repairs':[],
        'qis_gate_counts':dict(compiled.count_ops()),'qis_depth':compiled.depth(),
        'state_preparation_fallback':'nonnegative-real UCRY norm tree, optimization level 0',
        'original_synthesis_tvd':original_tvd}


core.compile_qis=precision_compile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'output'/'ionq_forte_29q')
    parser.add_argument('--width',type=int,required=True)
    parser.add_argument('--mode',choices=['noisy','ideal'],required=True)
    args=parser.parse_args()
    output=args.output.resolve();plan=json.loads((output/'study_plan.json').read_text())
    core.write_json(output/f'q{args.width}_{args.mode}'/'execution_extension.json',{
        'source':'resume_ionq_precision.py','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'purpose':'Use exact nonnegative-real rotation-tree preparation only when normal synthesis exceeds TVD=2e-6.',
        'changes_normal_path':False,'original_probability_validation_bound_retained':2e-6})
    run_case((str(output),args.width,args.mode,plan['generations'],plan['shots'],plan['seed'],
        plan['requested_qubit_budget'],plan['reference'],plan['provenance']))


if __name__=='__main__':main()
