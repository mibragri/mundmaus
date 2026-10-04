"""Tests for tools/lint_firmware.py, the firmware lint gate (task 3cb7): it fails on every finding of
every severity, on a stale suppression and on a source file cppcheck could not analyse."""
import subprocess
from pathlib import Path

import pytest

import lint_firmware as lint

FLAGS = ['--enable=all', '--inline-suppr', '--suppress=missingIncludeSystem']
needs_cppcheck = pytest.mark.skipif(not lint.CPPCHECK.exists(), reason='PlatformIO tool-cppcheck missing')
PENV_PYTHON = Path.home() / '.platformio' / 'penv' / 'bin' / 'python'


def tree(tmp_path, files):
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    (tmp_path / 'include').mkdir(exist_ok=True)
    return tmp_path


def test_defines_and_standard_come_from_the_build_flags():
    args = lint.cppcheck_args(['-DMUNDMAUS_VERSION=\\"4.2.16\\"', '-DPIN_SW=21', '-std=gnu++17', '-Wall'],
                              ['--enable=all'])
    assert '-DMUNDMAUS_VERSION="4.2.16"' in args
    assert '-DPIN_SW=21' in args
    assert '--std=c++17' in args
    assert '-Wall' not in args
    assert args[-1] == '--enable=all'


def test_a_source_without_a_checking_line_is_unanalysed():
    out = 'Checking src/a.cpp ...\nChecking src/a.cpp: X=1...\nChecking src/b.cpp ...\n'
    assert lint.unanalysed(['src/a.cpp', 'src/b.cpp'], out) == ['src/b.cpp']


@needs_cppcheck
def test_a_clean_tree_passes(tmp_path):
    fw = tree(tmp_path, {'src/a.cpp': '#include <Arduino.h>\nint helper(int a);\nint main() { return helper(1); }\n',
                         'src/b.cpp': '#include <Arduino.h>\nint helper(int a) { return a + 1; }\n'})
    assert lint.run_cppcheck(fw, ['-DX=1'], FLAGS) == []


@needs_cppcheck
def test_an_error_fails_the_gate(tmp_path):
    fw = tree(tmp_path, {'src/a.cpp': '#include <Arduino.h>\nint main() { int* p = nullptr; return *p; }\n'})
    assert any('[nullPointer]' in p for p in lint.run_cppcheck(fw, ['-DX=1'], FLAGS))


@needs_cppcheck
def test_an_unused_function_is_found_across_files(tmp_path):
    fw = tree(tmp_path, {'src/a.cpp': '#include <Arduino.h>\nint helper(int a);\nint main() { return helper(1); }\n',
                         'src/b.cpp': '#include <Arduino.h>\nint helper(int a) { return a + 1; }\nint dead() { return 2; }\n'})
    problems = lint.run_cppcheck(fw, ['-DX=1'], FLAGS)
    assert any("'dead'" in p and '[unusedFunction]' in p for p in problems), problems
    assert not any("'helper'" in p for p in problems), problems


@needs_cppcheck
def test_a_stale_suppression_fails_the_gate(tmp_path):
    fw = tree(tmp_path, {'src/a.cpp': '#include <Arduino.h>\n// cppcheck-suppress nullPointer -- planted\n'
                                      'int main() { return 0; }\n'})
    assert any('[unmatchedSuppression]' in p for p in lint.run_cppcheck(fw, ['-DX=1'], FLAGS))


@needs_cppcheck
def test_a_file_cppcheck_cannot_preprocess_fails_the_gate(tmp_path):
    fw = tree(tmp_path, {'src/a.cpp': '#include <Arduino.h>\n#include "bad.h"\nint main() { return 0; }\n',
                         'include/bad.h': '#error planted\n'})
    assert 'src/a.cpp: von cppcheck nicht analysiert' in lint.run_cppcheck(fw, ['-DX=1'], FLAGS)


@needs_cppcheck
@pytest.mark.skipif(not PENV_PYTHON.exists(), reason="PlatformIO's Python missing")
@pytest.mark.parametrize('env', ['esp32', 'esp32_testhooks', 'esp32s3'])
def test_the_firmware_passes(env):
    result = subprocess.run([str(PENV_PYTHON), lint.__file__, env], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
