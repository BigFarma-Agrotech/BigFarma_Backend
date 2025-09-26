from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from features.auth.schemas import UserResponse
from features.users.schemas import (
    FarmerProfileCreate, FarmerProfileResponse, FarmerProfileUpdate,
    ConsumerProfileCreate, ConsumerProfileResponse, ConsumerProfileUpdate,
    UserProfileResponse
)
from features.auth.models import User, UserCategory
from core.dependencies import get_current_active_user
from features.users.service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/profile", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    user_service = UserService(db)
    user_with_profile = user_service.get_user_profile(current_user.id)
    
    if not user_with_profile:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user_with_profile

@router.post("/farmer-profile", response_model=FarmerProfileResponse)
async def create_farmer_profile(
    profile: FarmerProfileCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.category != UserCategory.FARMER:
        raise HTTPException(status_code=400, detail="User is not a farmer")
    
    user_service = UserService(db)
    
    try:
        farmer_profile = user_service.create_farmer_profile(current_user.id, profile)
        return farmer_profile
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/farmer-profile", response_model=FarmerProfileResponse)
async def get_farmer_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.category != UserCategory.FARMER:
        raise HTTPException(status_code=400, detail="User is not a farmer")
    
    user_service = UserService(db)
    farmer_profile = user_service.get_farmer_profile(current_user.id)
    
    if not farmer_profile:
        raise HTTPException(status_code=404, detail="Farmer profile not found")
    
    return farmer_profile

@router.put("/farmer-profile", response_model=FarmerProfileResponse)
async def update_farmer_profile(
    profile: FarmerProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.category != UserCategory.FARMER:
        raise HTTPException(status_code=400, detail="User is not a farmer")
    
    user_service = UserService(db)
    updated_profile = user_service.update_farmer_profile(current_user.id, profile)
    
    if not updated_profile:
        raise HTTPException(status_code=404, detail="Farmer profile not found")
    
    return updated_profile

@router.delete("/farmer-profile")
async def delete_farmer_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.category != UserCategory.FARMER:
        raise HTTPException(status_code=400, detail="User is not a farmer")
    
    user_service = UserService(db)
    success = user_service.delete_farmer_profile(current_user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Farmer profile not found")
    
    return {"message": "Farmer profile deleted successfully"}

@router.post("/consumer-profile", response_model=ConsumerProfileResponse)
async def create_consumer_profile(
    profile: ConsumerProfileCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.category != UserCategory.CONSUMER:
        raise HTTPException(status_code=400, detail="User is not a consumer")
    
    user_service = UserService(db)
    
    try:
        consumer_profile = user_service.create_consumer_profile(current_user.id, profile)
        return consumer_profile
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/consumer-profile", response_model=ConsumerProfileResponse)
async def get_consumer_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.category != UserCategory.CONSUMER:
        raise HTTPException(status_code=400, detail="User is not a consumer")
    
    user_service = UserService(db)
    consumer_profile = user_service.get_consumer_profile(current_user.id)
    
    if not consumer_profile:
        raise HTTPException(status_code=404, detail="Consumer profile not found")
    
    return ConsumerProfileResponse.from_orm(consumer_profile)

@router.put("/consumer-profile", response_model=ConsumerProfileResponse)
async def update_consumer_profile(
    profile: ConsumerProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.category != UserCategory.CONSUMER:
        raise HTTPException(status_code=400, detail="User is not a consumer")
    
    user_service = UserService(db)
    updated_profile = user_service.update_consumer_profile(current_user.id, profile)
    
    if not updated_profile:
        raise HTTPException(status_code=404, detail="Consumer profile not found")
    
    return updated_profile

@router.delete("/consumer-profile")
async def delete_consumer_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.category != UserCategory.CONSUMER:
        raise HTTPException(status_code=400, detail="User is not a consumer")
    
    user_service = UserService(db)
    success = user_service.delete_consumer_profile(current_user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Consumer profile not found")
    
    return {"message": "Consumer profile deleted successfully"}