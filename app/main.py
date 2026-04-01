# app/main.py
from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "healthy", "service": "CoffeeShop Barista API"}

@app.get("/health")
def health_check():
    # The ALB will ping this endpoint constantly to make sure the container is alive
    return {"status": "ok"}

@app.get("/config-check")
def check_db():
    # Proof that your Secrets Manager environment variables are working!
    db_user = os.environ.get("DB_USERNAME", "Not Found")
    return {"message": f"I am ready to connect to RDS as user: {db_user}"}