import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from dotenv import load_dotenv, find_dotenv

from app.routers import routers

app = FastAPI(title="K-MANNER SPEECH", version="0.0.1")
app.include_router(routers.router)