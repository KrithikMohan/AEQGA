import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import supervise_ionq_forte as supervisor


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output=Path(self.temp.name)
        supervisor.save(self.output/'training_control.json',{'desired_state':'running'})

    def test_crash_restarts_same_output_and_finishes(self):
        calls=[]
        error=self.output/'stderr.log';error.write_text('')
        def launch(output,workers,attempt):
            calls.append((output,workers,attempt))
            if attempt==2:supervisor.save(output/'runner_status.json',{'status':'complete'})
            return SimpleNamespace(pid=100+attempt,returncode=1 if attempt==1 else 0,
                                   poll=lambda:1 if attempt==1 else 0),error
        with patch.object(supervisor,'launch_training',side_effect=launch),patch.object(supervisor.time,'sleep'):
            supervisor.supervise(self.output,6)
        self.assertEqual(calls,[(self.output,6,1),(self.output,6,2)])
        self.assertEqual(supervisor.read(self.output/'supervisor_status.json')['status'],'complete')

    def test_pause_during_retry_does_not_restart(self):
        error=self.output/'stderr.log';error.write_text('')
        process=SimpleNamespace(pid=10,returncode=1,poll=lambda:1)
        def pause(_):supervisor.save(self.output/'training_control.json',{'desired_state':'paused'})
        with patch.object(supervisor,'launch_training',return_value=(process,error)) as launch,patch.object(supervisor.time,'sleep',side_effect=pause):
            supervisor.supervise(self.output,6)
        launch.assert_called_once()
        self.assertEqual(supervisor.read(self.output/'runner_status.json')['status'],'paused_by_user')

    def test_uncertain_post_and_authentication_do_not_restart(self):
        request=self.output/'q7_noisy/cloud/g060/s0/request.json'
        supervisor.save(request,{}) if request.parent.exists() else None
        request.parent.mkdir(parents=True,exist_ok=True);supervisor.save(request,{})
        self.assertFalse(supervisor.retry_decision(self.output,'')[0])
        supervisor.save(request.parent/'submission.json',{'id':'saved-job'})
        self.assertFalse(supervisor.retry_decision(self.output,'HTTP 401')[0])
        self.assertTrue(supervisor.retry_decision(self.output,'still pending; resume reuses its job ID')[0])

    def test_restart_backoff_is_capped(self):
        self.assertEqual([supervisor.retry_delay(i) for i in range(1,7)],[60,120,240,300,300,300])


if __name__=='__main__':unittest.main()
