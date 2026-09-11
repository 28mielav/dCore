import json
from dcore.gates.release import read_runtime_report


def test_report_is_not_independent_execution(tmp_path):
    path = tmp_path / 'report.json'
    report = dict(status='PASS', cases={'reload': 'PASS'})
    path.write_text(json.dumps(report))
    assert read_runtime_report(path, ('reload',), 'abc', {'minecraft': '1.21.8'})['state'] == 'RUNTIME_INVALID'
    report.update(project_sha256='abc', environment={'minecraft': '1.21.8'},
                  provenance={'runner': 'user', 'timestamp': '2026-09-08T20:00:00Z', 'method': 'manual client'})
    path.write_text(json.dumps(report))
    result = read_runtime_report(path, ('reload',), 'abc', {'minecraft': '1.21.8'})
    assert result['state'] == 'RUNTIME_USER_REPORTED'
    assert result['independently_verified'] is False
    assert read_runtime_report(path, ('reload',), 'changed', {'minecraft': '1.21.8'})['state'] == 'RUNTIME_INVALID'
    assert read_runtime_report(path, ('reload',), 'abc', {'minecraft': '1.21.4'})['state'] == 'RUNTIME_INVALID'


def test_malformed_report_does_not_crash(tmp_path):
    path = tmp_path / 'report.json'
    path.write_text('[]')
    assert read_runtime_report(path, ('reload',))['state'] == 'RUNTIME_INVALID'
