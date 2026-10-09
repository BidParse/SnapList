import os
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from supabase import create_client, Client

app = FastAPI(title="SimpleList AI Engine", version="1.0.0")

# Initialize Supabase Client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") # Backend privileged key for multi-platform syncs

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class ListingCreate(BaseModel):
    user_id: str
    title: str
    description: str
    price: float
    cost_of_goods: float
    category: str
    condition_state: str
    images: list[str]

@app.post("/api/listings/create")
async def create_listing(listing: ListingCreate):
    try:
        response = supabase.table("listings").insert({
            "user_id": listing.user_id,
            "title": listing.title,
            "description": listing.description,
            "price": listing.price,
            "cost_of_goods": listing.cost_of_goods,
            "category": listing.category,
            "condition_state": listing.condition_state,
            "images": listing.images,
            "status": "active",
            "platforms_synced": {"ebay": "pending", "poshmark": "pending", "mercari": "pending"}
        }).execute()
        
        return {"success": True, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
