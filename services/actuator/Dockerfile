FROM python:3.11-slim
WORKDIR /app
COPY services/actuator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/actuator/ .
COPY src/ /app/src/
COPY contracts/ /app/contracts/
COPY networks/ /app/networks/
ENV PYTHONPATH=/app:/app/contracts
CMD ["python", "main.py"]
