"""Real subprocess regression tests; no SDK, downloads, Docker or firmware."""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from process_log import new_session,run_logged
import installer


class ProcessLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.directory=new_session(self.root/'diagnostics')

    def tearDown(self):self.tmp.cleanup()

    def run_code(self,code,name='clean.log'):
        run_logged([sys.executable,'-c',code],self.root,name,dict(os.environ),self.directory)

    def status(self):
        return json.loads((self.directory/'clean.status.json').read_text())

    def test_success_uses_exit_status_even_if_output_says_error(self):
        self.run_code("print('error failed exception are harmless output in this fixture')")
        record=self.status()
        self.assertEqual(record['returncode'],0)
        self.assertEqual(record['outcome'],'success')
        self.assertGreater(record['pid'],0)
        self.assertIsNotNone(record['finished_at'])
        self.assertEqual(record['cwd'],str(self.root))
        self.assertNotIn('env',record)

    def test_success_text_with_nonzero_exit_is_rejected_and_tail_reported(self):
        with self.assertRaisesRegex(ValueError,r'returncode=7') as failure:
            self.run_code("import sys; print('SUCCESS',flush=True); print('last stderr',file=sys.stderr); sys.exit(7)")
        self.assertIn('SUCCESS',str(failure.exception))
        self.assertIn('last stderr',str(failure.exception))
        self.assertIn(str(self.directory),str(failure.exception))
        self.assertEqual(self.status()['returncode'],7)

    @unittest.skipUnless(os.name=='posix','POSIX signal exit codes')
    def test_signal_is_not_misreported_as_success(self):
        with self.assertRaisesRegex(ValueError,r'returncode=-15 \(signal 15\)'):
            self.run_code("import os,signal; print('SUCCESS',flush=True); os.kill(os.getpid(),signal.SIGTERM)")
        self.assertEqual(self.status()['returncode'],-signal.SIGTERM)

    def test_runs_never_reuse_old_host_log(self):
        old=self.root/'clean.log';old.write_text('old SUCCESS')
        other=new_session(self.root/'diagnostics')
        self.assertNotEqual(other,self.directory)
        self.run_code("print('new process')")
        self.assertEqual(old.read_text(),'old SUCCESS')
        self.assertIn('new process',(self.directory/'clean.log').read_text())
        with self.assertRaises(FileExistsError):self.run_code("print('overwrite')")
        self.assertNotIn('overwrite',(self.directory/'clean.log').read_text())

    def test_stdout_stderr_are_both_preserved_and_tail_is_bounded(self):
        with self.assertRaises(ValueError) as failure:
            self.run_code("import sys; print('x'*20000); print('stdout end',flush=True); print('stderr end',file=sys.stderr); sys.exit(1)")
        self.assertLess(len(str(failure.exception)),9500)
        self.assertIn('stdout end',str(failure.exception))
        self.assertIn('stderr end',str(failure.exception))
        self.assertGreater((self.directory/'clean.log').stat().st_size,20000)

    def test_spawn_failure_has_status_without_fake_exit_code(self):
        with self.assertRaisesRegex(ValueError,'Could not start command'):
            run_logged([self.root/'missing-program'],self.root,'clean.log',dict(os.environ),self.directory)
        self.assertEqual(self.status()['outcome'],'spawn_error')
        self.assertIsNone(self.status()['returncode'])
        self.assertIn('error',self.status())

    def test_driver_tail_retains_inner_failure_status(self):
        code=("import os,sys; from process_log import run_logged; "
              "run_logged([sys.executable,'-c',\"[print('SUCCESS') for _ in range(60)]; raise SystemExit(7)\"],"
              f"{str(self.root)!r},'inner.log',dict(os.environ),{str(self.directory)!r})")
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'scripts'))
        with self.assertRaises(ValueError) as failure:
            run_logged([sys.executable,'-c',code],self.root,'clean.log',env,self.directory)
        self.assertIn('returncode=7',str(failure.exception))
        self.assertIn('inner.status.json',str(failure.exception))
        self.assertIn('returncode=1',str(failure.exception))
        self.assertEqual(self.status()['returncode'],1)

    def test_unwritable_log_fails_before_process_starts(self):
        with mock.patch.object(Path,'open',side_effect=PermissionError('read-only output')):
            with mock.patch('process_log.subprocess.Popen') as start:
                with self.assertRaises(PermissionError):self.run_code("print('never runs')")
                start.assert_not_called()

    def test_unsafe_log_name_rejected(self):
        with self.assertRaises(ValueError):self.run_code('pass','../escape.log')

    def test_installer_failure_retains_diagnostics_outside_bundle(self):
        output=self.root/'output'
        args=installer.parser().parse_args(['build','--output-root',str(output)])
        def failed_build(command,cwd,name,env,directory):
            self.assertEqual(env['STICKY_BUILD_LOG_DIR'],str(directory))
            run_logged([sys.executable,'-c',"print('SUCCESS',flush=True); raise SystemExit(9)"],
                       cwd,name,env,directory)
        with mock.patch.object(installer,'ROOT',self.root), \
             mock.patch.object(installer,'fetch',return_value=mock.Mock(read_bytes=lambda:b'fixture')), \
             mock.patch.object(installer,'official',return_value=b'fixture'), \
             mock.patch.object(installer,'run_logged',side_effect=failed_build), \
             mock.patch.object(installer,'export') as export,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'returncode=9'):installer.build_bundle(args)
        export.assert_not_called()
        self.assertFalse((output/'cp-2.0.0-seeedash-1.2.0').exists())
        logs=list((output/'diagnostics').glob('*/installer-first-driver.status.json'))
        self.assertEqual(len(logs),1)
        self.assertEqual(json.loads(logs[0].read_text())['returncode'],9)
