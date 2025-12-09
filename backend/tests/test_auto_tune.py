import importlib.util
import sys
from pathlib import Path


def test_recommend_settings_basic():
    path = Path(__file__).parents[1] / 'scripts' / 'auto_tune_llama.py'
    spec = importlib.util.spec_from_file_location('auto_tune', str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    rec = module.recommend_settings(16, 8)  # 16GB VRAM, 8GB model size
    assert rec is not None
    assert 'recommended_ctx' in rec
    assert 'recommended_ubatch' in rec
    assert rec['recommended_ctx'] > 0
    assert rec['recommended_ubatch'] in (512, 1024, 2048)
