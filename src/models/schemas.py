from datetime import datetime
from enum import Enum
from typing import List, Optional, Literal
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
    recordType: Literal["STARTUP"] = "STARTUP"
    source: Source
    content: StartupContent
    collectedAt: datetime

class ProductContent(BaseModel):
    startupName: str
    pricingModel: PricingModel

class EcommerceProductContent(BaseModel):
    productName: str
    price: Optional[str] = None
    brand: Optional[str] = None
    rating: Optional[str] = None

class ProductEntity(BaseModel):
    schemaVersion: str = "1.0"
    recordType: Literal["PRODUCT"] = "PRODUCT"
    source: Source
    content: ProductContent
    collectedAt: datetime

class EcommerceProductEntity(BaseModel):
    schemaVersion: str = "1.0"
    recordType: Literal["ECOMMERCE_PRODUCT"] = "ECOMMERCE_PRODUCT"
    source: Source
    content: EcommerceProductContent
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
    recordType: Literal["RESEARCH_PAPER"] = "RESEARCH_PAPER"
    content: ResearchPaperContent

class NewsContent(BaseModel):
    title: str
    url: str
    published_date: datetime
    summary: Optional[str] = None

class NewsEntity(BaseModel):
    schemaVersion: str = "1.0"
    recordType: Literal["NEWS"] = "NEWS"
    source: Source
    content: NewsContent
    collectedAt: datetime

class JobContent(BaseModel):
    company: Optional[str] = None
    date: datetime
    is_remote: bool = False
    role_family: str = "Engineering"

class JobEntity(BaseModel):
    schemaVersion: str = "1.0"
    recordType: Literal["JOB"] = "JOB"
    content: JobContent
