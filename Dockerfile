# Use an official NVIDIA CUDA image as a base
FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

# Set non-interactive frontend for package installers
ENV DEBIAN_FRONTEND=noninteractive

# Install software-properties-common and add deadsnakes PPA for Python 3.12
RUN apt-get update && apt-get install -y software-properties-common
RUN add-apt-repository ppa:deadsnakes/ppa -y

# Install system dependencies including Python and Git
RUN apt-get update && apt-get install -y     python3.12     python3.12-venv     python3-pip     git     && rm -rf /var/lib/apt/lists/*

# Set python3.12 as the default python
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1

# Install vLLM and our preferred package manager, UV
# We install vllm first as it has complex dependencies
RUN pip install vllm

# Install UV
RUN pip install "uv>=0.1.30"

# Install Python dependencies from requirements.txt
COPY requirements.txt .
RUN uv pip install --no-cache-dir -r requirements.txt --system
    
# Set the working directory inside the container
WORKDIR /app

# By default, copy the current project code into the container
# This is mainly for building the image, the volume mount will override this at runtime
COPY . .
