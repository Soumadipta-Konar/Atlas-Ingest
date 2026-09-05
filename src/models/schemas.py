from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class PricingModel(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"

class Source(BaseModel):
    name: str
    url: str

class StartupData(BaseModel):
    employeeCount: Optional[int] = None

class StartupContent(BaseModel):
    entityName: str
    data: StartupData

class StartupEntity(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = Field(default="STARTUP", Literal=True)
    source: Source
    content: StartupContent
    collectedAt: datetime

class ProductContent(BaseModel):
    startupName: str
    pricingModel: PricingModel

class ProductEntity(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = Field(default="PRODUCT", Literal=True)
    source: Source
    content: ProductContent
    collectedAt: datetime

class ResearchPaperContent(BaseModel):
    title: str
    authors: List[str]
    paper_url: str
    github_url: Optional[str] = None
    github_stars: Optional[int] = None
    published_date: datetime

class ResearchPaperEntity(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = Field(default="RESEARCH_PAPER", Literal=True)
    content: ResearchPaperContent
    collectedAt: datetime

class JobContent(BaseModel):
    company: str
    date: datetime
    is_remote: bool
    role_family: str

class JobEntity(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = Field(default="JOB", Literal=True)
    content: JobContent
    collectedAt: datetime
