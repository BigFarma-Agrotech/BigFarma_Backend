from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from app.services.auth import get_db
from app.database import User, Profile, FarmerProfile, ConsumerProfile, UserCategory
from app.schemas.accounts import (
    FarmerProfileCreate, 
    ConsumerProfileCreate, 
    ProfileSetupResponse,
    FarmerProfileResponse,
    ConsumerProfileResponse
)
from app.api.v1.dependencies import get_current_user
from app.services.file_service import upload_file

router = APIRouter()


@router.post("/farmer/setup", response_model=ProfileSetupResponse)
async def setup_farmer_profile(
    first_name: str = Form(...),
    last_name: str = Form(...),
    address: str = Form(...),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    valid_id: UploadFile = File(...),
    farm_type: str = Form(...),
    farm_image: Optional[UploadFile] = File(None),
    farm_location: str = Form(...),
    farm_size: Optional[str] = Form(None),
    years_experience: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.user_category is None:
        current_user.user_category = UserCategory.FARMER
        db.add(current_user)
    if current_user.user_category != UserCategory.FARMER:
        raise HTTPException(status_code=400, detail="User must be a farmer to setup farmer profile")
    
    # Check if profile already exists
    existing_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == current_user.id).first()
    if existing_profile:
        raise HTTPException(status_code=400, detail="Farmer profile already exists")
    
    # Validate farm type
    valid_farm_types = ["crop", "livestock", "mixed"]
    if farm_type.lower() not in valid_farm_types:
        raise HTTPException(status_code=400, detail=f"Farm type must be one of: {', '.join(valid_farm_types)}")
    
    # Upload valid ID document
    valid_id_url = await upload_file(valid_id, "valid_ids")
    
    # Upload farm image if provided
    farm_image_url = None
    if farm_image:
        farm_image_url = await upload_file(farm_image, "farm_images")
    
    # Create base profile
    profile = Profile(
        user_id=current_user.id,
        first_name=first_name,
        last_name=last_name,
        address=address,
        phone=phone or current_user.phone,
        email=email or current_user.email,
        avatar_url=None,  # Will be handled separately
        user_category=current_user.user_category
    )
    
    # Create farmer profile
    farmer_profile = FarmerProfile(
        user_id=current_user.id,
        valid_id_url=valid_id_url,
        farm_type=farm_type.lower(),
        farm_image_url=farm_image_url,
        farm_location=farm_location,
        farm_size=farm_size,
        years_experience=years_experience
    )
    
    db.add(profile)
    db.add(farmer_profile)
    db.commit()
    db.refresh(profile)
    db.refresh(farmer_profile)
    
    return ProfileSetupResponse(
        message="Thank you! Your profile has been submitted for verification. We'll notify you once you're verified.",
        user_id=current_user.id,
        profile_type="farmer",
        next_steps="Your profile is pending verification. You can upload a profile picture and update your information while waiting."
    )


