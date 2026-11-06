"""Official IonQ Forte noise execution for complete AEQGA subpopulations.

Credentials are read from IONQ_API_KEY only. Every cloud target is simulator.
The four reset-separated stages become four independent packed submissions.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
import requests
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import StatePreparation
from qiskit.quantum_info import Statevector

from aeqga import AEQGA


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def split_stages(circuit):
    """Retain preparation and gates, with fresh zero initialization per stage."""
    result, current, measured = [], QuantumCircuit(circuit.num_qubits), set()
    for item in circuit.data:
        name = item.operation.name
        wires = [circuit.find_bit(q).index for q in item.qubits]
        if name == 'barrier':
            continue
        if name == 'measure':
            measured.update(wires)
            if len(measured) == circuit.num_qubits:
                result.append(current)
                current, measured = QuantumCircuit(circuit.num_qubits), set()
            continue
        if measured:
            raise ValueError('Unexpected gate within terminal measurement block.')
        if name == 'initialize':
            if current.data:
                raise ValueError('Initialization must start a fresh stage.')
            current.append(StatePreparation(item.operation.params), wires)
        else:
            current.append(item.operation, wires)
    if current.data or measured or len(result) != len(circuit.metadata['stages']):
        raise ValueError('Incomplete stage extraction.')
    return result


def compile_qis(stage, seed):
    """Convert to explicit QIS gates; check ideal probabilities independently.

    Preserve the same isometry preparation as Marrakesh. Retry only recognized
    floating-point isometry failures and record any sub-1e-14 amplitude repair.
    """
    original = np.asarray(stage.data[0].operation.params, dtype=complex)
    target = Statevector(original / np.linalg.norm(original))
    tail = QuantumCircuit(stage.num_qubits)
    for item in stage.data[1:]:
        tail.append(item.operation, [stage.find_bit(q).index for q in item.qubits])
    expected = target.evolve(tail).probabilities()
    repairs = []
    for attempt, ulps in enumerate((None, 0, 1, -1, 2, -2, 4, -4)):
        candidate = stage.copy()
        if ulps is not None:
            adjusted = original/np.linalg.norm(original)*(1+ulps*np.finfo(float).eps)
            delta = float(np.max(np.abs(adjusted-original)))
            if delta > 1e-14:
                raise AssertionError('Excessive state preparation repair.')
            candidate.data[0] = candidate.data[0].replace(operation=StatePreparation(adjusted))
        try:
            compiled = transpile(candidate, basis_gates=['rx','ry','rz','cx'],
                                 optimization_level=1, seed_transpiler=seed)
            break
        except Exception as exc:
            if 'state_preparation' not in str(exc) and 'not unitary' not in str(exc):
                raise
            if attempt == 7:
                raise
    if ulps is not None:
        repairs.append({'max_amplitude_change':delta, 'ulps':ulps})
    actual = Statevector.from_instruction(compiled).probabilities()
    tvd = float(np.abs(expected-actual).sum()/2)
    if tvd > 2e-6:
        raise AssertionError(f'QIS synthesis changed probabilities: TVD={tvd}')
    gates = []
    for item in compiled.data:
        wires = [compiled.find_bit(q).index for q in item.qubits]
        if item.operation.name == 'cx':
            gates.append({'gate':'cnot', 'control':wires[0], 'target':wires[1]})
        else:
            assert item.operation.name in ('rx','ry','rz')
            gates.append({'gate':item.operation.name,'target':wires[0],
                          'rotation':float(item.operation.params[0])})
    return gates, actual, {'synthesis_tvd':tvd, 'roundoff_repairs':repairs,
                           'qis_gate_counts':dict(compiled.count_ops()), 'qis_depth':compiled.depth()}


def pack_gates(groups, width):
    packed = []
    for group, gates in enumerate(groups):
        for gate in gates:
            item = dict(gate)
            for key in ('target','control'):
                if key in item:
                    item[key] += group*width
            packed.append(item)
    return packed


def marginal(histogram, width, group):
    result = np.zeros(1 << width, dtype=np.int64)
    for value, count in histogram.items():
        result[(int(value) >> (group*width)) & ((1 << width)-1)] += count
    return result


class IonQCloud:
    base = 'https://api.ionq.co/v0.4'

    def __init__(self):
        self.key = os.environ.get('IONQ_API_KEY')
        if not self.key:
            raise RuntimeError('Set IONQ_API_KEY in the environment before cloud execution.')

    def request(self, method, path, **kwargs):
        for attempt in range(9):
            try:
                response = requests.request(method, self.base+path,
                    headers={'Authorization':'apiKey '+self.key}, timeout=(15,90), **kwargs)
            except requests.RequestException:
                if method != 'GET':
                    raise RuntimeError('Submission connection interrupted; inspect cloud jobs before retrying to avoid duplication.') from None
                if attempt == 8:
                    raise RuntimeError('IonQ GET repeatedly failed.') from None
                time.sleep(min(2**attempt, 30)); continue
            if response.status_code == 429 or (method == 'GET' and response.status_code >= 500):
                time.sleep(min(float(response.headers.get('Retry-After',2**attempt)),45)); continue
            if not response.ok:
                raise RuntimeError(f'IonQ {method} {path}: HTTP {response.status_code}: '
                                   + response.text.replace(self.key,'[REDACTED]')[:1200])
            return response.json()
        raise RuntimeError('IonQ request retry limit exceeded.')

    def run(self, payload, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        request_file, result_file = directory/'request.json', directory/'result.json'
        if payload['backend'] != 'simulator' or payload['noise']['model'] != 'forte-1':
            raise ValueError('This runner permits only the official forte-1 noisy simulator.')
        if request_file.exists():
            if json.loads(request_file.read_text()) != payload:
                raise ValueError(f'Cached cloud request differs: {directory}')
        else:
            write_json(request_file,payload)
        if result_file.exists():
            saved = json.loads(result_file.read_text())
            if saved['request_sha256'] != digest(payload):
                raise ValueError('Cached result hash mismatch.')
            return saved
        submission = directory/'submission.json'
        started = time.perf_counter()
        if submission.exists():
            submitted = json.loads(submission.read_text())
        else:
            # Do not automatically repeat ambiguous POST failures.
            submitted = self.request('POST','/jobs',json=payload)
            write_json(submission,submitted)
        job_id = submitted['id']
        status_file = directory/'job.json'
        while True:
            job = self.request('GET','/jobs/'+job_id)
            write_json(status_file,job)
            if job['status'] == 'completed':
                break
            if job['status'] in ('failed','canceled','cancelled'):
                raise RuntimeError(f'Cloud job {job_id}: {job.get("failure") or job["status"]}')
            if time.perf_counter()-started > 14400:
                raise TimeoutError(f'Cloud job {job_id} still pending; resume reuses its job ID.')
            time.sleep(4)
        histogram = self.request('GET',f'/jobs/{job_id}/results/histogram')
        if not isinstance(histogram,dict) or not all(isinstance(n,int) and n >= 0 for n in histogram.values()):
            raise ValueError('Unexpected cloud histogram format.')
        if sum(histogram.values()) != payload['shots']:
            raise ValueError('Cloud histogram shot total mismatch.')
        if any(int(v) < 0 or int(v) >= (1 << payload['input']['qubits']) for v in histogram):
            raise ValueError('Cloud histogram outside submitted qubit register.')
        native = job.get('output',{}).get('compilation',{}).get('compiled_circuits',{}).get('ionq.native.v1')
        if native:
            artifact = self.request('GET',f'/jobs/{job_id}/artifacts/{native["id"]}')
            write_json(directory/'compiled_native.json',artifact)
        saved = {'job_id':job_id,'request_sha256':digest(payload), 'histogram':histogram,
                 'wall_seconds':time.perf_counter()-started, 'job':job}
        write_json(result_file,saved)
        return saved


class ProfiledIonQAEQGA(AEQGA):
    def __init__(self, problem, *, width, qubit_budget=29, mode='noisy',
                 record_directory, shots=100, seed=7):
        groups = qubit_budget//width
        if not 3 <= width <= 8 or qubit_budget > 29 or groups < 1:
            raise ValueError('Require widths 3--8 and a simulator budget at most 29.')
        self.problem, self.mode = problem, mode
        self.record_directory = Path(record_directory)
        # The requested width is explicit: first discard the budget remainder.
        super().__init__(problem.predict,[70.,.3],bounds=problem.bounds,vectorized=True,
                         active_qubits=width*groups,parallel_circuits=groups,shots=shots,seed=seed)
        self.active_qubits = qubit_budget
        self.discarded_qubits = qubit_budget-self.used_active_qubits
        self.cloud = IonQCloud() if mode == 'noisy' else None
        self.objective_seconds = self.quantum_wall_seconds = 0.

    def train(self, *, generations=100, verbose=True):
        self._started = time.perf_counter()
        self.problem.cache.clear()
        return super().train(self.problem.x,self.problem.y,covariance=self.problem.covariance,
                             generations=generations,verbose=verbose)

    def _evaluate_candidates(self, candidates, inputs, targets, scale, cholesky):
        start = time.perf_counter()
        values = self.problem.evaluate(candidates.reshape(-1,2))
        self.n_evaluations_ += len(values)
        self.objective_seconds += time.perf_counter()-start
        return values[:,0].reshape(candidates.shape[:-1])

    def _measure_circuits(self, circuits, seed, rng):
        started = time.perf_counter()
        generation = self.n_generations_+1
        folder = self.record_directory/'cloud'/f'g{generation:03d}'
        compiled = [[compile_qis(stage,seed) for stage in split_stages(c)] for c in circuits]
        seeds = [int(s.generate_state(1)[0] % (2**31-1))+1
                 for s in np.random.SeedSequence([seed,20261030]).spawn(4)]
        payloads = [{'type':'ionq.circuit.v1','backend':'simulator',
            'name':f'AEQGA q{self.qubits_per_circuit} g{generation:03d} stage{s}',
            'shots':self.shots,'noise':{'model':'forte-1','seed':seeds[s]},
            'input':{'qubits':self.used_active_qubits,'gateset':'qis',
                     'circuit':pack_gates([group[s][0] for group in compiled],self.qubits_per_circuit)}}
            for s in range(4)]
        if self.mode == 'noisy':
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda s:self.cloud.run(payloads[s],folder/f's{s}'),range(4)))
        else:
            results = []
            for stage in range(4):
                sampler = np.random.default_rng(seeds[stage])
                samples = np.zeros(self.shots,dtype=np.int64)
                for group in range(self.parallel_circuits):
                    p = compiled[group][stage][1]
                    draws = sampler.choice(len(p),size=self.shots,p=p/p.sum())
                    samples |= draws.astype(np.int64) << (group*self.qubits_per_circuit)
                results.append({'job_id':None,'histogram':{str(v):n for v,n in Counter(map(int,samples)).items()},
                                'request_sha256':digest(payloads[stage])})
        groups, diagnostics, probability_rows = [], [], []
        for group,circuit in enumerate(circuits):
            combined = np.zeros(self.shots,dtype=np.uint64)
            for stage,spec in enumerate(circuit.metadata['stages']):
                counts = marginal(results[stage]['histogram'],self.qubits_per_circuit,group)
                assert counts.sum() == self.shots
                # Only marginals are used by AEQGA. This synthetic pairing is
                # an adapter, NOT observed cross-stage correlations or raw shots.
                expanded = np.repeat(np.arange(len(counts),dtype=np.uint64),counts)
                combined |= expanded << (stage*self.qubits_per_circuit)
                ideal = compiled[group][stage][1]
                diagnostics.append({**spec,'subpopulation_index':group,
                    'counts_vs_ideal_tvd':float(np.abs(counts/self.shots-ideal).sum()/2),
                    'zero_fraction_used_candidates':float(np.mean(counts[:spec['candidate_count']]==0)),
                    **compiled[group][stage][2]})
                probability_rows.append(ideal)
            groups.append({format(v,f'0{4*self.qubits_per_circuit}b'):n for v,n in Counter(map(int,combined)).items()})
        probability_path = self.record_directory/'ideal_probabilities'/f'g{generation:03d}.npz'
        probability_path.parent.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(probability_path,probabilities=np.asarray(probability_rows).reshape(
            self.parallel_circuits,4,1 << self.qubits_per_circuit))
        self.quantum_wall_seconds += time.perf_counter()-started
        self.executed_circuits_ += 4
        self.execution_history_.append({'generation':generation,'mode':self.mode,
            'execution_seed':seed,'stage_noise_seeds':seeds,'shots_per_stage':self.shots,
            'packed_executions':4,'physical_hardware_execution':False,
            'histogram_adapter':'sorted pairing across independently executed stages; only marginals used',
            'stage_diagnostics':diagnostics,'packed_stage_results':[
                {'stage':s,'job_id':r['job_id'],'histogram':r['histogram'],
                 'request_sha256':r['request_sha256']} for s,r in enumerate(results)]})
        return groups

    def _record_subpopulations(self,population,losses,generation,verbose):
        super()._record_subpopulations(population,losses,generation,False)
        record = self.history_[-1]
        values = self.problem.evaluate(population.reshape(-1,2))
        if not np.allclose(values[:,0],losses.ravel(),atol=1e-9,rtol=0):
            raise AssertionError('Profiled likelihood record mismatch.')
        for candidate,(_,m,unconstrained) in zip(record['population'],values):
            candidate.update({'M_profiled':float(m),'M_unconstrained':float(unconstrained),
                              'M_at_bound':bool(m != unconstrained),'all_parameters':[*candidate['p'],float(m)]})
        record.update({'all_parameters':record['population'][record['best_index']]['all_parameters'],
                       'fitness_evaluations':self.n_evaluations_,
                       'elapsed_wall_seconds':time.perf_counter()-self._started,
                       'objective_seconds_cumulative':self.objective_seconds,
                       'quantum_wall_seconds_cumulative':self.quantum_wall_seconds})
        self.problem.retain(population)
        write_json(self.record_directory/'generations'/f'g{generation:03d}.json',record)
        if generation:
            write_json(self.record_directory/'executions'/f'g{generation:03d}.json',self.execution_history_[-1])
        if verbose and (generation % 5 == 0 or generation == 1):
            print(f'q={self.qubits_per_circuit} {self.mode} generation={generation} '
                  f'chi2={self.loss_:.10f} elapsed={record["elapsed_wall_seconds"]:.1f}s',flush=True)
