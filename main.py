from fastapi import FastAPI, UploadFile, File
from google import genai
from PIL import Image
import io

app = FastAPI()

# The client automatically picks up the GEMINI_API_KEY you will set in Render
client = genai.Client()

@app.post("/api/generate-listing")
async def generate_listing(image_file: UploadFile = File(...)):
    # Read the uploaded image file into memory
    image_data = await image_file.read()
    image = Image.open(io.BytesIO(image_data))
    
    # The prompt forces Gemini to act as an expert reseller
    prompt = """
    You are an expert e-commerce seller. Analyze this image and generate a high-converting online marketplace listing.
    Return ONLY the following three sections in plain text:
    
    TITLE: [A click-optimized, keyword-rich title]
    PRICE ESTIMATE: [A fair market resale value range]
    DESCRIPTION: [A detailed, SEO-friendly description noting any visible features or conditions]
    """
    
    # Send the photo and instructions to Gemini 1.5 Flash
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=[image, prompt]
    )
    
    return {"listing": response.text}
