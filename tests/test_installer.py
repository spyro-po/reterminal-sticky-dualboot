"""Offline CLI, compatibility, bundle corruption and Docker-boundary regressions."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import bundle
import compatibility
import installer
import check_updates
from common import ROOT,EXPECTED,FLASH_SIZE,partition_table,sha,image
from test_integrity import pair


class CompatibilityTests(unittest.TestCase):
    def test_docker_config_and_locks(self):
        from audit_builder import configuration
        self.assertEqual(configuration()['status'],'PASS')
        data=json.loads((ROOT/'manifests/builder.lock.json').read_text())
        for name,digest in data['files'].items():self.assertEqual(sha((ROOT/name).read_bytes()),digest)

    def test_single_stable_and_source_pins(self):
        entry=compatibility.select()
        self.assertEqual(entry['channel'],'stable')
        self.assertEqual(entry['crosspoint']['version'],'2.0.0')
        self.assertFalse(entry['hardware_validation']['docker_build_tested'])
        with mock.patch.object(compatibility,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'integrity mismatch'):compatibility.manifest()

    def altered(self,data):
        path=Path(self.tmp.name)/'compatibility.json'
        path.write_text(json.dumps(data))
        return mock.patch.object(compatibility,'MANIFEST',path)

    def setUp(self):self.tmp=tempfile.TemporaryDirectory()
    def tearDown(self):self.tmp.cleanup()

    def test_new_version_cannot_be_stable(self):
        for project in ['crosspoint','seeedash']:
            data=compatibility.manifest();data['combinations'][0][project]['version']='9.0.0'
            with self.altered(data):
                with self.assertRaisesRegex(ValueError,'cannot be stable'):compatibility.manifest()

    def test_experimental_cannot_be_selected_as_stable(self):
        data=compatibility.manifest();entry=copy.deepcopy(data['combinations'][0])
        entry.update(id='future-9.0.0',channel='experimental');data['combinations'].append(entry)
        with self.altered(data):
            with self.assertRaisesRegex(ValueError,'Experimental'):compatibility.select(entry['id'])
        with self.assertRaisesRegex(ValueError,'Unknown combination'):compatibility.select('latest')

    def test_current_and_older_versions_are_not_new_updates(self):
        fixtures={check_updates.CROSSPOINT:{'tag_name':'2.0.0'},check_updates.SEEED:[{'name':'1.1.0','type':'dir'},{'name':'1.2.0','type':'dir'}]}
        self.assertEqual(check_updates.check(fixtures.__getitem__)['candidates'],[])

    def test_upstream_is_read_only_metadata(self):
        original=compatibility.MANIFEST.read_bytes()
        fixtures={check_updates.CROSSPOINT:{'tag_name':'v9.0.0'},check_updates.SEEED:[{'name':'1.2.0','type':'dir'},{'name':'9.0.0','type':'dir'}]}
        report=check_updates.check(fixtures.__getitem__)
        self.assertEqual(len(report['candidates']),2)
        self.assertTrue(all(x['channel']=='experimental' and x['compatibility']=='NOT_VALIDATED' for x in report['candidates']))
        self.assertFalse(report['firmware_downloaded']);self.assertFalse(report['stable_manifest_modified'])
        self.assertEqual(compatibility.MANIFEST.read_bytes(),original)
        with self.assertRaises(ValueError):check_updates.save_report(Path(self.tmp.name),'../escape.json',report)
        check_updates.save_report(Path(self.tmp.name),'report.json',report)
        with self.assertRaises(ValueError):check_updates.save_report(Path(self.tmp.name),'report.json',report)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.boot,self.cp=pair();self.entry=copy.deepcopy(compatibility.select())
        fresh=bytearray(b'\xff'*FLASH_SIZE)
        for index,(name,_,_,offset,size) in enumerate(EXPECTED):
            if name in self.entry['factory_partition_sha256']:
                fresh[offset:offset+size]=bytes([index+1])*size
                self.entry['factory_partition_sha256'][name]=sha(fresh[offset:offset+size])
        fresh[:0x8000]=self.boot.ljust(0x8000,b'\xff')
        fresh[0x8000:0x9000]=partition_table().ljust(4096,b'\xff')
        fresh[0x690000:0xc90000]=self.cp.ljust(0x600000,b'\xff')
        self.image=bytes(fresh)
        self.report={'builder_version':'1.1.0','combination':self.entry['id'],
                     'compatibility_manifest_sha256':sha(compatibility.MANIFEST.read_bytes()),
                     'dependency_lock_sha256':sha((ROOT/'manifests/dependencies.lock.json').read_bytes()),
                     'builder_lock_sha256':sha((ROOT/'manifests/builder.lock.json').read_bytes()),
                     'hardware_tested_this_build':False}
        self.source=self.root/'pair';self.source.mkdir()
        bi,ci=image(self.boot,0x8000),image(self.cp,0x600000)
        meta={'version':'1.0.0','partition_table_sha256':sha(partition_table()),'segments':[
            dict(file='bootloader.bin',offset='0x0',**bi),dict(file='crosspoint.bin',offset='0x690000',**ci)]}
        for name,data in [('bootloader.bin',self.boot),('crosspoint.bin',self.cp),('segments.json',json.dumps(meta).encode())]:
            (self.source/name).write_bytes(data)
        self.destination=self.root/'bundle'
        self.selector=mock.patch.object(bundle,'select',return_value=self.entry);self.selector.start()
        with mock.patch.object(bundle,'fresh_image',return_value=self.image):
            bundle.export(self.destination,self.source,b'factory-local-only',self.entry,self.report)

    def tearDown(self):self.selector.stop();self.tmp.cleanup()

    def rewrite_sums(self):
        (self.destination/'SHA256SUMS.txt').write_text(''.join(sha(p.read_bytes())+'  '+p.name+'\n' for p in sorted(self.destination.iterdir()) if p.name!='SHA256SUMS.txt'))

    def test_export_and_no_overwrite(self):
        self.assertEqual(bundle.verify(self.destination)['status'],'PASS')
        self.assertEqual({p.name for p in self.destination.iterdir()},bundle.FILES)
        with self.assertRaisesRegex(ValueError,'already exists'):bundle.export(self.destination,self.source,b'',self.entry,self.report)

    def test_preserve_needs_explicit_ack_and_actual_backup(self):
        with self.assertRaisesRegex(ValueError,'confirm-layout'):bundle.verify(self.destination,mode='preserve')
        with self.assertRaisesRegex(ValueError,'complete private'):bundle.verify(self.destination,mode='preserve',confirm='protected-reference')
        path=self.root/'private-backup';path.write_bytes(b'incomplete')
        with self.assertRaisesRegex(ValueError,'33554432'):bundle.verify(self.destination,mode='preserve',backup=path,confirm='protected-reference')
        complete=b'\xff'*FLASH_SIZE;path.write_bytes(complete)
        with mock.patch.object(bundle,'backup_check') as check:
            result=bundle.verify(self.destination,mode='preserve',backup=path,confirm='protected-reference')
            check.assert_called_once_with(complete,self.boot,self.cp)
            self.assertTrue(result['preserve_data_preflight'])

    def test_malformed_reports_and_oversize_files(self):
        path=self.destination/'build-report.json';path.write_text('[]');self.rewrite_sums()
        with self.assertRaisesRegex(ValueError,'expected a JSON object'):bundle.verify(self.destination)
        path.write_bytes(b'x'*1048577)
        with self.assertRaisesRegex(ValueError,'size limit'):bundle.verify(self.destination)

    def test_checksum_and_extra_file_rejection(self):
        path=self.destination/'bootloader.bin';path.write_bytes(path.read_bytes()+b'bad')
        with self.assertRaisesRegex(ValueError,'Checksum mismatch'):bundle.verify(self.destination)
        path.write_bytes(self.boot)
        (self.destination/'private.txt').write_text('not an output artifact')
        with self.assertRaisesRegex(ValueError,'exactly the six'):bundle.verify(self.destination)

    def test_self_consistent_fresh_tampering_rejected(self):
        path=self.destination/'fresh-32MiB.bin'
        for offset,reason in [(0,'bootloader region'),(0x8000,'partition sector'),(0x89000,'private partitions'),(0x90000,'Factory bytes'),(0x690000,'CrossPoint region')]:
            data=bytearray(self.image);data[offset]^=1;path.write_bytes(data);self.rewrite_sums()
            with self.assertRaisesRegex(ValueError,reason):bundle.verify(self.destination)

    def test_hardware_claim_and_lock_tampering_rejected(self):
        path=self.destination/'build-report.json'
        for key,value in [('hardware_tested_this_build',True),('builder_lock_sha256','0'*64),('compatibility_manifest_sha256','0'*64)]:
            data=dict(self.report);data[key]=value;path.write_text(json.dumps(data));self.rewrite_sums()
            with self.assertRaises(ValueError):bundle.verify(self.destination)

    def test_paths_symlinks_and_checksum_traversal(self):
        for name in ['..','../escape','/tmp','a/b']:
            with self.assertRaises(ValueError):bundle.bundle_path(self.root,name)
        linked=self.root/'linked';linked.symlink_to(self.destination,target_is_directory=True)
        with self.assertRaises(ValueError):bundle.bundle_path(self.root,'linked')
        (self.destination/'SHA256SUMS.txt').write_text('0'*64+'  ../escape\n')
        with self.assertRaises(ValueError):bundle.verify(self.destination)

    def test_failed_export_is_not_visible(self):
        target=self.root/'must-not-exist'
        with mock.patch.object(bundle,'fresh_image',return_value=b'bad'):
            with self.assertRaises(ValueError):bundle.export(target,self.source,b'factory-local',self.entry,self.report)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob('.sticky-build-*')))

    def test_info_only_prints_commands(self):
        argv=['info','--output-root',str(self.root),'--directory','bundle','--mode','fresh']
        with mock.patch.object(installer.subprocess,'run') as run,contextlib.redirect_stdout(io.StringIO()) as output:
            installer.main(argv)
        run.assert_not_called();self.assertIn('MANUAL HOST',output.getvalue())
        self.assertIn('New outputs are not hardware tested',output.getvalue())


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.log=self.root/'docker-args';self.output=self.root/'out with spaces'
        fake=self.root/'docker'
        fake.write_text('#!/bin/sh\nprintf "%s\\n" "CALL" "$@" >> "$FAKE_DOCKER_LOG"\nif [ "$1" = info ] && [ "${FAKE_DOCKER_FAIL:-}" = yes ]; then exit 1; fi\n')
        fake.chmod(0o755)
        self.env=dict(os.environ,PATH=str(self.root)+os.pathsep+os.environ['PATH'],FAKE_DOCKER_LOG=str(self.log))

    def tearDown(self):self.tmp.cleanup()

    def launch(self,*args):
        return subprocess.run(['bash',str(ROOT/'sticky-installer.sh'),*args,'--output',str(self.output)],cwd=ROOT,env=self.env,capture_output=True,text=True)

    def test_no_socket_privilege_or_device_passthrough(self):
        backup=self.root/'backup';backup.write_bytes(b'private')
        result=self.launch('verify','--mode','preserve','--backup',str(backup),'--confirm-layout','protected-reference')
        self.assertEqual(result.returncode,0,result.stderr)
        text=self.log.read_text()
        self.assertIn('readonly',text);self.assertIn('--cap-drop\nALL',text)
        self.assertIn('--security-opt\nno-new-privileges',text)
        self.assertIn('dst=/output',text)
        for forbidden in ['docker.sock','--privileged','--device','--network\nhost']:
            self.assertNotIn(forbidden,text)

    def test_missing_daemon_stops_before_build(self):
        self.env['FAKE_DOCKER_FAIL']='yes'
        result=self.launch('build')
        self.assertNotEqual(result.returncode,0);self.assertIn('daemon is unavailable',result.stderr)
        self.assertNotIn('\nbuild\n',self.log.read_text());self.assertNotIn('\nrun\n',self.log.read_text())

    def test_unknown_commands_and_repository_output_rejected(self):
        self.assertNotEqual(self.launch('flash').returncode,0)
        result=subprocess.run(['bash',str(ROOT/'sticky-installer.sh'),'list','--output',str(ROOT)],env=self.env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('repository root',result.stderr)


if __name__=='__main__':unittest.main()
