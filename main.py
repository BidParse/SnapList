import os
import stripe
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from supabase import create_client, Client

# Initialize app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Services
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    try:
        with open("index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "<html><body><h1>index.html not found.</h1></body></html>"

@app.get("/logo.png")
async def serve_logo():
    if os.path.exists("logo.png"):
        return FileResponse("logo.png")
    return HTMLResponse(status_code=404, content="Logo not found")

@app.post("/api/generate-listing")
async def generate_listing(
    image: UploadFile = File(...), 
    category: str = Form("General"),
    user_id: str = Form(None)
):
    if not gemini_client:
        raise HTTPException(status_code=500, detail="Gemini API Key missing")
        
    if not user_id or not supabase:
        return JSONResponse(content={"error": "Please log in to generate listings."}, status_code=401)
        
    # Paywall Logic
    try:
        profile_response = supabase.table("profiles").select("is_pro, generation_count").eq("id", user_id).execute()
        if not profile_response.data:
            return JSONResponse(content={"error": "User profile not found. Please log out and back in."}, status_code=404)
        
        profile = profile_response.data[0]
        is_pro = profile.get("is_pro", False)
        generation_count = profile.get("generation_count", 0)
        
        if not is_pro and generation_count >= 3:
            return JSONResponse(
                content={"error": "FREE TRIAL ENDED! You have used your 3 free listings. Click 'UPGRADE - $9.99' above for unlimited generations!"}
            )
    except Exception as e:
        print("Database error:", e)
        return JSONResponse(content={"error": "Database connection error."}, status_code=500)
    
    try:
        image_data = await image.read()
        
        category_instructions = {
            "Sneakers & Shoes": "Focus on colorway, size tags, visible wear on outsoles, authenticity indicators, and box condition.",
            "Trading Cards & Collectibles": "Focus on centering, corner sharpness, edge wear, surface condition, and grading value.",
            "Electronics & Computers": "Focus on identifying make, model, specs (RAM, storage, processor), ports, and physical condition.",
            "Vehicles & Auto Parts": "Identify the vehicle part or model. Focus on compatibility, visible wear, OEM markers.",
            "Clothing & Apparel": "Focus on brand, aesthetic style, visible size, material quality, and measurements.",
            "General": "Provide a comprehensive breakdown of the item's visual condition and standard features."
        }
        
        niche_focus = category_instructions.get(category, category_instructions["General"])
        
        # NEW JSON PROMPT
        prompt = f"""You are an elite e-commerce copywriter.
        Category: {category}. 
        CRITICAL NICHE INSTRUCTION: {niche_focus}

        Analyze this product image and generate a master listing package. 
        YOU MUST RETURN YOUR RESPONSE AS A VALID, RAW JSON OBJECT. Do not include markdown formatting like ```json. Just return the JSON starting with {{ and ending with }}.
        
        Use exactly these keys:
        "title": "A highly-searchable, 80-character max SEO title",
        "pricing": "Quick Sale: $... | Fair Market: $... | Max Profit: $...",
        "ebay": "A detailed, bulleted description focusing on exact item specifics, condition grading, and professionalism. DO NOT INCLUDE THE TITLE HERE.",
        "facebook": "A conversational, urgent, and friendly description with local pickup placeholders. DO NOT INCLUDE THE TITLE HERE.",
        "poshmark": "A trendy, stylish description utilizing relevant emojis and hashtags. DO NOT INCLUDE THE TITLE HERE.",
        "condition": "A strict assessment of visible condition and flaws.",
        "tags": "A comma-separated list of 15 high-volume search keywords."
        """
        
        response = gemini_client.models.generate_content(
            model='gemini-3.8-flash',
            contents=[
                prompt,
                types.Part.from_bytes(data=image_data, mime_type=image.content_type)
            ]
        )
        
        if not is_pro:
            supabase.table("profiles").update({"generation_count": generation_count + 1}).eq("id", user_id).execute()
        
        return JSONResponse(content={"result": response.text})
        
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/api/checkout")
async def create_checkout_session(request: Request):
    try:
        data = await request.json()
        user_id = data.get("user_id", "guest")

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': 'SimpleList Pro'},
                    'unit_amount': 999,
                },
                'quantity': 1,
            }],
            mode='payment',
            allow_promotion_codes=True,
            success_url=str(request.base_url) + "?success=true",
            cancel_url=str(request.base_url) + "?canceled=true",
            client_reference_id=user_id
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")

        if user_id and user_id != "guest" and supabase:
            try:
                supabase.table("profiles").update({"is_pro": True}).eq("id", user_id).execute()
            except Exception as db_error:
                print("Supabase update error:", db_error)

    return {"status": "success"}
