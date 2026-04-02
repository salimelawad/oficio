from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import io

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


class DocumentRequest(BaseModel):
    content: str
    lawyer_name: str
    inpreabogado: str
    title: str
    city: str
    date: str
    show_line_numbers: bool = True
    show_page_numbers: bool = True


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.post("/generate")
def generate(req: DocumentRequest):
    from pdf_generator import generate_pdf
    pdf = generate_pdf(req)
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=documento_legal.pdf"},
    )
