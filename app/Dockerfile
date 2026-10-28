FROM python:3.13-slim AS app

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

# Switch to user
RUN useradd -m app
USER app

CMD ["python", "app.py"]