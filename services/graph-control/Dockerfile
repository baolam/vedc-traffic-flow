FROM python:3.11-slim
WORKDIR /app
COPY services/graph-control/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/graph-control/ .
COPY src/rl/ /app/src/rl/
CMD ["python", "main.py"]
