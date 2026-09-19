from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_ROOT = REPO_ROOT / "berita-dampak" / "scripts"
ACCREDITATION_SCRIPT_ROOT = REPO_ROOT / "akreditasi" / "scripts"
for script_root in (SCRIPT_ROOT, ACCREDITATION_SCRIPT_ROOT):
    if str(script_root) not in sys.path:
        sys.path.insert(0, str(script_root))


@lru_cache(maxsize=None)
def load_module(filename: str) -> ModuleType:
    path = SCRIPT_ROOT / filename
    spec = importlib.util.spec_from_file_location(f"ugm_analytics_source_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load source module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=None)
def load_accreditation_module(filename: str) -> ModuleType:
    path = ACCREDITATION_SCRIPT_ROOT / filename
    spec = importlib.util.spec_from_file_location(f"ugm_analytics_accreditation_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load accreditation module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def kepmen() -> ModuleType:
    return load_module("kepmen_sdg.py")


def units() -> ModuleType:
    return load_module("unit_kerja.py")


def keywords() -> ModuleType:
    return load_module("keywords.py")
