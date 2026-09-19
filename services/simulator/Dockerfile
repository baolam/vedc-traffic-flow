FROM python:3.11-slim

# Install SUMO system binaries and tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    sumo sumo-tools \
    && rm -rf /var/lib/apt/lists/*

ENV SUMO_HOME=/usr/share/sumo

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
