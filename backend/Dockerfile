# Base Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# Expose port (e.g., 8000 for the gateway)
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 