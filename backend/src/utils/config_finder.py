from pathlib import Path


def find_config_path() -> str | None:
    """Find a config.yaml across known locations: repo_root/configs/config.yaml, repo_root/config.yaml, repo_root/ece-core/config.yaml.

    Returns the first path that exists or None.
    """
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [repo_root / "configs" / "config.yaml", repo_root / "config.yaml", repo_root / "ece-core" / "config.yaml"]
    for p in candidates:
        if p.exists():
            return str(p)
    return None
