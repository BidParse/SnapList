import os
import json
import re
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types

app = FastAPI()

# Initialize Gemini Client using the new google-genai SDK
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

@app.get("/", response_class=HTMLResponse)
async def read_index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>SimpleList Backend Online</h1><p>index.html missing from root directory.</p>"

@app.post("/api/generate-listing")
async def generate_listing(
    image: UploadFile = File(...),
    category: str = Form("General"),
    user_id: str = Form(...)
):
    try:
        image_bytes = await image.read()
        
        prompt = (
            f"Analyze this item for an online marketplace listing under category: {category}. "
            "You must return ONLY a valid JSON object with exactly these keys: "
            "title, pricing, condition, ebay, facebook, poshmark, tags. "
            "Do not include any markdown formatting like ```json or ```, just return the raw JSON string."
        )

        response = gemini_client.models.generate_content(
            model='gemini-3.8-flash',
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=image.content_type or "image/jpeg",
                ),
                prompt
            ]
        )

        raw_text = response.text.strip()
        
        # Bulletproof extraction: find the first '{' and last '}'
        parsed_json = None
        try:
            match = re.search(r\{.*\}", raw_text, re.DOTALL)
            if match:
                json_str = match.group(0)
                parsed_json = json.loads(json_str)
            else:
                parsed_json = json.loads(raw_text)
        except Exception:
            # Fallback wrapper if extraction fails
            parsed_json = {
                "title": f"Marketplace Listing - {category}",
                "pricing": "$25.00",
                "condition": "Good pre-owned condition.",
                "ebay": raw_text,
                "facebook": raw_text,
                "poshmark": raw_text,
                "tags": "#marketplace #resale"
            }

        return JSONResponse(content={"result": parsed_json})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
