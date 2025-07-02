# utils/routers/pages.py
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", name="home")
async def get_form(request: Request):
    """Serves the main web chat form."""
    return templates.TemplateResponse("form.html", {"request": request})
