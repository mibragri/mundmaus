#!/usr/bin/env python3
"""The firmware lint gate: suppressions with rule and reason, then ONE cppcheck run over src/.

fix_arduino3_deps.py runs it before a build whose sources or platformio.ini changed. By hand, with
PlatformIO's Python (it reads platformio.ini):

    ~/.platformio/penv/bin/python tools/lint_firmware.py [env]   -> exit 1 on any finding

All files in one run: unusedFunction and the report of stale suppressions (unmatchedSuppression)
need the whole program. Only include/ and src/ are on the include path; the framework's and the
libraries' headers stay out, cppcheck cannot preprocess all of them.
"""
import subprocess
import sys
from pathlib import Path

import check_suppressions

REPO = Path(__file__).resolve().parent.parent
FIRMWARE = REPO / 'firmware' / 'arduino'
CPPCHECK = Path.home() / '.platformio' / 'packages' / 'tool-cppcheck' / 'cppcheck'
SOURCE_SUFFIXES = {'.c', '.cpp', '.ino'}
TEMPLATE = '{file}:{line}:{column}: {severity}: {message} [{id}]'


def cppcheck_args(build_flags, cppcheck_flags):
    """Defines and language standard of the env's build_flags, then custom_cppcheck_flags."""
    # A stand-in, so the real OTA secret never appears on a lint command line.
    args = ['--language=c++', '--error-exitcode=1', '--template=' + TEMPLATE, '-DOTA_AUTH_B64="lint"']
    for flag in build_flags:
        if flag.startswith('-D'):
            args.append(flag.replace('\\"', '"'))  # platformio.ini escapes the quotes for the shell
        elif flag.startswith('-std='):
            args.append('--std=' + flag[len('-std='):].replace('gnu', 'c'))
    return args + list(cppcheck_flags)


def unanalysed(sources, output):
    """Sources without cppcheck's 'Checking <file>: <defines>...' line, which it prints only after
    it could preprocess the file."""
    checked = {line[len('Checking '):].split(': ', 1)[0]
               for line in output.splitlines() if line.startswith('Checking ') and ': ' in line}
    return [s for s in sources if s not in checked]


def run_cppcheck(firmware, build_flags, cppcheck_flags, cppcheck=CPPCHECK):
    """One line per finding; empty when cppcheck analysed every source and found nothing."""
    firmware = Path(firmware)
    sources = sorted(p.relative_to(firmware).as_posix()
                     for p in (firmware / 'src').rglob('*') if p.suffix in SOURCE_SUFFIXES)
    cmd = [str(cppcheck), *cppcheck_args(build_flags, cppcheck_flags), '-Iinclude', '-Isrc', 'src']
    try:
        result = subprocess.run(cmd, cwd=firmware, capture_output=True, text=True)
    except FileNotFoundError:
        return [f'{cppcheck} fehlt: pio pkg install -g -t platformio/tool-cppcheck']
    problems = [line for line in result.stderr.splitlines() if line.strip()]
    problems += [f'{s}: von cppcheck nicht analysiert' for s in unanalysed(sources, result.stdout)]
    if result.returncode != 0 and not problems:
        problems.append(f'cppcheck endete mit {result.returncode} ohne Befund')
    return problems


def main():
    from platformio.project.config import ProjectConfig  # PlatformIO's Python only

    env = 'env:' + (sys.argv[1] if len(sys.argv) > 1 else 'esp32')
    config = ProjectConfig(str(FIRMWARE / 'platformio.ini'))
    cppcheck = Path(config.get('platformio', 'packages_dir')) / 'tool-cppcheck' / 'cppcheck'
    problems = check_suppressions.check_repo(REPO)
    problems += run_cppcheck(FIRMWARE, config.get(env, 'build_flags'),
                             config.get(env, 'custom_cppcheck_flags').split(), cppcheck)
    for p in problems:
        print(p)
    if problems:
        print(f'\nLint: {len(problems)} Befund(e).', file=sys.stderr)
        return 1
    print('Lint: Unterdrueckungen begruendet, cppcheck ohne Befund in allen Quelldateien.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
