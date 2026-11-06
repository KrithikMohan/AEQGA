"""Resume the saved Forte study and retry recoverable worker/process failures.

Credentials are inherited through IONQ_API_KEY and never written to disk.
Set training_control.json desired_state to paused to stop automatic recovery.
This supervisor runs while Windows is running; it does not register a startup task.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent


def utc():return datetime.now(timezone.utc).isoformat()


def save(path,data):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8');temp.replace(path)


def read(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def paused(output):
    return (read(output/'training_control.json').get('desired_state')!='running'
            or read(output/'runner_status.json').get('status')=='paused_by_user')


def retry_delay(attempt):return min(60*2**min(max(attempt-1,0),3),300)


def retry_decision(output,error_text):
    """Never blindly repeat a submission whose acceptance is unknown."""
    missing=[p for p in output.glob('q*_noisy/cloud/*/*/request.json')
             if not (p.parent/'submission.json').exists()]
    if missing:return False,'Cloud submission without a saved job ID; reconcile it before resuming.'
    fatal=('HTTP 400','HTTP 401','HTTP 402','HTTP 403','HTTP 404','HTTP 422',
           'AssertionError','ValueError','PermissionError','ModuleNotFoundError',
           'Cached cloud request differs','Cached result hash mismatch','configuration differs',
           'Submission connection interrupted')
    if any(token in error_text for token in fatal):
        return False,'Authentication, validation or submission error requires inspection.'
    failures=read(output/'runner_status.json').get('failures',[])
    for failure in failures:
        message=failure.get('error','')
        if not any(t in message for t in ('GET repeatedly failed','retry limit exceeded','still pending; resume reuses its job ID')):
            return False,'Non-transient training failure requires inspection: '+message[:300]
    return True,'Retrying the same study using saved requests, job IDs and histograms.'


def hidden_options():
    if os.name!='nt':return {}
    info=subprocess.STARTUPINFO();info.dwFlags|=subprocess.STARTF_USESHOWWINDOW;info.wShowWindow=0
    return {'startupinfo':info,'creationflags':subprocess.CREATE_NO_WINDOW}


def launch_training(output,workers,attempt):
    logs=output/'supervisor_logs';logs.mkdir(exist_ok=True)
    stem=f'attempt_{attempt:03d}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}'
    out=logs/(stem+'.stdout.log');err=logs/(stem+'.stderr.log')
    command=[sys.executable,'-u',str(ROOT/'run_ionq_forte_resilient.py'),
             '--output',str(output),'--workers',str(workers),'--analyze']
    with out.open('wb') as stdout,err.open('wb') as stderr:
        process=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,
                                 stdout=stdout,stderr=stderr,**hidden_options())
    return process,err


def event(output,**data):
    entry={'timestamp_utc':utc(),**data}
    with (output/'supervisor_events.jsonl').open('a',encoding='utf-8') as file:
        file.write(json.dumps(entry)+'\n')
    save(output/'supervisor_status.json',entry)
    print(json.dumps(entry),flush=True)


def stop_tree(process):
    if process.poll() is not None:return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**hidden_options())
    else:process.terminate()


def mark_paused(output,attempt):
    save(output/'runner_status.json',{'status':'paused_by_user','paused_utc':utc()})
    event(output,status='paused_by_user',attempt=attempt)


def supervise(output,workers,poll_seconds=10):
    attempt=0
    while not paused(output):
        attempt+=1
        save(output/'runner_status.json',{'status':'starting','attempt':attempt,'started_utc':utc()})
        process,stderr=launch_training(output,workers,attempt)
        event(output,status='running',attempt=attempt,supervisor_pid=os.getpid(),training_pid=process.pid)
        last_heartbeat=0.
        while process.poll() is None:
            if paused(output):
                stop_tree(process);mark_paused(output,attempt);return
            if time.monotonic()-last_heartbeat>=60:
                save(output/'supervisor_status.json',{'status':'running','attempt':attempt,
                    'supervisor_pid':os.getpid(),'training_pid':process.pid,'heartbeat_utc':utc()})
                last_heartbeat=time.monotonic()
            time.sleep(poll_seconds)
        if paused(output):mark_paused(output,attempt);return
        state=read(output/'runner_status.json')
        if process.returncode==0 and state.get('status')=='complete':
            event(output,status='complete',attempt=attempt);return
        errors=stderr.read_text(encoding='utf-8',errors='replace') if stderr.exists() else ''
        retry,reason=retry_decision(output,errors)
        if not retry:
            event(output,status='needs_attention',attempt=attempt,reason=reason,exit_code=process.returncode)
            save(output/'runner_status.json',{'status':'needs_attention','reason':reason});return
        delay=retry_delay(attempt)
        event(output,status='retry_wait',attempt=attempt,next_retry_seconds=delay,reason=reason,exit_code=process.returncode)
        for _ in range(delay):
            if paused(output):mark_paused(output,attempt);return
            time.sleep(1)


@contextmanager
def study_lock(output):
    import msvcrt
    with (output/'supervisor.lock').open('a+b') as file:
        if file.tell()==0:file.write(b'0');file.flush()
        file.seek(0)
        try:msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise RuntimeError('A supervisor already owns this study.') from None
        try:yield
        finally:file.seek(0);msvcrt.locking(file.fileno(),msvcrt.LK_UNLCK,1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'output'/'ionq_forte_29q')
    parser.add_argument('--workers',type=int,default=6)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    if not os.environ.get('IONQ_API_KEY'):raise RuntimeError('Set IONQ_API_KEY before resuming.')
    with study_lock(output):
        save(output/'supervisor_resume_receipt.json',{'requested_utc':utc(),'previous_state':read(output/'runner_status.json'),
             'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        save(output/'training_control.json',{'desired_state':'running','requested_utc':utc()})
        save(output/'runner_status.json',{'status':'starting','started_utc':utc()})
        helpers=[]
        try:
            with (output/'supervisor_helpers.log').open('ab') as log:
                for name,arguments in [('keep_ionq_training_awake.py',[str(os.getpid())]),('monitor_ionq_forte_study.py',['--output',str(output)])]:
                    helpers.append(subprocess.Popen([sys.executable,'-u',str(ROOT/name),*arguments],cwd=ROOT,
                        stdin=subprocess.DEVNULL,stdout=log,stderr=log,**hidden_options()))
            supervise(output,args.workers)
        finally:
            for helper in helpers:
                if helper.poll() is None:helper.terminate()


if __name__=='__main__':main()
