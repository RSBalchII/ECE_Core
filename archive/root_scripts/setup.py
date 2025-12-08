from setuptools import setup

# This is a monorepo - individual packages should be installed separately
# This setup.py exists to prevent package discovery errors
setup(
    name="context-engine",
    version="0.1.0",
    description="Monorepo for Context Engine - Executive Cognitive Enhancement tools",
    packages=[],  # No packages in root - install ece-core or anchor separately
    install_requires=[],
)