import os
from functools import lru_cache
from pathlib import Path
import importlib
import sys


def makeToAbsolutPath(string_relativPath):
        dirname = get_base_path()
        filename = os.path.join(dirname, string_relativPath)
        return filename


"""returns base-path - works both with .py and .exe."""
def get_base_path() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def getClassByName(fileName: str, className: str):
    base = get_base_path()
    script_path = os.path.join(base, f"{fileName}.py")

    # only load if not cashed
    if fileName not in sys.modules:
        spec = importlib.util.spec_from_file_location(fileName, script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[fileName] = module       # chache 
        spec.loader.exec_module(module)

    return getattr(sys.modules[fileName], className)


@lru_cache(maxsize=1)
def getAllAvailableReactions() -> list[str]:
    reactions_folder = Path(get_base_path()) / "reaction_definitions"

    if not reactions_folder.exists(): #safety check
        return []

    return [
        p.stem
        for p in reactions_folder.glob("*.yaml")
        if p.stem.lower() != "template"    # filter out non-valid scripts
    ]