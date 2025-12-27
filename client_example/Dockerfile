FROM python:3.13-slim

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY client_bot.py .

CMD ["python", "client_bot.py"]