"""Run this project's standard-library tests with the skill scripts on sys.path."""
from pathlib import Path
import argparse
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'skills' / 'resume-workbench' / 'scripts'))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pattern', default='test_*.py')
    args = parser.parse_args()
    tests = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=args.pattern)
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    raise SystemExit(main())
