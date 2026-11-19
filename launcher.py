"""Packaged entry point, independent of this Mac's source-launch configuration."""
import multiprocessing
import sys

def main():
    multiprocessing.freeze_support()
    if sys.argv[1:2] == ['--self-test']:
        from package_selftest import main as test
        return test(sys.argv[2:])
    from app import main as gui
    return gui()

if __name__=='__main__':raise SystemExit(main())
