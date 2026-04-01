#!/usr/bin/env python3
"""Minify and gzip HTML files for ESP32 deployment.

Usage: python3 tools/minify_gzip.py [games/*.html]
       Without args: processes all games/*.html

Creates .min.html (minified) and .min.html.gz (gzip) in games/ directory.
The .min.html.gz files get uploaded to ESP32 as www/<name>.html.gz
"""

import gzip
import re
import sys
from pathlib import Path


def minify_html(text: str) -> str:
    """Simple HTML/CSS/JS minifier. Removes comments and excess whitespace."""
    # Remove HTML comments (but not IE conditionals)
    text = re.sub(r'<!--(?!\[).*?-->', '', text, flags=re.S)
    # Remove CSS/JS block comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    # Remove single-line JS comments (only at start of line to avoid breaking URLs)
    text = re.sub(r'^\s*//[^\n]*$', '', text, flags=re.M)
    # Collapse leading whitespace per line
    text = re.sub(r'\n[ \t]+', '\n', text)
    # Remove blank lines
    text = re.sub(r'\n{2,}', '\n', text)
    # Strip leading/trailing
    return text.strip() + '\n'


def process_file(path: Path) -> None:
    raw = path.read_text(encoding='utf-8')
    minified = minify_html(raw)
    gz_data = gzip.compress(minified.encode('utf-8'), compresslevel=9)

    gz_path = path.with_suffix('.html.gz')
    gz_path.write_bytes(gz_data)

    raw_size = len(raw.encode('utf-8'))
    min_size = len(minified.encode('utf-8'))
    gz_size = len(gz_data)
    ratio = raw_size / gz_size if gz_size else 0

    print(f"  {path.name}: {raw_size:,}B → min {min_size:,}B → gz {gz_size:,}B ({ratio:.1f}x)")


def main():
    games_dir = Path(__file__).parent.parent / 'games'

    if len(sys.argv) > 1:
        files = [Path(f) for f in sys.argv[1:]]
    else:
        files = sorted(games_dir.glob('*.html'))

    if not files:
        print("No HTML files found")
        sys.exit(1)

    print(f"Minify + gzip ({len(files)} files):")
    for f in files:
        process_file(f)
    print("Done.")


if __name__ == '__main__':
    main()
