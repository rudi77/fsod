"""Einstiegsskript für PyInstaller (eigenständige Executable).

PyInstaller braucht ein Top-Level-Skript als Aufhänger; das `agentkit`-Paket selbst
wird über den Import mitgebündelt. `agentkit/__main__.py` nutzt einen relativen
Import und eignet sich daher nicht direkt als PyInstaller-Entry — dieses Skript schon.
"""

from agentkit.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
