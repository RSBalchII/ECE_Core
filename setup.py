from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np

# Define extensions that will be compiled with Cython
extensions = [
    Extension(
        "ece.agents.tier3.qlearning.qlearning_cpp",
        [
            "ece/agents/tier3/qlearning/qlearning_cpp.pyx",
            "ece/agents/tier3/qlearning/qlearning_core.cpp"
        ],
        include_dirs=[np.get_include(), "ece/agents/tier3/qlearning/"],
        language="c++",
        extra_compile_args=["-std=c++11"],
        extra_link_args=[]
    ),
    Extension(
        "ece.agents.tier3.distiller.distiller_cpp",
        [
            "ece/agents/tier3/distiller/distiller_cpp.pyx",
            "ece/agents/tier3/distiller/distiller_core.cpp"
        ],
        include_dirs=[np.get_include(), "ece/agents/tier3/distiller/"],
        language="c++",
        extra_compile_args=["-std=c++11"],
        extra_link_args=[]
    )
]

setup(
    name="ECE Optimized Modules",
    ext_modules=cythonize(
        extensions,
        compiler_directives={'language_level': 3}  # Use Python 3
    ),
    zip_safe=False,
)