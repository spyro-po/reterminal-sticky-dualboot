"""Offline regressions for first-clean package initialization; no firmware build."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import ROOT,LOCK
from pio_dependencies import framework_sources,initialize_project,validate_frameworks


class PioDependenciesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.core=Path(self.tmp.name)/'core'
        self.checkout=Path(self.tmp.name)/'checkout';self.checkout.mkdir()
        self.env={'PLATFORMIO_CORE_DIR':str(self.core),'STICKY_BUILD_LOG_DIR':str(self.core/'logs')}
        self.platform=self.core/'platforms/espressif32/platform.json'
        self.platform.parent.mkdir(parents=True)
        self.platform.write_text(json.dumps({'version':LOCK['platformio']['platform_version'],
            'packages':{name:{'version':url} for name,url in framework_sources().items()}}))
        self.command=['pinned-python','-m','platformio']

    def tearDown(self):self.tmp.cleanup()

    def install(self):
        versions=['3.3.11','5.5.5+sha.b774170ff46','3.50505']
        for (name,url),version in zip(framework_sources().items(),versions):
            directory=self.core/'packages'/name;directory.mkdir(parents=True,exist_ok=True)
            (directory/'package.json').write_text(json.dumps({'name':name,'version':version}))
            (directory/'.piopm').write_text(json.dumps({'name':name,'spec':{'uri':url},
                'version':version+'.0' if name=='framework-espidf' else version}))
        libs=self.core/'packages/framework-arduinoespressif32-libs/esp32s3'
        libs.mkdir(exist_ok=True);(libs/'sdkconfig').write_text('fixture')

    def initialize(self,runner):
        initialize_project(self.command,self.checkout,'first',self.env,runner)

    def test_empty_cache_installs_selected_pinned_environment_before_validation(self):
        self.assertFalse((self.core/'packages').exists())
        calls=[]
        def runner(command,cwd,log,env):
            calls.append((command,cwd,log,env));self.install()
        self.initialize(runner)
        self.assertEqual(calls,[(self.command+['pkg','install','--environment','sticky-dualboot-test','--no-save'],
                                self.checkout,'first-dependencies.log',self.env)])
        validate_frameworks(self.core)

    def test_existing_cache_still_resolves_environment_and_keeps_files(self):
        self.install()
        before={p.relative_to(self.core):p.read_bytes() for p in self.core.rglob('*') if p.is_file()}
        runner=mock.Mock();self.initialize(runner);runner.assert_called_once()
        self.assertEqual(before,{p.relative_to(self.core):p.read_bytes() for p in self.core.rglob('*') if p.is_file()})

    def test_successful_install_without_frameworks_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'metadata missing'):self.initialize(mock.Mock())

    def test_package_install_failure_is_not_ignored(self):
        with self.assertRaisesRegex(ValueError,'returncode=7'):
            self.initialize(mock.Mock(side_effect=ValueError('returncode=7')))

    def test_changed_platform_source_rejected_before_install(self):
        data=json.loads(self.platform.read_text())
        data['packages']['framework-arduinoespressif32-libs']['version']='https://example.invalid/latest.tar.xz'
        self.platform.write_text(json.dumps(data));runner=mock.Mock()
        with self.assertRaisesRegex(ValueError,'approved versions'):self.initialize(runner)
        runner.assert_not_called()

    def test_wrong_cached_package_source_or_metadata_rejected(self):
        self.install();path=self.core/'packages/framework-arduinoespressif32-libs/.piopm'
        data=json.loads(path.read_text());data['spec']['uri']='https://example.invalid/latest.tar.xz'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'source/metadata mismatch'):self.initialize(mock.Mock())

    def test_partial_framework_without_s3_sdkconfig_rejected(self):
        self.install();(self.core/'packages/framework-arduinoespressif32-libs/esp32s3/sdkconfig').unlink()
        with self.assertRaisesRegex(ValueError,'SDK configuration missing'):self.initialize(mock.Mock())

    def test_existing_rebuilt_cache_accepts_original_sdkconfig(self):
        self.install();path=self.core/'packages/framework-arduinoespressif32-libs/esp32s3/sdkconfig'
        path.rename(path.with_suffix('.orig'))
        self.initialize(mock.Mock())

    def builder(self):
        # Test orchestration without pyelftools in stdlib-only CI. Stop before
        # linking/auditing firmware; none of that module's code is exercised.
        spec=importlib.util.spec_from_file_location('build_under_test',ROOT/'scripts/build.py')
        module=importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules,{'elf_audit':mock.Mock()}):spec.loader.exec_module(module)
        return module

    def test_build_orchestration_installs_before_first_clean_on_cold_and_warm_cache(self):
        class StopBeforeCompile(Exception):pass
        for warm in [False,True]:
            with self.subTest(warm=warm):
                if warm:self.install()
                module=self.builder();calls=[]
                def runner(command,cwd,log,env):
                    calls.append(log)
                    if 'pkg' in command:self.install()
                    else:
                        validate_frameworks(self.core)
                        if 'clean' not in command:raise StopBeforeCompile()
                with mock.patch.object(module,'environment',return_value=self.env), \
                     mock.patch.object(module,'prepare',return_value=self.checkout), \
                     mock.patch.object(module,'pio_command',return_value=self.command), \
                     mock.patch.object(module,'prepare_platform'),mock.patch.object(module,'run',side_effect=runner):
                    with self.assertRaises(StopBeforeCompile):module.build(mock.Mock(label='first',clean_app=True))
                self.assertEqual(calls,['first-dependencies.log','first-clean.log','first-crosspoint.log'])

    def test_build_does_not_reach_clean_when_initialization_is_incomplete(self):
        module=self.builder();runner=mock.Mock()
        with mock.patch.object(module,'environment',return_value=self.env), \
             mock.patch.object(module,'prepare',return_value=self.checkout), \
             mock.patch.object(module,'pio_command',return_value=self.command), \
             mock.patch.object(module,'prepare_platform'),mock.patch.object(module,'run',runner):
            with self.assertRaisesRegex(ValueError,'metadata missing'):module.build(mock.Mock(label='first',clean_app=True))
        self.assertEqual(runner.call_count,1)
        self.assertIn('pkg',runner.call_args.args[0])
