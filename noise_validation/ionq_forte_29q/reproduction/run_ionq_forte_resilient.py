"""Run/resume the Forte study, waiting through temporary cloud GET failures.

Circuit submissions, seeds and saved responses are unchanged. Ambiguous POST
failures and authentication/validation errors still stop for inspection.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import time

from aeqga_ionq_cloud import IonQCloud,write_json
from run_ionq_forte_precision_study import main as precision_main

_original_request=IonQCloud.request
_log_lock=threading.Lock()


def retry_log(event):
    event={'timestamp_utc':datetime.now(timezone.utc).isoformat(),**event}
    print('Cloud read recovery:',json.dumps(event),flush=True)
    filename=os.environ.get('IONQ_RETRY_LOG')
    if filename:
        with _log_lock:
            with Path(filename).open('a',encoding='utf-8') as file:
                file.write(json.dumps(event)+'\n')


def resilient_request(self,method,path,**kwargs):
    failures=0
    while True:
        try:
            result=_original_request(self,method,path,**kwargs)
            if failures:retry_log({'event':'read_recovered','path':path,'failed_cycles':failures})
            return result
        except RuntimeError as error:
            transient=str(error) in ('IonQ GET repeatedly failed.','IonQ request retry limit exceeded.')
            if method!='GET' or not transient:raise
            failures+=1
            delay=min(60*failures,300)
            retry_log({'event':'waiting_for_read_connection','path':path,
                       'failed_cycles':failures,'next_retry_seconds':delay})
            time.sleep(delay)


IonQCloud.request=resilient_request


def main():
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'output'/'ionq_forte_29q')
    args,_=parser.parse_known_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    os.environ['IONQ_RETRY_LOG']=str(output/'transport_retries.jsonl')
    previous=output/'runner_status.json'
    if previous.exists() and json.loads(previous.read_text()).get('status')=='needs_attention':
        write_json(output/'previous_interruption.json',json.loads(previous.read_text()))
    source=Path(__file__).resolve()
    write_json(output/'transport_extension.json',{'source':source.name,
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'policy':'Repeat temporary GET failures after 60--300 seconds; do not retry ambiguous POST or authentication failures.',
        'simulation_and_sampling_unchanged':True})
    precision_main()


if __name__=='__main__':main()
