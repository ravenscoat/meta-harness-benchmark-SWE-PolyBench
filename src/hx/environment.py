"""Cheap environment bootstrap; reports tools without running repository code."""
import platform
import shutil
import sys


def snapshot() -> dict:
    return {
        "scope": "HX controller process; container adapters may have different tools",
        "platform": platform.system(),
        "python": {"executable": sys.executable, "version": platform.python_version()},
        "available_tools": {name: shutil.which(name) for name in
            ("git", "python", "python3", "node", "npm", "yarn", "pnpm", "pytest", "rg")},
        "limits": "Availability only; versions, dependencies and functional checks are not proved. No repository code executed.",
    }
