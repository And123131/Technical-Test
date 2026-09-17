from datetime import date
from typing import Literal

from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

from app.service import process_csv, delete_row, export_data

router = APIRouter()


class UploadResponse(BaseModel):
    message: str
    rows_inserted: int


class DeleteResponse(BaseModel):
    message: str
    row_id: int


@router.get("/")
def index():
    return {"message": "Test API"}


@router.post("/upload-csv/", response_model=UploadResponse)
def upload_csv(file: UploadFile = File(...)):
    return process_csv(file)


@router.delete("/delete/{row_id}", response_model=DeleteResponse)
def delete_row_endpoint(row_id: int):
    return delete_row(row_id)


@router.get("/export/")
def export(
        from_date: date,
        to_date: date,
        format: Literal["json", "csv"] = "json"
):
    return export_data(
        from_date,
        to_date,
        format
    )
