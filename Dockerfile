# Use an official NVIDIA CUDA image as a base
FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

# Set non-interactive frontend for package installers
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies including Python and Git
RUN apt-get update && apt-get install -y     python3.11     python3.11-venv     python3-pip     git     && rm -rf /var/lib/apt/lists/*

# Set python3.11 as the default python
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# Install vLLM and our preferred package manager, UV
# We install vllm first as it has complex dependencies
RUN pip install vllm

# Set the working directory inside the container
WORKDIR /app

# By default, copy the current project code into the container
# This is mainly for building the image, the volume mount will override this at runtime
COPY . .

# Install the rest of our project dependencies using UV
RUN pip install "uv>=0.1.30"
RUN uv pip install --system -r requirements.txt

# Command to keep the container running
CMD ["tail", "-f", "/dev/null"]