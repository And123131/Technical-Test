from fastapi import FastAPI

from app.database import create_tables
from app.api import router

app = FastAPI()

app.include_router(router)


@app.on_event("startup")
def startup():
    create_tables()
