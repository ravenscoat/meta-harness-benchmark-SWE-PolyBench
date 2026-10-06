import json
import os
import shutil
import subprocess

import pytest

from benchmarks.polybench.report_capture import capture_argv


def test_non_json_commands_unchanged():
    assert capture_argv(['pytest', '-vv'], 20000000) == ['pytest', '-vv']


@pytest.mark.skipif(os.name == 'nt' or not shutil.which('node'), reason='POSIX Node runtime check')
def test_forced_exit_preserves_complete_json_and_exit_code():
    code = "process.stdout.write(JSON.stringify({data:'x'.repeat(6000000)}));process.exit(8)"
    argv = ['node', '-e', code, '--', '--reporter', 'json']
    result = subprocess.run(capture_argv(argv, 20000000), capture_output=True, timeout=30)
    assert result.returncode == 8
    assert len(json.loads(result.stdout)['data']) == 6000000


@pytest.mark.skipif(os.name == 'nt', reason='POSIX capture wrapper')
def test_shell_metacharacters_remain_literal_and_stderr_separate(tmp_path):
    marker = tmp_path / 'must-not-exist'
    arg = '$(touch ' + str(marker) + ')'
    argv = ['sh', '-c', 'printf "%s" "$1"; printf "error" >&2; exit 7', 'fixture', arg, '--reporter', 'json']
    result = subprocess.run(capture_argv(argv, 20000000), capture_output=True, timeout=10)
    assert result.returncode == 7 and result.stdout.decode() == arg and result.stderr == b'error'
    assert not marker.exists()
