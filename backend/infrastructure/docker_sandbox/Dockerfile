# UI-Pro Docker Sandbox
# Isolated environment for code execution

FROM python:3.12-slim

# Install minimal dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    npm \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -s /bin/bash sandboxuser

# Set work directory
WORKDIR /home/sandboxuser

# Copy execution script
COPY sandbox_executor.py /home/sandboxuser/executor.py
RUN chown -R sandboxuser:sandboxuser /home/sandboxuser

# Switch to non-root user
USER sandboxuser

# Set Python path
ENV PYTHONPATH=/home/sandboxuser

# Default command
CMD ["python", "executor.py"]