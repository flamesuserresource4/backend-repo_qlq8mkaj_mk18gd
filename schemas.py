"""
Database Schemas

CuraLink core schemas using Pydantic. Each class name maps to a MongoDB
collection with the lowercase name (e.g., Patient -> "patient").
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal, Any

# Users / Profiles

class Patient(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    conditions: List[str] = Field(default_factory=list)
    city: Optional[str] = None
    country: Optional[str] = None
    global_experts: bool = False
    pub_query: Optional[str] = None

class Researcher(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    specialties: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    orcid: Optional[str] = None
    researchgate: Optional[str] = None
    available_meetings: bool = False

# Knowledge objects

class Publication(BaseModel):
    source_id: str = Field(..., description="External ID, e.g., PubMed ID")
    title: str
    journal: Optional[str] = None
    year: Optional[int] = None
    url: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)

class Trial(BaseModel):
    nct_id: str
    title: str
    status: Optional[str] = None
    conditions: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    url: Optional[str] = None

class Expert(BaseModel):
    name: str
    affiliation: Optional[str] = None
    specialties: List[str] = Field(default_factory=list)
    city: Optional[str] = None
    country: Optional[str] = None
    contact: Optional[str] = None

# Forums

class ForumQuestion(BaseModel):
    author_role: Literal["patient", "researcher"] = "patient"
    author_id: Optional[str] = None
    category: Optional[str] = None
    title: str
    body: str
    tags: List[str] = Field(default_factory=list)
    status: Literal["open", "closed", "answered"] = "open"

class ForumReply(BaseModel):
    question_id: str
    author_role: Literal["patient", "researcher"] = "researcher"
    author_id: Optional[str] = None
    body: str

# Favorites

class Favorite(BaseModel):
    user_id: Optional[str] = None
    user_role: Literal["patient", "researcher"]
    item_type: Literal["publication", "trial", "expert", "collaborator"]
    item: Any
