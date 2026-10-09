FROM python:3.11-slim
WORKDIR /app
COPY services/experiment-runner/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/experiment-runner/ .
COPY src/ /app/src/
COPY contracts/ /app/contracts/
COPY networks/ /app/networks/
COPY services/simulator/sumo_configs/ /app/services/simulator/sumo_configs/
COPY configs/ /app/configs/
ENV PYTHONPATH=/app:/app/contracts
CMD ["python", "runner.py"]
