from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from features.users.models import FarmerProfile, ConsumerProfile, FarmType, CropPreference
from features.users.schemas import FarmerProfileCreate, FarmerProfileUpdate, ConsumerProfileCreate, ConsumerProfileUpdate
from features.auth.models import User, UserCategory
from repositories.user_repository import UserRepository

class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def get_user_profile(self, user_id: int) -> Optional[User]:
        """Get user with profile information."""
        return self.user_repo.get_with_profile(user_id)

    def create_farmer_profile(self, user_id: int, profile_data: FarmerProfileCreate) -> FarmerProfile:
        """Create a farmer profile for a user and update user contact info if needed."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        if user.category != UserCategory.FARMER:
            raise ValueError("User is not a farmer")
        
        existing_profile = self.db.query(FarmerProfile).filter(FarmerProfile.user_id == user_id).first()
        if existing_profile:
            raise ValueError("Farmer profile already exists")
        
        profile_dict = profile_data.dict(exclude_unset=True)
        update_user_data = {}
        
        email = profile_dict.pop('email', None)
        phone = profile_dict.pop('phone', None)
        
        if email and not user.email:
            update_user_data['email'] = email
        
        if phone and not user.phone_number:
            update_user_data['phone_number'] = phone
        
        if update_user_data:
            for key, value in update_user_data.items():
                setattr(user, key, value)
        
        farmer_profile = FarmerProfile(**profile_dict, user_id=user_id)
        self.db.add(farmer_profile)
        
        user.profile_setup = True
        
        self.db.commit()
        self.db.refresh(farmer_profile)
        
        return farmer_profile

    def update_farmer_profile(self, user_id: int, profile_data: FarmerProfileUpdate) -> Optional[FarmerProfile]:
        """Update a farmer profile."""
        farmer_profile = self.db.query(FarmerProfile).filter(FarmerProfile.user_id == user_id).first()
        if not farmer_profile:
            return None
        
        update_data = profile_data.dict(exclude_unset=True)
        
        email = update_data.pop('email', None)
        phone = update_data.pop('phone', None)
        
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            if email and email != user.email:
                user.email = email
            if phone and phone != user.phone_number:
                user.phone_number = phone
        
        for field, value in update_data.items():
            setattr(farmer_profile, field, value)
        
        self.db.commit()
        self.db.refresh(farmer_profile)
        return farmer_profile

    def get_farmer_profile(self, user_id: int) -> Optional[FarmerProfile]:
        """Get farmer profile by user ID."""
        return self.db.query(FarmerProfile).filter(FarmerProfile.user_id == user_id).first()

    def verify_farmer_profile(self, user_id: int) -> bool:
        """Verify a farmer profile."""
        farmer_profile = self.db.query(FarmerProfile).filter(FarmerProfile.user_id == user_id).first()
        if not farmer_profile:
            return False
        
        farmer_profile.is_verified = True
        farmer_profile.verification_date = func.now()
        
        user = self.db.query(User).filter(User.id == user_id).first()
        if user and not user.is_verified:
            user.is_verified = True
        
        self.db.commit()
        return True

    def create_consumer_profile(self, user_id: int, profile_data: ConsumerProfileCreate) -> ConsumerProfile:
        """Create a consumer profile for a user and update user contact info if needed."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        if user.category != UserCategory.CONSUMER:
            raise ValueError("User is not a consumer")
        
        existing_profile = self.db.query(ConsumerProfile).filter(ConsumerProfile.user_id == user_id).first()
        if existing_profile:
            raise ValueError("Consumer profile already exists")
        
        profile_dict = profile_data.dict(exclude_unset=True)
        update_user_data = {}
        
        email = profile_dict.pop('email', None)
        phone = profile_dict.pop('phone', None)
        
        if email and not user.email:
            update_user_data['email'] = email
        
        if phone and not user.phone_number:
            update_user_data['phone_number'] = phone
        
        if update_user_data:
            for key, value in update_user_data.items():
                setattr(user, key, value)
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'address']
        for field in required_fields:
            if field not in profile_dict or not profile_dict[field]:
                raise ValueError(f"Field '{field}' is required")
        
        # Convert crop preferences
        if 'crop_preferences' in profile_dict and profile_dict['crop_preferences']:
            profile_dict['crop_preferences'] = ','.join(profile_dict['crop_preferences'])
        else:
            profile_dict['crop_preferences'] = None
        
        consumer_profile = ConsumerProfile(**profile_dict, user_id=user_id)
        self.db.add(consumer_profile)
        
        user.profile_setup = True
        
        self.db.commit()
        self.db.refresh(consumer_profile)
        
        return consumer_profile

    def update_consumer_profile(self, user_id: int, profile_data: ConsumerProfileUpdate) -> Optional[ConsumerProfile]:
        """Update a consumer profile."""
        consumer_profile = self.db.query(ConsumerProfile).filter(ConsumerProfile.user_id == user_id).first()
        if not consumer_profile:
            return None
        
        update_data = profile_data.dict(exclude_unset=True)
        
        email = update_data.pop('email', None)
        phone = update_data.pop('phone', None)
        
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            if email and email != user.email:
                user.email = email
            if phone and phone != user.phone_number:
                user.phone_number = phone
        
        if 'crop_preferences' in update_data and update_data['crop_preferences']:
            update_data['crop_preferences'] = ','.join(update_data['crop_preferences'])
        
        for field, value in update_data.items():
            setattr(consumer_profile, field, value)
        
        self.db.commit()
        self.db.refresh(consumer_profile)
        return consumer_profile

    def get_consumer_profile(self, user_id: int) -> Optional[ConsumerProfile]:
        """Get consumer profile by user ID."""
        return self.db.query(ConsumerProfile).filter(ConsumerProfile.user_id == user_id).first()

    def delete_farmer_profile(self, user_id: int) -> bool:
        """Delete farmer profile."""
        farmer_profile = self.db.query(FarmerProfile).filter(FarmerProfile.user_id == user_id).first()
        if farmer_profile:
            self.db.delete(farmer_profile)
            self.db.commit()
            return True
        return False

    def delete_consumer_profile(self, user_id: int) -> bool:
        """Delete consumer profile."""
        consumer_profile = self.db.query(ConsumerProfile).filter(ConsumerProfile.user_id == user_id).first()
        if consumer_profile:
            self.db.delete(consumer_profile)
            self.db.commit()
            return True
        return False