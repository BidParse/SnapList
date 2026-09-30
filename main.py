
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
    try:
        image_data = await image_file.read()
        image = Image.open(io.BytesIO(image_data))
        
        # Convert any format (WEBP, PNG, CMYK, etc.) to standard RGB JPEG-compatible format
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        elif image.mode != "RGB":
            image = image.convert("RGB")
            
        prompt = """
        You are an expert multi-channel e-commerce seller. Analyze this image and generate optimized listings for four different platforms:
        
        EBAY:
        TITLE: [SEO keyword-rich title under 80 chars]
        PRICE: [Fair market value]
        DESC: [Professional description with specs and condition]
        
        POSHMARK:
        TITLE: [Stylized, boutique-style title]
        PRICE: [Listing price]
        DESC: [Boutique description with style tags and keywords]
        
        FACEBOOK:
        TITLE: [Clear, localized title]
        PRICE: [Local resale price]
        DESC: [Friendly, concise description with pickup/shipping notes]
        
        MERCARI:
        TITLE: [Clean searchable title]
        PRICE: [Competitive price]
        DESC: [Bullet-point details and shipping note]
        """
        
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[image, prompt]
        )
        
        return {"listing": response.text}
    except Exception as e:
        return {"listing": f"Error processing image: {str(e)}"}
