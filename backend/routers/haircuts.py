from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import math
import httpx
import os
from dotenv import load_dotenv

from supabase_client import supabase
import schemas
from auth_utils import get_current_active_user

load_dotenv()

router = APIRouter()

# Mock data for development - in production, this would use a real API like Google Places
MOCK_HAIRCUT_SERVICES = [
    {
        "name": "Great Clips",
        "address": "123 Main St",
        "city": "Anytown",
        "state": "CA",
        "zip_code": "12345",
        "phone": "555-123-4567",
        "website": "https://www.greatclips.com",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "rating": 4.5,
        "price_range": "$",
        "hours": "9:00 AM - 9:00 PM"
    },
    {
        "name": "Supercuts",
        "address": "456 Oak Ave",
        "city": "Somewhere",
        "state": "CA",
        "zip_code": "12346",
        "phone": "555-987-6543",
        "website": "https://www.supercuts.com",
        "latitude": 37.7850,
        "longitude": -122.4300,
        "rating": 4.2,
        "price_range": "$",
        "hours": "8:00 AM - 8:00 PM"
    },
    {
        "name": "Sport Clips",
        "address": "789 Pine Blvd",
        "city": "Elsewhere",
        "state": "CA",
        "zip_code": "12347",
        "phone": "555-456-7890",
        "website": "https://www.sportclips.com",
        "latitude": 37.7900,
        "longitude": -122.4100,
        "rating": 4.7,
        "price_range": "$$",
        "hours": "10:00 AM - 7:00 PM"
    }
]

# Helper function to calculate distance between two points using Haversine formula
def calculate_distance(lat1, lon1, lat2, lon2):
    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Haversine formula
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    # Radius of Earth in kilometers
    radius = 6371
    
    # Calculate the distance
    distance = radius * c
    return distance

@router.get("/haircuts", response_model=List[schemas.HaircutService])
def get_haircuts():
    try:
        response = supabase.table("haircut_services").select("*").execute()
        haircuts = response.data if response.data else []
        
        # If no haircuts in database, seed with mock data
        if not haircuts:
            supabase.table("haircut_services").insert(MOCK_HAIRCUT_SERVICES).execute()
            response = supabase.table("haircut_services").select("*").execute()
            haircuts = response.data if response.data else []
        
        return haircuts
    except Exception:
        return []

@router.get("/haircuts/{haircut_id}", response_model=schemas.HaircutService)
def get_haircut(haircut_id: int):
    try:
        response = supabase.table("haircut_services").select("*").eq("id", haircut_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Haircut service not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Haircut service not found")

@router.post("/haircuts/search", response_model=List[schemas.HaircutService])
def search_haircuts(search: schemas.HaircutSearch):
    try:
        # Get all haircut services
        response = supabase.table("haircut_services").select("*").execute()
        haircuts = response.data if response.data else []
        
        # Filter by distance
        nearby_haircuts = []
        for haircut in haircuts:
            distance = calculate_distance(
                search.latitude, 
                search.longitude, 
                haircut["latitude"], 
                haircut["longitude"]
            )
            if distance <= search.radius:
                nearby_haircuts.append(haircut)
        
        # Sort by distance (closest first)
        nearby_haircuts.sort(
            key=lambda x: calculate_distance(
                search.latitude, 
                search.longitude, 
                x["latitude"], 
                x["longitude"]
            )
        )
        
        return nearby_haircuts
    except Exception:
        return []

@router.post("/haircuts", response_model=schemas.HaircutService)
def create_haircut(
    haircut: schemas.HaircutServiceCreate, 
    current_user: dict = Depends(get_current_active_user)
):
    try:
        haircut_data = haircut.dict()
        response = supabase.table("haircut_services").insert(haircut_data).execute()
        if response.data:
            return response.data[0]
        raise HTTPException(status_code=500, detail="Failed to create haircut service")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create haircut service: {str(e)}")
