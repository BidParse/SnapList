from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from google import genai
from PIL import Image
import io

app = FastAPI()

client = genai.Client()

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("index.html", "r") as f:
        return f.read()

@app.post("/api/generate-listing")
async def generate_listing(image_file: UploadFile = File(...)):
    image_data = await image_file.read()
    image = Image.open(io.BytesIO(image_data))
    
    prompt = """
    You are an expert e-commerce seller. Analyze this image and generate a high-converting online marketplace listing.
    Return ONLY the following three sections in plain text:
    
    TITLE: [A click-optimized, keyword-rich title]
    PRICE ESTIMATE: [A fair market resale value range]
    DESCRIPTION: [A detailed, SEO-friendly description noting any visible features or conditions]
    """
    
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=[image, prompt]
    )
    
    return {"listing": response.text}
