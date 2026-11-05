"""Keep later owner evidence artifact-specific and separate from build defaults."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import ROOT,TABLE_SHA256
from compatibility import select


class HardwareEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.path='manifests/v1.1-hardware-validation.json'
        self.report=json.loads((ROOT/self.path).read_text())

    def test_exact_artifact_and_approved_source_combination(self):
        entry=select();r=self.report;c=r['combination']
        self.assertEqual(r['evidence_type'],'owner-reported')
        self.assertEqual(r['status'],'PASS')
        self.assertEqual(c['id'],entry['id'])
        self.assertEqual(c['crosspoint_version'],entry['crosspoint']['version'])
        self.assertEqual(c['crosspoint_commit'],entry['crosspoint']['commit'])
        self.assertEqual(c['crosspoint_patch_sha256'],entry['crosspoint']['patch_sha256'])
        self.assertEqual(c['seeedash_version'],entry['seeedash']['version'])
        self.assertEqual(c['seeedash_official_sha256'],entry['seeedash']['sha256'])
        self.assertEqual(c['partition_table_sha256'],TABLE_SHA256)
        self.assertEqual(r['artifact']['fresh_image_sha256'],
                         'e4dcb8b45d07cdc367ef03517c19c4f59aab839aae4041dfcd3c50ad4c43f073')
        self.assertEqual(r['artifact']['fresh_image_bytes'],33554432)

    def test_all_nine_reported_hardware_tests_and_pipeline_results_retained(self):
        tests=self.report['hardware_tests']
        self.assertEqual(tests['passed'],9);self.assertEqual(tests['total'],9)
        self.assertEqual([t['id'] for t in tests['cases']],list(range(1,10)))
        self.assertTrue(all(t['status']=='PASS' for t in tests['cases']))
        self.assertEqual(len(self.report['pipeline_checks']),6)
        self.assertTrue(all(v=='PASS' for v in self.report['pipeline_checks'].values()))

    def test_owner_evidence_does_not_promote_future_build_hardware_claims(self):
        scope=self.report['scope']
        self.assertTrue(scope['exact_artifact_only'])
        self.assertFalse(scope['future_builds_hardware_tested'])
        self.assertFalse(scope['other_devices_or_revisions_validated'])
        self.assertEqual(self.report['device']['tested_device_count'],1)
        defaults=select()['hardware_validation']
        self.assertFalse(defaults['new_build_tested'])
        self.assertFalse(defaults['docker_build_tested'])
        historical=json.loads((ROOT/defaults['report']).read_text())
        self.assertIn(self.path,historical['additional_reports'])
        self.assertEqual(self.report['ota'],'UNSUPPORTED/FORBIDDEN')
