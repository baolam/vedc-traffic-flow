FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV CONTRACTS_DIR=/contracts
ENV PYTHONPATH=/app:/contracts

RUN pip install --no-cache-dir \
    paho-mqtt==1.6.1 \
    pydantic==2.6.4 \
    pydantic-settings==2.2.1 \
    jsonschema==4.21.1

COPY services/actuator /app
COPY contracts /contracts
COPY src /app/src

CMD ["python", "main.py"]
