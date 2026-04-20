FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY agentcore_entrypoint.py .
COPY strand_agent.py .
COPY tools.py .
COPY db.py .
COPY db_direct.py .
COPY config.py .

# Expose port 8080 (AgentCore requirement)
EXPOSE 8080

# Run the agent
CMD ["python", "agentcore_entrypoint.py"]
