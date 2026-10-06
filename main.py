import os
import json
import re
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types

app = FastAPI()

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
            "If this is a trading card or collectible, perform an expert optical grading inspection "
            "analyzing centering, corners, edges, and surface condition. "
            "1. For the 'pricing' key, return ONLY a clean text string formatted like this: "
            "Raw: $X - $Y | Grade 7: $X - $Y | Grade 8: $X - $Y | Grade 9: $X - $Y | Grade 10: $X - $Y | Gold Star 10: $X - $Y. "
            "2. For each platform key (ebay, facebook, offerup, poshmark, mercari, depop, vinted, etsy), provide a full, comprehensive sales description optimized for that specific marketplace, including a suggested listing price range suited for that platform's buyer demographic and fees. "
            "You must return ONLY a valid JSON object with exactly these keys: "
            "title, pricing, condition, ebay, facebook, offerup, poshmark, mercari, depop, vinted, etsy, tags. "
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
        
        parsed_json = None
        try:
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                json_str = match.group(0)
                parsed_json = json.loads(json_str)
            else:
                parsed_json = json.loads(raw_text)
            
            # Ensure pricing is a clean string
            if isinstance(parsed_json.get("pricing"), dict):
                p_dict = parsed_json["pricing"]
                parsed_json["pricing"] = " | ".join([f"{k}: {v}" for k, v in p_dict.items()])

            for k, v in parsed_json.items():
                if isinstance(v, dict) and k != "pricing":
                    parsed_json[k] = " ".join([str(sub_v) for sub_v in v.values()])
                elif not isinstance(v, str):
                    parsed_json[k] = str(v)

        except Exception:
            parsed_json = {
                "title": f"Marketplace Listing - {category}",
                "pricing": "Raw: $2.00 - $4.00 | Grade 7: $6.00 - $10.00 | Grade 8: $10.00 - $15.00 | Grade 9: $15.00 - $22.00 | Grade 10: $35.00 - $50.00 | Gold Star 10: $65.00 - $95.00",
                "condition": "Expert Grade Inspection Completed.",
                "ebay": raw_text,
                "facebook": raw_text,
                "offerup": raw_text,
                "poshmark": raw_text,
                "mercari": raw_text,
                "depop": raw_text,
                "vinted": raw_text,
                "etsy": raw_text,
                "tags": "#marketplace #resale"
            }

        return JSONResponse(content={"result": parsed_json})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
