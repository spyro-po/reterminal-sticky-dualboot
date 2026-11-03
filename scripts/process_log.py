"""Local-only, run-scoped subprocess diagnostics. Never infer status from output."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def now():
    return datetime.now(timezone.utc).isoformat()


def new_session(root):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    return Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=root)).resolve()


def run_logged(command,cwd,name,env,directory):
    """Keep raw merged output and status even when the container is removed.

    Exclusive filenames prevent retries from overwriting evidence. No environment
    values are dumped. Commands must not contain credentials (build tools only).
    """
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]*\.log',name):
        raise ValueError('Invalid diagnostic log name')
    directory=Path(directory).resolve()
    path=directory/name
    status=path.with_suffix('.status.json')
    argv=[str(arg) for arg in command]
    record={'command':argv,'cwd':str(Path(cwd).resolve()),'run_id':directory.name,
            'started_at':now(),'finished_at':None,'pid':None,'returncode':None,
            'outcome':'starting','log':str(path)}
    # Reserve both files before starting a process; never reuse an earlier log.
    with status.open('x',encoding='utf-8') as metadata, path.open('x+b') as stream:
        def save():
            metadata.seek(0);json.dump(record,metadata,indent=2);metadata.write('\n')
            metadata.truncate();metadata.flush()
        save()
        try:
            process=subprocess.Popen(argv,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT)
        except OSError as error:
            record.update(finished_at=now(),outcome='spawn_error',error=str(error))
            save()
            raise ValueError(f'Could not start command: {error}; status: {status}') from error
        record.update(pid=process.pid,outcome='running');save()
        try:
            code=process.wait()
        except KeyboardInterrupt:
            process.terminate();code=process.wait()
            record.update(returncode=code,finished_at=now(),outcome='interrupted');save()
            raise
        record.update(returncode=code,finished_at=now(),outcome='success' if code==0 else 'failed')
        save()
        if code!=0:
            stream.seek(0,os.SEEK_END)
            stream.seek(max(0,stream.tell()-8192))
            tail='\n'.join(stream.read().decode('utf-8',errors='replace').splitlines()[-40:])
            reason=f'returncode={code}'+(f' (signal {-code})' if code<0 else '')
            # Put the status last so an enclosing driver's bounded tail retains
            # the failing inner tool's code and paths, not only its final output.
            raise ValueError('Final process output (up to 40 lines / 8 KiB):\n'+tail+
                             f'\nCommand failed: {reason}; log: {path}; status: {status}')
