"""Offline regression for the base-image/main-vs-security dependency mismatch."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import audit_builder
from common import ROOT,sha


class AptSourcesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ['Dockerfile','.dockerignore','manifests/builder.lock.json','docker/apt.sources']:
            target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,target)
        self.patch=mock.patch.object(audit_builder,'ROOT',self.root);self.patch.start()
        self.source=self.root/'docker/apt.sources'

    def tearDown(self):self.patch.stop();self.tmp.cleanup()

    def change_source(self,text):
        self.source.write_text(text)
        path=self.root/'manifests/builder.lock.json';lock=json.loads(path.read_text())
        lock['files']['docker/apt.sources']=sha(self.source.read_bytes())
        path.write_text(json.dumps(lock))

    def test_complete_signed_snapshot_streams(self):
        lock=json.loads((self.root/'manifests/builder.lock.json').read_text())
        entries=audit_builder.apt_sources(lock)
        self.assertEqual([x['Suites'] for x in entries],['bookworm bookworm-updates','bookworm-security'])
        self.assertTrue(all(lock['debian_snapshot'] in x['URIs'] for x in entries))
        self.assertTrue(all(x['Signed-By']=='/usr/share/keyrings/debian-archive-keyring.gpg' for x in entries))
        self.assertEqual(audit_builder.configuration()['status'],'PASS')

    def test_missing_security_or_updates_is_rejected(self):
        original=self.source.read_text()
        for broken in [original.split('\n\n')[0]+'\n',original.replace('bookworm bookworm-updates','bookworm')]:
            self.change_source(broken)
            with self.assertRaises(ValueError):audit_builder.configuration()

    def test_live_or_mixed_snapshot_sources_are_rejected(self):
        original=self.source.read_text()
        for broken in [original.replace('debian-security/20261102T000000Z','debian-security/20261103T000000Z'),
                       original.replace('https://snapshot.debian.org/archive/debian/20261102T000000Z/','https://deb.debian.org/debian')]:
            self.change_source(broken)
            with self.assertRaises(ValueError):audit_builder.configuration()

    def test_signature_bypass_and_duplicate_fields_are_rejected(self):
        original=self.source.read_text()
        for broken in [original.replace('Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg','Trusted: yes'),
                       original.replace('Components: main','Components: main\nComponents: main')]:
            self.change_source(broken)
            with self.assertRaises(ValueError):audit_builder.configuration()

    def test_multiline_apt_failure_bypasses_are_rejected(self):
        path=self.root/'Dockerfile';original=path.read_text()
        for flag in ['--allow-downgrades','--allow-unauthenticated','--force-yes']:
            path.write_text(original.replace('apt-get install -y', 'apt-get install -y '+flag))
            with self.assertRaisesRegex(ValueError,'must not be bypassed'):audit_builder.configuration()

    def test_inherited_live_sources_must_be_removed_and_lock_must_match(self):
        path=self.root/'Dockerfile';original=path.read_text()
        path.write_text(original.replace('RUN rm -f /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources && ', 'RUN '))
        with self.assertRaisesRegex(ValueError,'inherited live APT'):audit_builder.configuration()
        path.write_text(original)
        self.source.write_text(self.source.read_text()+'\n# unreviewed modification\n')
        with self.assertRaisesRegex(ValueError,'differs from builder lock'):audit_builder.configuration()


if __name__=='__main__':unittest.main()
