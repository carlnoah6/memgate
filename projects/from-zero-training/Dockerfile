FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

WORKDIR /app

# Install git and other basics if needed
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements if we had them (placeholder)
# COPY requirements.txt .
# RUN pip install -r requirements.txt

# Copy source code
COPY src/ /app/src/

# Set the entrypoint
CMD ["python3", "src/train.py"]
