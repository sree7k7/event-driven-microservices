# 1. Base Image: Use a slim, official Python image to reduce vulnerability surface area
FROM python:3.12-slim

# 2. Environment Variables: Best practices for Python in Docker
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Install Dependencies first (This caches the layer so rebuilds are blazing fast)
# Note: Create a 'requirements-app.txt' with your web app dependencies (e.g., fastapi, uvicorn, psycopg2)
COPY app/requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt

# 5. Copy your actual application code into the container
COPY ./app /app

# 6. Security: NEVER run containers as the 'root' user in production. 
# Create a restricted user and switch to it.
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# 7. Expose the port your application will listen on (Matches your ALB listener on port 80)
EXPOSE 80

# 8. Start the server (Example uses Uvicorn for FastAPI)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]