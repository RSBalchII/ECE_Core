FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
# Using --no-cache-dir reduces the image size
RUN pip install uv && uv pip install -r requirements.txt

# Copy the entire project's source code into the container
COPY . .

# Default command to run when the container starts (can be overridden)
CMD ["python", "ark_main.py"]