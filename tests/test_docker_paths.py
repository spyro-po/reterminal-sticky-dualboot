"""Static SDK installation, directory and Python-environment regressions."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import audit_builder
from common import ROOT


class DockerPathsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ['Dockerfile','.dockerignore','manifests/builder.lock.json','docker/apt.sources','docker/entrypoint.sh']:
            target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,target)
        self.patch=mock.patch.object(audit_builder,'ROOT',self.root);self.patch.start()
        self.dockerfile=self.root/'Dockerfile';self.original=self.dockerfile.read_text()

    def tearDown(self):self.patch.stop();self.tmp.cleanup()

    def test_current_build_and_runtime_layout(self):
        self.assertEqual(audit_builder.configuration()['status'],'PASS')

    def test_create_tools_root_before_install_and_constraints_copy(self):
        self.dockerfile.write_text(self.original.replace('mkdir -p "$IDF_TOOLS_PATH"','true'))
        with self.assertRaisesRegex(ValueError,'create directories'):audit_builder.configuration()

    def test_version_qualified_idf54_selector_cannot_return_silent_success(self):
        broken=self.original.replace('install --targets esp32s3 xtensa-esp-elf','install --targets esp32s3 xtensa-esp-elf@esp-14.2.0_20241119')
        self.dockerfile.write_text(broken)
        with self.assertRaisesRegex(ValueError,'version-qualified'):audit_builder.configuration()

    def test_sdk_python_and_tool_paths_must_agree(self):
        for old,new in [('IDF_TOOLS_PATH=/opt/esp/tools','IDF_TOOLS_PATH=/opt/elsewhere'),
                        ('IDF_PYTHON_ENV_PATH=/opt/esp/idf-python','IDF_PYTHON_ENV_PATH=/opt/sticky/python')]:
            self.dockerfile.write_text(self.original.replace(old,new))
            with self.assertRaisesRegex(ValueError,'environment paths'):audit_builder.configuration()

    def test_constraints_need_explicit_filename_before_dependency_check(self):
        source='cp /opt/sticky/locks/espidf.constraints.v5.4.txt "$IDF_TOOLS_PATH/espidf.constraints.v5.4.txt"'
        check='"$IDF54_PYTHON" "$IDF_PATH/tools/idf_tools.py" check-python-dependencies'
        for broken in [self.original.replace(source,source.replace('/espidf.constraints.v5.4.txt"','/"')),
                       self.original.replace(source,'TEMP_COPY').replace(check,source).replace('TEMP_COPY',check)]:
            self.dockerfile.write_text(broken)
            with self.assertRaisesRegex(ValueError,'check Python in order'):audit_builder.configuration()

    def test_compiler_presence_and_runtime_prerequisites_checked(self):
        compiler='test -x "$IDF_TOOLS_PATH/tools/xtensa-esp-elf/esp-14.2.0_20241119/xtensa-esp-elf/bin/xtensa-esp-elf-gcc"'
        self.dockerfile.write_text(self.original.replace(compiler,'true'))
        with self.assertRaisesRegex(ValueError,'verify the compiler'):audit_builder.configuration()
        self.dockerfile.write_text(self.original)
        entry=self.root/'docker/entrypoint.sh'
        entry.write_text(entry.read_text().replace('test -r /opt/sticky/locks/espidf.constraints.v5.4.txt','true'))
        with self.assertRaisesRegex(ValueError,'guard missing'):audit_builder.configuration()

    def test_sdk_install_cannot_run_before_python_environment_creation(self):
        venv=self.original.index('RUN python -m venv /opt/sticky/python')
        sdk=self.original.index('RUN git clone')
        end=self.original.index('# No CrossPoint compile')
        self.dockerfile.write_text(self.original[:venv]+self.original[sdk:end]+self.original[venv:sdk]+self.original[end:])
        with self.assertRaisesRegex(ValueError,'before invoking'):audit_builder.configuration()

    def test_locks_and_privilege_drop_follow_install_order(self):
        locks='COPY docker/requirements-pio.lock docker/requirements-idf.lock docker/espidf.constraints.v5.4.txt /opt/sticky/locks/'
        self.dockerfile.write_text(self.original.replace(locks,'# missing locks'))
        with self.assertRaisesRegex(ValueError,'Copy Python locks'):audit_builder.configuration()
        broken=self.original.replace('USER 1000:1000','').replace('RUN git clone','USER 1000:1000\nRUN git clone',1)
        self.dockerfile.write_text(broken)
        with self.assertRaisesRegex(ValueError,'before dropping privileges'):audit_builder.configuration()

    def test_runtime_copy_destinations_are_created_first(self):
        path=self.root/'docker/entrypoint.sh';original=path.read_text()
        for old,reason in [('mkdir -p "$HOME" /tmp/sticky-project','writable runtime workspace'),
                           ('mkdir -p /tmp/sticky-project/.cache/platformio','helper environment parent')]:
            path.write_text(original.replace(old,'true'))
            with self.assertRaisesRegex(ValueError,reason):audit_builder.configuration()

    def test_dependency_constraints_cannot_be_disabled(self):
        self.dockerfile.write_text(self.original.replace('COPY docker/requirements-pio.lock','ENV IDF_PYTHON_CHECK_CONSTRAINTS=no\nCOPY docker/requirements-pio.lock',1))
        with self.assertRaisesRegex(ValueError,'constraints must remain enabled'):audit_builder.configuration()

    def test_runtime_metadata_directory_must_exist_before_symlink(self):
        entry=self.root/'docker/entrypoint.sh'
        entry.write_text(entry.read_text().replace('mkdir -p "$HOME/.espressif"','true'))
        with self.assertRaisesRegex(ValueError,'metadata directory'):audit_builder.configuration()


if __name__=='__main__':unittest.main()
