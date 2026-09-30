import os
import stripe
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from supabase import create_client, Client

# Initialize app
app = FastAPI()

# Enable CORS so your frontend can talk to your backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Environment Variables from Render
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

# Initialize the new Gemini Client
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    try:
        with open("index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "<html><body><h1>index.html not found. Make sure it is in your GitHub repo.</h1></body></html>"

@app.post("/api/generate-listing")
async def generate_listing(image: UploadFile = File(...)):
    if not gemini_client:
        raise HTTPException(status_code=500, detail="Gemini API Key missing")
    
    try:
        image_data = await image.read()
        prompt = "Analyze this product image. Provide a JSON response with 'title', 'price' (estimated fair market value), and a detailed 'description' for an online marketplace listing."
        
        # New SDK syntax for generating content with an image
        response = gemini_client.models.generate_content(
            model='gemini-1.5-pro',
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
                    'product_data': {'name': 'SimplyList Pro'},
                    'unit_amount': 999, # $9.99
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=str(request.base_url) + "?success=true",
            cancel_url=str(request.base_url) + "?canceled=true",
            client_reference_id=user_id # Passes the user ID to the webhook
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

    # If payment is successful, upgrade the user in Supabase
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")

        if user_id and user_id != "guest" and supabase:
            try:
                supabase.table("profiles").update({"is_pro": True}).eq("id", user_id).execute()
            except Exception as db_error:
                print("Supabase update error:", db_error)

    return {"status": "success"}
