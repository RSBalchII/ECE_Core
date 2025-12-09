import importlib.util
from pathlib import Path


def test_generate_env_outputs_ubatch_default():
    path = Path(__file__).parents[1] / 'scripts' / 'generate_llama_env.py'
    spec = importlib.util.spec_from_file_location('generate_llama_env', str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # The module prints outputs but also defines the OUT dict; verify it exists
    assert hasattr(module, 'OUT')
    out = getattr(module, 'OUT')
    assert 'LLAMA_UBATCH' in out
    assert int(out['LLAMA_UBATCH']) >= 512
