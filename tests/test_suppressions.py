"""Tests for tools/check_suppressions.py: a suppression is allowed only when it names its rule and
says why (agents/quality-prompt.md; user's order of 04.10.2026, task 3cb7)."""
import shutil
from pathlib import Path

import pytest

import check_suppressions as cs


@pytest.mark.parametrize('line', [
    'int x = f();  // NOLINT',
    'int x = f();  // NOLINT(bugprone-foo)',
    '// NOLINTNEXTLINE',
    '// cppcheck-suppress',
    '// cppcheck-suppress nullPointer',
    'x = 1  # noqa',
    'x = 1  # noqa: E501',
    'x = f()  # type: ignore',
    'x = f()  # type: ignore[attr-defined]',
    '// eslint-disable-next-line',
    '// eslint-disable-next-line no-undef',
    '// @ts-ignore',
    '// @ts-expect-error',
    '# shellcheck disable=SC2086',
])
def test_a_suppression_without_rule_or_reason_is_reported(line):
    assert cs.check_line(line), line


@pytest.mark.parametrize('line', [
    'int x = f();  // NOLINT(bugprone-foo) the RSSI is int8_t, the warning does not apply',
    '// NOLINTNEXTLINE(readability-magic-numbers) datasheet value, see sensors.h',
    '// cppcheck-suppress nullPointer -- checked by the caller, see config.cpp',
    'x = 1  # noqa: E501 - a URL that cannot be split',
    'x = f()  # type: ignore[attr-defined]  # added at runtime by PlatformIO',
    '// eslint-disable-next-line no-undef -- defined by device-link.js',
    '// @ts-expect-error: the runner adds this field',
    '# shellcheck disable=SC2086 # word splitting wanted here',
    'int nolint_counter = 0;',
    '// the word NOLINT in prose is not a suppression of this line',
])
def test_a_specific_suppression_with_a_reason_passes(line):
    assert cs.check_line(line) is None, cs.check_line(line)


def test_platformio_suppressions_need_a_reason():
    ini = (
        "build_flags =\n"
        "    -Wno-foo  ; the framework's own code triggers this (lib.cpp:12)\n"
        "    -Wno-bar\n"
        "check_flags =\n"
        "    cppcheck: --enable=all --suppress=missingIncludeSystem\n"
    )
    problems = cs.check_platformio(ini)
    assert any('-Wno-bar' in p for p in problems)
    assert any('missingIncludeSystem' in p for p in problems)
    assert not any('-Wno-foo' in p for p in problems)


def test_platformio_suppression_reason_may_stand_on_the_line_above():
    ini = (
        "check_flags =\n"
        "    ; cppcheck gets no system headers (check_skip_packages)\n"
        "    cppcheck: --enable=all --suppress=missingIncludeSystem\n"
    )
    assert cs.check_platformio(ini) == []


def test_unmatched_suppression_must_not_be_suppressed():
    ini = (
        "check_flags =\n"
        "    ; reason\n"
        "    cppcheck: --suppress=unmatchedSuppression\n"
    )
    assert any('unmatchedSuppression' in p for p in cs.check_platformio(ini))


def test_the_repository_passes():
    assert cs.check_repo(Path(__file__).parent.parent) == []


needs_mypy_and_ruff = pytest.mark.skipif(not (shutil.which('mypy') and shutil.which('ruff')),
                                         reason='mypy or ruff missing')


@needs_mypy_and_ruff
def test_a_stale_python_suppression_is_reported(tmp_path):
    (tmp_path / 'a.py').write_text('import json  # noqa: E402 - planted\n'
                                   'x = json.dumps(1)  # type: ignore[arg-type]  # planted\n')
    problems = cs.stale_python(tmp_path, ['a.py'])
    assert any('RUF100' in p for p in problems), problems
    assert any('[unused-ignore]' in p for p in problems), problems


@needs_mypy_and_ruff
def test_a_needed_python_suppression_is_not_reported(tmp_path):
    (tmp_path / 'a.py').write_text('x = 1\nimport json  # noqa: E402 - planted\n'
                                   'import not_installed_here  # type: ignore[import-not-found]  # planted\n')
    assert cs.stale_python(tmp_path, ['a.py']) == []


@needs_mypy_and_ruff
def test_no_python_suppression_in_the_repository_is_stale():
    root = Path(__file__).parent.parent
    assert cs.stale_python(root, cs.tracked_sources(root, {'.py'})) == []
