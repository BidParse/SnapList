import os
import stripe
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
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
async def generate_listing(image: UploadFile = File(...)):
    if not gemini_client:
        raise HTTPException(status_code=500, detail="Gemini API Key missing")
    
    try:
        image_data = await image.read()
        
        # The Elite Cross-Listing Super Prompt
        prompt = """You are an elite e-commerce copywriter, appraiser, and cross-listing expert. Analyze this product image and generate a master listing package designed to maximize sales across multiple platforms.

        Format the output clearly with the following sections and spacing so the user can easily copy and paste what they need:

        🏆 MASTER TITLE
        (Provide a highly-searchable, 80-character max SEO title including brand, model, color, and size if applicable)

        💰 APPRAISAL & PRICING STRATEGY
        • Quick Sale Price (Priced to move in 24-48 hours): $...
        • Fair Market Value (Average current comp): $...
        • Max Profit/Retail (If in pristine/new condition): $...

        📦 PLATFORM-SPECIFIC DESCRIPTIONS
        
        1️⃣ eBay / Mercari (The Professional Listing)
        Write a detailed, bulleted description focusing on exact item specifics, condition grading, authenticity markers, and professional shipping/return policies.
        
        2️⃣ Facebook Marketplace / OfferUp (The Local Listing)
        Write a conversational, urgent, and friendly description. Include placeholders for [City/Zip Code] local pickup, cash/digital payment preferences, and a "first come, first served" call to action.
        
        3️⃣ Poshmark / Depop (The Boutique Listing)
        Write a trendy, stylish description utilizing relevant emojis. Focus on the aesthetic, how to style it, and include 5-10 highly relevant aesthetic hashtags at the bottom.

        ✨ CONDITION & FLAW CHECK
        (List the apparent condition based on the photo. Note any visible flaws, scuffs, or missing parts the seller should double-check before posting.)

        🔍 MASTER SEO TAGS
        (Provide a comma-separated list of 15 high-volume search keywords for backend tags)
        """
        
        response = gemini_client.models.generate_content(
            model='gemini-3.8-flash',
            contents=[
                prompt,
                types.Part.from_bytes(data=image_data, mime_type=image.content_type)
            ]
        )
        
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
