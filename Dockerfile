FROM python:3.12-slim

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо файли та запускаємо додаток
COPY . .
CMD ["python", "main.py"]
