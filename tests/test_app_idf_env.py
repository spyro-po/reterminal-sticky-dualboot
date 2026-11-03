"""Application-IDF bootstrap/import regressions, without downloads or SDK builds."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import app_idf_env as app
from common import ROOT,sha


class AppIdfTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.core=self.root/'core';self.env={'PLATFORMIO_CORE_DIR':str(self.core),
            'UV_CONSTRAINT':'outer-pio-lock','UV_BUILD_CONSTRAINT':'outer-pio-build-lock','UV_OVERRIDE':'untrusted-override'}
        self.directory=self.core/'penv/.espidf-5.5.5';self.python=self.directory/'bin/python'
        self.builder=json.loads((ROOT/'manifests/builder.lock.json').read_text())
        for name in ['docker/requirements-app-idf.lock','manifests/builder.lock.json']:
            target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())
        self.source=self.core/'platforms/espressif32/builder/frameworks/espidf.py'
        self.requirements=self.core/'packages/framework-espidf/tools/requirements/requirements.core.txt'
        for path in [self.source,self.requirements]:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
        for key in ['upstream_builder_sha256','core_requirements_sha256']:
            self.builder['app_idf_environment'][key]=sha(b'fixture')
        (self.root/'manifests/builder.lock.json').write_text(json.dumps(self.builder))
        self.patch=mock.patch.object(app,'ROOT',self.root);self.patch.start()
        self.calls=[]

    def tearDown(self):self.patch.stop();self.tmp.cleanup()

    def runner(self,command,cwd,log,env):
        self.calls.append((command,log,env))
        if 'venv' in command:
            self.python.parent.mkdir(parents=True);self.python.write_text('fixture interpreter')

    def initialize(self,runner=None):
        with contextlib.redirect_stdout(io.StringIO()),mock.patch.object(app.subprocess,'check_output',return_value='3.12.16-final.0\n'):
            app.initialize_app_idf(self.root,'first',self.env,runner or self.runner)

    def test_empty_cache_uses_explicit_application_interpreter_and_hashed_lock(self):
        before=dict(self.env);self.initialize()
        self.assertEqual(self.calls[0][0],[self.core/'penv/bin/uv','venv','--clear','--python',self.core/'penv/bin/python',self.directory])
        install=self.calls[2][0]
        self.assertIn('--require-hashes',install)
        self.assertEqual(install[install.index('--python')+1],self.python)
        probe=self.calls[-1][0]
        self.assertEqual(probe[:3],[self.python,'-I','-c'])
        self.assertIn('import idf_component_manager',probe[3])
        self.assertEqual(probe[-2:], [self.directory,self.root/'docker/requirements-app-idf.lock'])
        for _,_,env in self.calls:
            self.assertEqual(env['UV_CONSTRAINT'],str(self.root/'docker/requirements-app-idf.lock'))
            self.assertNotIn('UV_OVERRIDE',env)
        self.assertEqual(self.env,before)
        marker=json.loads((self.directory/'pio-idf-venv.json').read_text())
        self.assertEqual(marker['deps_hash'],sha(json.dumps(self.builder['app_idf_environment']['dependencies'],sort_keys=True).encode()))

    def test_existing_cache_is_synced_checked_and_probed_again(self):
        self.python.parent.mkdir(parents=True);self.python.write_text('existing interpreter')
        self.initialize()
        self.assertEqual(len(self.calls),4)
        self.assertNotIn('venv',self.calls[0][0])
        self.assertEqual(self.python.read_text(),'existing interpreter')

    def test_failed_import_does_not_create_success_marker(self):
        def runner(command,cwd,log,env):
            self.runner(command,cwd,log,env)
            if log.endswith('-probe.log'):raise ValueError('No module named idf_component_manager')
        with self.assertRaisesRegex(ValueError,'idf_component_manager'):self.initialize(runner)
        self.assertFalse((self.directory/'pio-idf-venv.json').exists())

    def test_install_failure_stops_before_probe_and_marker(self):
        def runner(command,cwd,log,env):
            self.runner(command,cwd,log,env)
            if 'sync' in command:raise ValueError('hash mismatch')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.initialize(runner)
        self.assertEqual(len(self.calls),3)
        self.assertFalse((self.directory/'pio-idf-venv.json').exists())

    def test_tampered_lock_or_upstream_script_stops_before_install(self):
        lock=self.root/'docker/requirements-app-idf.lock';original=lock.read_bytes()
        lock.write_text('untrusted')
        with self.assertRaisesRegex(ValueError,'lock integrity'):self.initialize()
        lock.write_bytes(original);self.source.write_text('changed upstream')
        with self.assertRaisesRegex(ValueError,'contract changed'):self.initialize()
        self.assertFalse(self.calls)

    def test_skip_marker_and_symlink_environment_are_rejected(self):
        skip=self.requirements.parents[2]/'.pio_skip_pypackages';skip.touch()
        with self.assertRaisesRegex(ValueError,'must not be skipped'):self.initialize()
        skip.unlink();other=self.root/'bootloader-python';other.mkdir()
        self.directory.parent.mkdir(parents=True);self.directory.symlink_to(other,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):self.initialize()
        self.assertFalse(self.calls)

    def test_probe_rejects_wrong_interpreter_in_real_subprocess(self):
        result=subprocess.run([sys.executable,'-I','-c',app.PROBE,str(self.directory),
                               str(self.root/'docker/requirements-app-idf.lock')],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Wrong application interpreter',result.stderr)

    def test_correct_but_empty_interpreter_rejects_missing_component_manager(self):
        subprocess.run([sys.executable,'-m','venv','--without-pip',str(self.directory)],check=True)
        lock=self.root/'empty.lock';lock.write_text('')
        result=subprocess.run([self.python,'-I','-c',app.PROBE,str(self.directory),str(lock)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("No module named 'idf_component_manager'",result.stderr)

    def test_lock_covers_sdk_core_and_all_pio_required_packages(self):
        import re
        packages=dict(re.findall(r'^([A-Za-z0-9_.-]+)==([A-Za-z0-9.+!-]+)',
                               (self.root/'docker/requirements-app-idf.lock').read_text(),re.M))
        self.assertEqual(len(packages),59)
        self.assertEqual(packages['idf-component-manager'],'2.4.11')
        self.assertEqual(packages['esp-idf-kconfig'],'3.7.0')
        self.assertEqual(packages['cryptography'],'44.0.3')
        self.assertEqual(packages['pyparsing'],'3.2.5')
        self.assertTrue({'esp-idf-diag','tree-sitter','tree-sitter-c','esp-idf-monitor','esptool'}<=packages.keys())


if __name__=='__main__':unittest.main()
