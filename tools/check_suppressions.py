#!/usr/bin/env python3
"""Every suppression names its rule and says why.

Checks the comments that switch a checker off (NOLINT, cppcheck-suppress, noqa, type: ignore,
eslint-disable, @ts-ignore, @ts-expect-error, shellcheck disable) in every tracked source file, and
the suppressions in firmware/arduino/platformio.ini (-Wno-*, cppcheck --suppress=, clang-tidy check
exclusions). Whether a suppression is still needed is checked by the tools themselves where they can:
cppcheck reports a stale one as unmatchedSuppression (tools/lint_firmware.py), so that one must never
be suppressed; for Python, mypy reports an unused type: ignore and ruff an unused noqa (RUF100).

Usage: python3 tools/check_suppressions.py   -> exit 1 and one line per problem
"""
import re
import subprocess
import sys
from pathlib import Path

REASON = r'\S.{3,}'  # some words after the rule; what they say is for a review to judge

# (name, finds the directive, a compliant directive matches this; None: never allowed)
DIRECTIVES = [
    ('NOLINT', re.compile(r'//\s*NOLINT(?:NEXTLINE|BEGIN|END)?\b'),
     re.compile(r'//\s*NOLINT(?:NEXTLINE|BEGIN|END)?\([\w.,*-]+\)\s*' + REASON)),
    ('cppcheck-suppress', re.compile(r'cppcheck-suppress'),
     re.compile(r'cppcheck-suppress\s+\w+\s+' + REASON)),
    ('noqa', re.compile(r'#\s*noqa\b'),
     re.compile(r'#\s*noqa:\s*[A-Z]+\d+(?:\s*,\s*[A-Z]+\d+)*\s+' + REASON)),
    ('type: ignore', re.compile(r'#\s*type:\s*ignore\b'),
     re.compile(r'#\s*type:\s*ignore\[[\w-]+(?:,\s*[\w-]+)*\]\s*#?\s*' + REASON)),
    ('eslint-disable', re.compile(r'eslint-disable'),
     re.compile(r'eslint-disable(?:-next-line|-line)?\s+[\w@/-]+(?:\s*,\s*[\w@/-]+)*\s+--\s+' + REASON)),
    ('@ts-ignore', re.compile(r'@ts-ignore'), None),
    ('@ts-expect-error', re.compile(r'@ts-expect-error'),
     re.compile(r'@ts-expect-error:?\s+' + REASON)),
    ('shellcheck disable', re.compile(r'#\s*shellcheck\s+disable='),
     re.compile(r'#\s*shellcheck\s+disable=SC\d+(?:,SC\d+)*\s+#?\s*' + REASON)),
]

SOURCE_SUFFIXES = {'.c', '.cpp', '.h', '.hpp', '.ino', '.py', '.js', '.ts', '.html', '.sh'}

# The checker and its test carry the bad examples as data.
SELF = {'tools/check_suppressions.py', 'tests/test_suppressions.py'}

PLATFORMIO = 'firmware/arduino/platformio.ini'


def check_line(line):
    """None if the line holds no suppression or a compliant one, else what is missing."""
    for name, finds, compliant in DIRECTIVES:
        if not finds.search(line):
            continue
        if compliant is None:
            return f'{name} ist nicht erlaubt (stattdessen eine gezielte Ausnahme mit Grund)'
        if not compliant.search(line):
            return f'{name} ohne Regelname oder ohne Begruendung'
    return None


def check_platformio(text):
    """Suppressions in platformio.ini need a reason: an inline '; ...' or a comment line right above."""
    problems = []
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        code, sep, comment = raw.partition(';')
        above = lines[i - 1].strip() if i > 0 else ''
        has_reason = (sep and len(comment.strip()) > 3) or (above.startswith(';') and len(above.lstrip('; ')) > 3)
        found = re.findall(r'-Wno-[\w-]+', code)
        found += ['--suppress=' + s for s in re.findall(r'--suppress=([\w:*/.-]+)', code)]
        tidy = re.search(r'--checks=(\S+)', code)
        if tidy:
            found += [c for c in tidy.group(1).split(',') if c.startswith('-') and c != '-*']
        for f in found:
            if f.startswith('--suppress=unmatchedSuppression'):
                problems.append(f'{PLATFORMIO}:{i + 1}: {f} verdeckt veraltete Unterdrueckungen')
            elif not has_reason:
                problems.append(f'{PLATFORMIO}:{i + 1}: {f} ohne Begruendung')
    return problems


def tracked_sources(root, suffixes=SOURCE_SUFFIXES):
    tracked = subprocess.run(['git', 'ls-files'], cwd=root, capture_output=True, text=True,
                             check=True).stdout.splitlines()
    return [rel for rel in tracked if rel not in SELF and Path(rel).suffix in suffixes]


def check_repo(root):
    root = Path(root)
    problems = []
    for rel in tracked_sources(root):
        try:
            text = (root / rel).read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as e:
            problems.append(f'{rel}: nicht lesbar ({e})')
            continue
        for n, line in enumerate(text.splitlines(), 1):
            msg = check_line(line)
            if msg:
                problems.append(f'{rel}:{n}: {msg}')
    problems += check_platformio((root / PLATFORMIO).read_text(encoding='utf-8'))
    return problems


def stale_python(root, paths):
    """Python suppressions their tool no longer needs: mypy's unused-ignore, ruff's RUF100."""
    texts = {rel: (Path(root) / rel).read_text(encoding='utf-8') for rel in paths}
    ignores = [rel for rel, t in texts.items() if re.search(r'#\s*type:\s*ignore\b', t)]
    noqas = [rel for rel, t in texts.items() if re.search(r'#\s*noqa\b', t)]
    # RUF100 judges only codes whose rules are selected; select exactly the ones in use.
    codes = sorted({code for t in texts.values()
                    for m in re.finditer(r'#\s*noqa:\s*([A-Z]+\d+(?:\s*,\s*[A-Z]+\d+)*)', t)
                    for code in re.split(r'\s*,\s*', m.group(1))})
    runs = []
    if ignores:
        runs.append((['mypy', '--warn-unused-ignores', '--follow-imports=silent', '--no-error-summary',
                      *ignores], '[unused-ignore]'))
    if noqas:
        runs.append((['ruff', 'check', '--no-cache', '--output-format=concise',
                      '--select', ','.join(['RUF100', *codes]), *noqas], ' RUF100 '))
    problems = []
    for cmd, marker in runs:
        try:
            result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        except FileNotFoundError:
            problems.append(f'{cmd[0]} fehlt: ob eine Unterdrueckung in Python veraltet ist, bleibt ungeprueft')
            continue
        if result.returncode not in (0, 1):
            problems.append(f'{cmd[0]} endete mit {result.returncode}: {result.stderr.strip()[:300]}')
        problems += [line for line in result.stdout.splitlines() if marker in line]
    return problems


def main():
    root = Path(__file__).resolve().parent.parent
    problems = check_repo(root)
    problems += stale_python(root, tracked_sources(root, {'.py'}))
    for p in problems:
        print(p)
    if problems:
        print(f'\n{len(problems)} Befund(e) zu Unterdrueckungen.', file=sys.stderr)
        return 1
    print('Unterdrueckungen: alle gezielt, begruendet und noch noetig.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
