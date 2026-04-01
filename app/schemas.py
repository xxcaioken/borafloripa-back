from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List, Optional


class TagOut(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True


class VenueOut(BaseModel):
    id: int
    owner_id: Optional[int] = None
    name: str
    city: str
    lat: float
    lng: float
    address: Optional[str]
    instagram: Optional[str]
    whatsapp: Optional[str]
    hours: Optional[str]
    category: Optional[str] = 'bar'
    is_new: bool
    logo_url: Optional[str] = None
    wheelchair: bool
    hearing_loop: bool
    visual_aid: bool
    adapted_wc: bool
    parking: bool
    checkin_count: int = 0
    class Config:
        from_attributes = True


class EventOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    date: datetime
    vibe_status: str
    is_featured: bool
    category: str
    is_temporary: bool
    organizers: Optional[str]
    cover_url: Optional[str] = None
    price_info: Optional[str] = None
    view_count: int = 0
    venue: VenueOut
    tags: List[TagOut]
    class Config:
        from_attributes = True


class EventCreate(BaseModel):
    venue_id: int
    title: str
    description: Optional[str] = None
    date: datetime
    vibe_status: str = "Normal"
    is_featured: bool = False
    category: str = "bar"
    is_temporary: bool = False
    organizers: Optional[str] = None
    price_info: Optional[str] = None
    tag_ids: List[int] = []


class VenueCreate(BaseModel):
    name: str
    city: str = "Florianópolis"
    lat: float
    lng: float
    address: Optional[str] = None
    instagram: Optional[str] = None
    whatsapp: Optional[str] = None
    hours: Optional[str] = None
    wheelchair: bool = False
    hearing_loop: bool = False
    visual_aid: bool = False
    adapted_wc: bool = False
    parking: bool = False


class EventAnalytics(BaseModel):
    event_id: int
    title: str
    date: datetime
    view_count: int
    bora_count: int
    class Config:
        from_attributes = True


class PartnerStats(BaseModel):
    total_events: int
    featured_events: int
    venues: List[VenueOut]


# Auth
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    pref_music: Optional[str] = None
    pref_vibes: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    pref_music: Optional[str]
    pref_vibes: Optional[str]
    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


class BoraReactionOut(BaseModel):
    event_id: int
    count: int
    reacted: bool


class CommunityOut(BaseModel):
    id: int
    tag_name: str
    name: str
    description: Optional[str]
    discount_code: Optional[str]
    member_count: int
    is_member: bool = False
    class Config:
        from_attributes = True


class VibeTag(BaseModel):
    tag_name: str
    count: int
    voted: bool = False


class CheckinCreate(BaseModel):
    venue_id: int
    session_id: str = ""


class HotVenue(BaseModel):
    venue_id: int
    venue_name: str
    checkin_count: int
