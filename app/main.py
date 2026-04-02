# app/main.py
from fastapi import FastAPI
# NEW: Import X-Ray SDK
from aws_xray_sdk.core import xray_recorder, patch_all
from aws_xray_sdk.ext.fastapi.middleware import XRayMiddleware
import os

# Patch all supported libraries for X-Ray tracing
patch_all()


app = FastAPI()
# NEW: Configure the recorder and add the middleware to FastAPI
xray_recorder.configure(service='CoffeeShopBaristaAPI')
app.add_middleware(XRayMiddleware, app_name='CoffeeShopBaristaAPI')

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