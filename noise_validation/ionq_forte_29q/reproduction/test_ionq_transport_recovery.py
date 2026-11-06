import unittest
from unittest.mock import patch
import run_ionq_forte_resilient as recovery


class RecoveryTests(unittest.TestCase):
    def test_temporary_get_failure_recovers_same_job(self):
        job={'id':'saved-job','status':'completed'}
        with patch.object(recovery,'_original_request',side_effect=[RuntimeError('IonQ GET repeatedly failed.'),job]) as request,patch.object(recovery.time,'sleep') as sleep,patch.object(recovery,'retry_log'):
            result=recovery.resilient_request(object(),'GET','/jobs/saved-job')
        self.assertEqual(result,job)
        self.assertEqual(request.call_count,2)
        self.assertEqual(request.call_args_list[0],request.call_args_list[1])
        sleep.assert_called_once_with(60)

    def test_post_and_authentication_errors_do_not_retry(self):
        for method,error in [('POST','IonQ request retry limit exceeded.'),('GET','IonQ GET /jobs/saved-job: HTTP 401')]:
            with patch.object(recovery,'_original_request',side_effect=RuntimeError(error)) as request,patch.object(recovery.time,'sleep') as sleep:
                with self.assertRaises(RuntimeError):recovery.resilient_request(object(),method,'/jobs/saved-job')
                request.assert_called_once();sleep.assert_not_called()


if __name__=='__main__':unittest.main()
