"""Check the declared Windows environment and installed package versions."""
import importlib.metadata
import platform
import struct
import sys

EXPECTED={'PySide6_Essentials':'6.12.0','shiboken6':'6.12.0','numpy':'2.3.5'}

def main():
    errors=[]
    if sys.platform!='win32':errors.append('The live beta targets Windows, not this operating system')
    if sys.version_info[:2]!=(3,12):errors.append('Use Python 3.12 for the distributed Windows environment')
    if struct.calcsize('P')!=8 or platform.machine().lower() not in ('amd64','x86_64'):
        errors.append('Windows x86-64 is required; this package does not include ARM64 pins')
    for name,expected in EXPECTED.items():
        try:found=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:found='not installed'
        print(f'{name}: {found} (required {expected})')
        if found!=expected:errors.append(f'{name} does not match the declared version')
    if errors:
        print('\nEnvironment check FAILED:\n'+'\n'.join(errors));return 1
    try:
        from PySide6 import QtWidgets, QtGui
        import numpy
    except ImportError as exc:
        print(f'Qt/NumPy import failed: {type(exc).__name__}');return 1
    print('Declared Python and library versions OK; this is NOT a Windows/Elite functional test.')
    return 0

if __name__=='__main__':raise SystemExit(main())
