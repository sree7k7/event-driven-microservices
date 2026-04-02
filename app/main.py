# app/main.py
from fastapi import FastAPI
import os

from aws_xray_sdk.core import xray_recorder, patch_all
from xraysink.context import AsyncContext
from xraysink.asgi.middleware import xray_middleware
from starlette.middleware.base import BaseHTTPMiddleware

# Patch all supported libraries for X-Ray tracing
patch_all()

# NEW: Configure the recorder with AsyncContext specifically for FastAPI
# xray_recorder.configure(context=AsyncContext(), service='CoffeeShopBaristaAPI')
xray_recorder.configure(context=AsyncContext(), service='CoffeeShopBaristaAPI', plugins=())


app = FastAPI()

# NEW: Add the X-Ray middleware using Starlette's BaseHTTPMiddleware
app.add_middleware(BaseHTTPMiddleware, dispatch=xray_middleware)

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