@router.post("/consumer/setup", response_model=ProfileSetupResponse)
async def setup_consumer_profile(
    first_name: str = Form(...),
    last_name: str = Form(...),
    address: str = Form(...),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    product_preferences: str = Form(...),  # JSON string of product preferences
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.user_category is None:
        current_user.user_category = UserCategory.CONSUMER
        db.add(current_user)
    if current_user.user_category != UserCategory.CONSUMER:
        raise HTTPException(status_code=400, detail="User must be a consumer to setup consumer profile")
    
    # Check if profile already exists
    existing_profile = db.query(ConsumerProfile).filter(ConsumerProfile.user_id == current_user.id).first()
    if existing_profile:
        raise HTTPException(status_code=400, detail="Consumer profile already exists")
    
    # Validate product preferences
    try:
        preferences = json.loads(product_preferences)
        if not isinstance(preferences, list):
            raise ValueError("Product preferences must be a list")
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid product preferences format")
    
    # Create base profile
    profile = Profile(
        user_id=current_user.id,
        first_name=first_name,
        last_name=last_name,
        address=address,
        phone=phone or current_user.phone,
        email=email or current_user.email,
        avatar_url=None,
        user_category=current_user.user_category
    )
    
    # Create consumer profile
    consumer_profile = ConsumerProfile(
        user_id=current_user.id,
        product_preferences=product_preferences
    )
    
    db.add(profile)
    db.add(consumer_profile)
    db.commit()
    db.refresh(profile)
    db.refresh(consumer_profile)
    
    return ProfileSetupResponse(
        message="Account setup complete! Welcome to BigFarma.",
        user_id=current_user.id,
        profile_type="consumer",
        next_steps="You can now browse products, set preferences, and start shopping!"
    )


@router.post("/upload-avatar")
async def upload_profile_picture(
    avatar: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload profile picture for any user type.
    """
    # Upload avatar file
    avatar_url = await upload_file(avatar, "avatars")
    
    # Update profile with avatar URL
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile:
        profile.avatar_url = avatar_url
        db.commit()
        db.refresh(profile)
    
    return {"message": "Profile picture uploaded successfully", "avatar_url": avatar_url}


@router.get("/farmer", response_model=FarmerProfileResponse)
async def get_farmer_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get farmer profile information.
    """
    if current_user.user_category != UserCategory.FARMER:
        raise HTTPException(status_code=400, detail="User must be a farmer")
    
    profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Farmer profile not found")
    
    return profile


@router.get("/consumer", response_model=ConsumerProfileResponse)
async def get_consumer_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get consumer profile information.
    """
    if current_user.user_category != UserCategory.CONSUMER:
        raise HTTPException(status_code=400, detail="User must be a consumer")
    
    profile = db.query(ConsumerProfile).filter(ConsumerProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Consumer profile not found")
    
    return profile


@router.put("/farmer/update")
async def update_farmer_profile(
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    farm_type: Optional[str] = Form(None),
    farm_location: Optional[str] = Form(None),
    farm_size: Optional[str] = Form(None),
    years_experience: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update farmer profile information.
    """
    if current_user.user_category != UserCategory.FARMER:
        raise HTTPException(status_code=400, detail="User must be a farmer")
    
    # Update base profile
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile:
        if first_name:
            profile.first_name = first_name
        if last_name:
            profile.last_name = last_name
        if address:
            profile.address = address
        if phone:
            profile.phone = phone
        if email:
            profile.email = email
    
    # Update farmer profile
    farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == current_user.id).first()
    if farmer_profile:
        if farm_type:
            valid_farm_types = ["crop", "livestock", "mixed"]
            if farm_type.lower() not in valid_farm_types:
                raise HTTPException(status_code=400, detail=f"Farm type must be one of: {', '.join(valid_farm_types)}")
            farmer_profile.farm_type = farm_type.lower()
        if farm_location:
            farmer_profile.farm_location = farm_location
        if farm_size:
            farmer_profile.farm_size = farm_size
        if years_experience is not None:
            farmer_profile.years_experience = years_experience
    
    db.commit()
    
    return {"message": "Profile updated successfully"}


@router.put("/consumer/update")
async def update_consumer_profile(
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    product_preferences: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update consumer profile information.
    """
    if current_user.user_category != UserCategory.CONSUMER:
        raise HTTPException(status_code=400, detail="User must be a consumer")
    
    # Update base profile
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile:
        if first_name:
            profile.first_name = first_name
        if last_name:
            profile.last_name = last_name
        if address:
            profile.address = address
        if phone:
            profile.phone = phone
        if email:
            profile.email = email
    
    # Update consumer profile
    consumer_profile = db.query(ConsumerProfile).filter(ConsumerProfile.user_id == current_user.id).first()
    if consumer_profile and product_preferences:
        try:
            preferences = json.loads(product_preferences)
            if not isinstance(preferences, list):
                raise ValueError("Product preferences must be a list")
            consumer_profile.product_preferences = product_preferences
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid product preferences format")
    
    db.commit()
    
    return {"message": "Profile updated successfully"} 