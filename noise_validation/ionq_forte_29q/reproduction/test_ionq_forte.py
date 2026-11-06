"""Offline validation of cloud conversion, packing, decoding and selection."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import StatePreparation
from qiskit.quantum_info import Statevector
from aeqga import AEQGA
from aeqga_ionq_cloud import (compile_qis,split_stages,pack_gates,marginal,
                              ProfiledIonQAEQGA,IonQCloud,write_json,digest)
from aeqga_profiled_pantheon import ProfiledPantheon


class IonQTests(unittest.TestCase):
    def test_exact_fallback_against_requested_state_and_genetic_gates(self):
        import resume_ionq_precision as extension
        rng=np.random.default_rng(69)
        for q in range(3,9):
            a=np.zeros(1<<q)
            a[:1<<(q-2)]=1+rng.uniform(0,1e-5,size=1<<(q-2))
            a/=np.linalg.norm(a)
            stage=QuantumCircuit(q)
            stage.append(StatePreparation(a),range(q))
            stage.cry(np.pi/2,q-1,0);stage.cry(np.pi/2,0,q-1);stage.rx(np.pi/2,1)
            tail=QuantumCircuit(q)
            tail.cry(np.pi/2,q-1,0);tail.cry(np.pi/2,0,q-1);tail.rx(np.pi/2,1)
            expected=Statevector(a).evolve(tail).probabilities()
            with patch.object(extension,'original_compile',side_effect=AssertionError('QIS synthesis changed probabilities: TVD=4.1e-06')):
                gates,p,info=extension.precision_compile(stage,7)
            np.testing.assert_allclose(p,expected,atol=1e-12,rtol=0)
            self.assertLess(info['synthesis_tvd'],1e-12)

    def test_stage_conversion_and_pack_order(self):
        a=AEQGA(lambda x,p:np.zeros(len(x)),[70.,.3],bounds=[(60,80),(.1,.5)],active_qubits=6,parallel_circuits=2)
        rng=np.random.default_rng(17)
        elites=np.array([[69,.2],[73,.3]])
        random=np.array([[65,.13],[75,.2],[77,.35],[68,.4]])
        c=a._subpopulation_circuit(elites,random,rng,0)
        stages=split_stages(c)
        self.assertEqual(len(stages),4)
        for stage in stages:
            gates,p,info=compile_qis(stage,7)
            rebuilt=QuantumCircuit(3)
            for g in gates:
                if g['gate']=='cnot': rebuilt.cx(g['control'],g['target'])
                else: getattr(rebuilt,g['gate'])(g['rotation'],g['target'])
            np.testing.assert_allclose(Statevector.from_instruction(rebuilt).probabilities(),p,atol=1e-9)
            self.assertLess(info['synthesis_tvd'],2e-6)
        packed=pack_gates([[{'gate':'cnot','control':0,'target':2}]]*2,3)
        self.assertEqual(packed[1],{'gate':'cnot','control':3,'target':5})

    def test_marginals_from_non_symmetric_packed_histogram(self):
        hist={'17':40,'42':60} # (group1,group0)=(2,1),(5,2)
        np.testing.assert_array_equal(marginal(hist,3,0),[0,40,60,0,0,0,0,0])
        np.testing.assert_array_equal(marginal(hist,3,1),[0,0,40,0,0,60,0,0])

    def test_budget_width_remainders_and_elites(self):
        class Problem:
            bounds=[(60,80),(.1,.5)]
            def predict(self,x,p):return np.zeros(len(x))
        for q,k,used in [(3,9,27),(4,7,28),(5,5,25),(6,4,24),(7,4,28),(8,3,24)]:
            a=ProfiledIonQAEQGA(Problem(),width=q,mode='ideal',record_directory='unused')
            self.assertEqual((a.qubits_per_circuit,a.parallel_circuits,a.used_active_qubits),(q,k,used))
            self.assertEqual(a.discarded_qubits,29-used)
            self.assertEqual([a.elite_count,a.local_count,a.random_count],[2**(q-2),2**(q-2),2**(q-1)])
            pop=np.arange(k*2**q*2).reshape(k,2**q,2)
            losses=np.arange(k*2**q)[::-1].reshape(k,2**q)
            e,s=a._select_elites(pop,losses,np.random.default_rng(1),1)
            expected=np.argsort(losses.ravel(),kind='stable')[:k*a.elite_count].reshape(a.elite_count,k).T
            np.testing.assert_array_equal(e,pop.reshape(-1,2)[expected])

    def test_cache_avoids_resubmission_and_rejects_changes(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict('os.environ',{'IONQ_API_KEY':'test-placeholder'}):
            cloud=IonQCloud()
            payload={'backend':'simulator','noise':{'model':'forte-1'}}
            write_json(Path(tmp)/'request.json',payload)
            write_json(Path(tmp)/'result.json',{'request_sha256':digest(payload),'histogram':{'0':100}})
            with patch.object(cloud,'request',side_effect=AssertionError('No API expected')):
                self.assertEqual(cloud.run(payload,tmp)['histogram'],{'0':100})
                with self.assertRaises(ValueError):cloud.run({**payload,'shots':99},tmp)
                with self.assertRaises(ValueError):cloud.run({**payload,'backend':'qpu.forte-1'},tmp)

    def test_profiled_training_and_full_candidate_records(self):
        x=np.array([[.05,.05,0,0],[.1,.1,0,0],[.01,.01,1,31.]])
        y=np.array([17.5,19.,11.8])
        p=ProfiledPantheon(data=(x,y,np.eye(3)*.01))
        with tempfile.TemporaryDirectory() as tmp:
            a=ProfiledIonQAEQGA(p,width=3,qubit_budget=6,mode='ideal',record_directory=tmp)
            a.train(generations=2,verbose=False)
            self.assertEqual(len(a.history_),3)
            for h in a.history_:
                self.assertEqual(len(h['population']),16)
                for c in h['population']:
                    self.assertEqual(len(c['all_parameters']),3)
                    self.assertAlmostEqual(p.direct_check(c['p'],c['M_profiled']),c['chi2'],places=7)
            for e in a.execution_history_:
                for s in e['stage_measurements']: self.assertEqual(sum(s['counts'].values()),100)
            self.assertTrue(all(a.history_[i+1]['loss']<=a.history_[i]['loss'] for i in range(2)))


if __name__=='__main__': unittest.main()
