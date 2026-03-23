"""
Pydantic models for configuration validation.
Requirements: 17.1, 17.3, 19.1
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OPENROUTER = "openrouter"
    MINIMAX = "minimax"


class DatabaseConfig(BaseModel):
    """Supabase/Postgres database configuration."""
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_anon_key: str = Field(..., description="Supabase anonymous key")
    supabase_service_role_key: str = Field(..., description="Supabase service role key")
    database_url: str = Field(..., description="PostgreSQL connection URL")


class LLMConfig(BaseModel):
    """LLM provider configuration."""
    provider: LLMProvider = Field(default=LLMProvider.MINIMAX, description="Default LLM provider")
    model: str = Field(default="MiniMax-M2.1", description="Default model name")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    google_api_key: Optional[str] = Field(default=None, description="Google/Gemini API key")
    openrouter_api_key: Optional[str] = Field(default=None, description="OpenRouter API key")
    minimax_api_key: Optional[str] = Field(default=None, description="MiniMax API key")
    
    @field_validator('provider', mode='before')
    @classmethod
    def validate_provider(cls, v):
        if isinstance(v, str):
            return LLMProvider(v.lower())
        return v


class ApifyConfig(BaseModel):
    """Apify scraping configuration."""
    api_token: str = Field(..., description="Apify API token")
    max_concurrent_runs: int = Field(default=5, ge=1, le=20)
    default_timeout_secs: int = Field(default=300, ge=60, le=3600)
    memory_mbytes: int = Field(default=1024, ge=128, le=8192)


class SteelConfig(BaseModel):
    """Steel.dev browser automation configuration."""
    api_key: str = Field(..., description="Steel.dev API key")
    max_concurrent_sessions: int = Field(default=3, ge=1, le=10)
    default_timeout_ms: int = Field(default=30000, ge=5000, le=120000)


class PineconeConfig(BaseModel):
    """Pinecone vector store configuration."""
    api_key: str = Field(..., description="Pinecone API key")
    environment: str = Field(default="us-east-1", description="Pinecone environment/region")
    index_name: str = Field(default="zrai-playbooks", description="Pinecone index name")


class S3Config(BaseModel):
    """S3-compatible object storage configuration."""
    access_key_id: Optional[str] = Field(default=None)
    secret_access_key: Optional[str] = Field(default=None)
    region: str = Field(default="us-east-1")
    bucket_name: str = Field(default="zrai-artifacts")
    use_supabase_storage: bool = Field(default=True)


class EmailConfig(BaseModel):
    """Email/SMTP configuration for outreach."""
    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    smtp_user: Optional[str] = Field(default=None)
    smtp_password: Optional[str] = Field(default=None)
    from_email: Optional[str] = Field(default=None)


class BudgetConfig(BaseModel):
    """Daily budget limits for cost control.
    Requirements: 23.1
    """
    daily_llm_token_limit: int = Field(default=1_000_000, ge=0)
    daily_browser_session_limit: int = Field(default=100, ge=0)
    daily_scraper_run_limit: int = Field(default=50, ge=0)


class CoolDownConfig(BaseModel):
    """Cool-down period configuration."""
    after_bounce_days: int = Field(default=7, ge=1)
    after_spam_complaint_days: int = Field(default=30, ge=7)
    after_angry_reply_days: int = Field(default=14, ge=1)
    after_no_response_days: int = Field(default=7, ge=1)


class RateLimitConfig(BaseModel):
    """Rate limiting configuration.
    Requirements: 12.1
    """
    per_domain_email_per_day: int = Field(default=5, ge=1, le=50)
    per_domain_dm_per_day: int = Field(default=2, ge=1, le=20)
    email_per_hour: int = Field(default=50, ge=1, le=500)
    email_per_day: int = Field(default=200, ge=1, le=2000)
    dm_per_hour: int = Field(default=20, ge=1, le=200)
    dm_per_day: int = Field(default=50, ge=1, le=500)
    cool_downs: CoolDownConfig = Field(default_factory=CoolDownConfig)


class KillSwitchConfig(BaseModel):
    """Kill switch configuration for emergency stops.
    Requirements: 1.6
    """
    global_kill: bool = Field(default=False)
    discovery_kill: bool = Field(default=False)
    audit_kill: bool = Field(default=False)
    outreach_kill: bool = Field(default=False)


class SystemConfig(BaseModel):
    """System-level configuration."""
    environment: str = Field(default="development")
    max_concurrent_leads: int = Field(default=10, ge=1, le=100)
    log_level: str = Field(default="INFO")


class ScoringWeights(BaseModel):
    """Weighted scoring configuration per niche.
    Requirements: 7.1, 7.2
    """
    ad_activity: float = Field(default=0.20, ge=0, le=1)
    intent: float = Field(default=0.25, ge=0, le=1)
    leak: float = Field(default=0.30, ge=0, le=1)
    reactivation: float = Field(default=0.10, ge=0, le=1)
    contact_quality: float = Field(default=0.10, ge=0, le=1)
    business_size: float = Field(default=0.05, ge=0, le=1)
    
    @field_validator('business_size', mode='after')
    @classmethod
    def validate_weights_sum(cls, v, info):
        """Ensure weights sum to approximately 1.0"""
        values = info.data
        total = (
            values.get('ad_activity', 0) +
            values.get('intent', 0) +
            values.get('leak', 0) +
            values.get('reactivation', 0) +
            values.get('contact_quality', 0) +
            v
        )
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")
        return v


class NicheConfig(BaseModel):
    """Configuration for a specific niche."""
    name: str
    keywords: List[str] = Field(default_factory=list)
    geo_filters: List[str] = Field(default_factory=list)
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    min_score_threshold: int = Field(default=60, ge=0, le=100)
    tier_a_threshold: int = Field(default=80, ge=0, le=100)
    tier_b_threshold: int = Field(default=60, ge=0, le=100)


class AppConfig(BaseModel):
    """Main application configuration.
    Requirements: 17.1, 17.2, 17.3
    """
    database: DatabaseConfig
    llm: LLMConfig
    apify: ApifyConfig
    steel: SteelConfig
    pinecone: PineconeConfig
    s3: S3Config = Field(default_factory=S3Config)
    email: EmailConfig = Field(default_factory=EmailConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    rate_limits: RateLimitConfig = Field(default_factory=RateLimitConfig)
    kill_switches: KillSwitchConfig = Field(default_factory=KillSwitchConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    niches: Dict[str, NicheConfig] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True
