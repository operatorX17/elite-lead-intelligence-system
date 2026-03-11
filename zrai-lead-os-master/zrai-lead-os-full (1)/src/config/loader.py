"""
Configuration loader with environment variable and YAML support.
Requirements: 17.1, 17.2, 17.3, 19.1, 19.3
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading

from .models import (
    AppConfig,
    DatabaseConfig,
    LLMConfig,
    LLMProvider,
    ApifyConfig,
    SteelConfig,
    PineconeConfig,
    S3Config,
    EmailConfig,
    BudgetConfig,
    RateLimitConfig,
    KillSwitchConfig,
    SystemConfig,
    NicheConfig,
    ScoringWeights,
)


def load_env_file(env_path: str = ".env") -> None:
    """Load environment variables from .env file."""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()


def get_env(key: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """Get environment variable with optional default and required check."""
    value = os.getenv(key, default)
    if required and not value:
        raise ValueError(f"Required environment variable {key} is not set")
    return value


class ConfigLoader:
    """
    Configuration loader that supports:
    - Environment variables
    - YAML config files
    - Hot reload on file changes
    
    Requirements: 17.1, 17.2, 17.3
    """
    
    def __init__(self, config_dir: str = "config", env_file: str = ".env"):
        self.config_dir = Path(config_dir)
        self.env_file = env_file
        self._config: Optional[AppConfig] = None
        self._observer: Optional[Observer] = None
        self._lock = threading.Lock()
        self._reload_callbacks: list = []
        
        # Load .env file
        load_env_file(self.env_file)
    
    def load(self) -> AppConfig:
        """Load configuration from environment and YAML files."""
        with self._lock:
            # Load from environment variables
            database_config = self._load_database_config()
            llm_config = self._load_llm_config()
            apify_config = self._load_apify_config()
            steel_config = self._load_steel_config()
            pinecone_config = self._load_pinecone_config()
            s3_config = self._load_s3_config()
            email_config = self._load_email_config()
            budget_config = self._load_budget_config()
            rate_limit_config = self._load_rate_limit_config()
            kill_switch_config = self._load_kill_switch_config()
            system_config = self._load_system_config()
            
            # Load niches from YAML if available
            niches = self._load_niches_config()
            
            self._config = AppConfig(
                database=database_config,
                llm=llm_config,
                apify=apify_config,
                steel=steel_config,
                pinecone=pinecone_config,
                s3=s3_config,
                email=email_config,
                budget=budget_config,
                rate_limits=rate_limit_config,
                kill_switches=kill_switch_config,
                system=system_config,
                niches=niches,
            )
            
            return self._config
    
    def _load_database_config(self) -> DatabaseConfig:
        """Load database configuration from environment."""
        return DatabaseConfig(
            supabase_url=get_env("SUPABASE_URL", "https://your-project.supabase.co"),
            supabase_anon_key=get_env("SUPABASE_ANON_KEY", "your-anon-key"),
            supabase_service_role_key=get_env("SUPABASE_SERVICE_ROLE_KEY", "your-service-role-key"),
            database_url=get_env("DATABASE_URL", "postgresql://localhost:5432/zrai"),
        )
    
    def _load_llm_config(self) -> LLMConfig:
        """Load LLM configuration from environment."""
        provider_str = get_env("DEFAULT_LLM_PROVIDER", "google")
        return LLMConfig(
            provider=provider_str,
            model=get_env("DEFAULT_LLM_MODEL", "gemini-2.5-flash"),
            openai_api_key=get_env("OPENAI_API_KEY"),
            anthropic_api_key=get_env("ANTHROPIC_API_KEY"),
            google_api_key=get_env("GOOGLE_API_KEY"),
        )
    
    def _load_apify_config(self) -> ApifyConfig:
        """Load Apify configuration from environment."""
        return ApifyConfig(
            api_token=get_env("APIFY_API_TOKEN", "your-apify-token"),
        )
    
    def _load_steel_config(self) -> SteelConfig:
        """Load Steel.dev configuration from environment."""
        return SteelConfig(
            api_key=get_env("STEEL_API_KEY", "your-steel-key"),
        )
    
    def _load_pinecone_config(self) -> PineconeConfig:
        """Load Pinecone configuration from environment."""
        return PineconeConfig(
            api_key=get_env("PINECONE_API_KEY", "your-pinecone-key"),
            environment=get_env("PINECONE_ENVIRONMENT", "us-east-1"),
            index_name=get_env("PINECONE_INDEX_NAME", "zrai-playbooks"),
        )
    
    def _load_s3_config(self) -> S3Config:
        """Load S3 configuration from environment."""
        return S3Config(
            access_key_id=get_env("AWS_ACCESS_KEY_ID"),
            secret_access_key=get_env("AWS_SECRET_ACCESS_KEY"),
            region=get_env("AWS_REGION", "us-east-1"),
            bucket_name=get_env("S3_BUCKET_NAME", "zrai-artifacts"),
            use_supabase_storage=get_env("USE_SUPABASE_STORAGE", "true").lower() == "true",
        )
    
    def _load_email_config(self) -> EmailConfig:
        """Load email configuration from environment."""
        return EmailConfig(
            smtp_host=get_env("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(get_env("SMTP_PORT", "587")),
            smtp_user=get_env("SMTP_USER"),
            smtp_password=get_env("SMTP_PASSWORD"),
            from_email=get_env("FROM_EMAIL"),
        )
    
    def _load_budget_config(self) -> BudgetConfig:
        """Load budget configuration from environment."""
        return BudgetConfig(
            daily_llm_token_limit=int(get_env("DAILY_LLM_TOKEN_LIMIT", "1000000")),
            daily_browser_session_limit=int(get_env("DAILY_BROWSER_SESSION_LIMIT", "100")),
            daily_scraper_run_limit=int(get_env("DAILY_SCRAPER_RUN_LIMIT", "50")),
        )
    
    def _load_rate_limit_config(self) -> RateLimitConfig:
        """Load rate limit configuration from environment."""
        return RateLimitConfig(
            max_emails_per_domain_per_day=int(get_env("MAX_EMAILS_PER_DOMAIN_PER_DAY", "5")),
            max_emails_per_hour=int(get_env("MAX_EMAILS_PER_HOUR", "50")),
            max_emails_per_day=int(get_env("MAX_EMAILS_PER_DAY", "200")),
        )
    
    def _load_kill_switch_config(self) -> KillSwitchConfig:
        """Load kill switch configuration from environment."""
        return KillSwitchConfig(
            global_kill=get_env("KILL_SWITCH_GLOBAL", "false").lower() == "true",
            discovery_kill=get_env("KILL_SWITCH_DISCOVERY", "false").lower() == "true",
            audit_kill=get_env("KILL_SWITCH_AUDIT", "false").lower() == "true",
            outreach_kill=get_env("KILL_SWITCH_OUTREACH", "false").lower() == "true",
        )
    
    def _load_system_config(self) -> SystemConfig:
        """Load system configuration from environment."""
        return SystemConfig(
            environment=get_env("ENVIRONMENT", "development"),
            max_concurrent_leads=int(get_env("MAX_CONCURRENT_LEADS", "10")),
            log_level=get_env("LOG_LEVEL", "INFO"),
        )
    
    def _load_niches_config(self) -> Dict[str, NicheConfig]:
        """Load niches configuration from YAML file."""
        niches_file = self.config_dir / "niches.yaml"
        if not niches_file.exists():
            return {}
        
        with open(niches_file, 'r') as f:
            data = yaml.safe_load(f) or {}
        
        niches = {}
        for name, config in data.get('niches', {}).items():
            weights_data = config.get('scoring_weights', {})
            scoring_weights = ScoringWeights(**weights_data) if weights_data else ScoringWeights()
            
            niches[name] = NicheConfig(
                name=name,
                keywords=config.get('keywords', []),
                geo_filters=config.get('geo_filters', []),
                scoring_weights=scoring_weights,
                min_score_threshold=config.get('min_score_threshold', 60),
                tier_a_threshold=config.get('tier_a_threshold', 80),
                tier_b_threshold=config.get('tier_b_threshold', 60),
            )
        
        return niches
    
    def get_config(self) -> AppConfig:
        """Get current configuration, loading if necessary."""
        if self._config is None:
            return self.load()
        return self._config
    
    def reload(self) -> AppConfig:
        """Force reload configuration.
        Requirements: 17.2
        """
        config = self.load()
        for callback in self._reload_callbacks:
            callback(config)
        return config
    
    def on_reload(self, callback) -> None:
        """Register a callback to be called when config is reloaded."""
        self._reload_callbacks.append(callback)
    
    def start_watching(self) -> None:
        """Start watching config files for changes.
        Requirements: 17.2
        """
        if self._observer is not None:
            return
        
        class ConfigChangeHandler(FileSystemEventHandler):
            def __init__(self, loader):
                self.loader = loader
            
            def on_modified(self, event):
                if event.src_path.endswith('.yaml') or event.src_path.endswith('.yml'):
                    self.loader.reload()
        
        self._observer = Observer()
        if self.config_dir.exists():
            self._observer.schedule(
                ConfigChangeHandler(self),
                str(self.config_dir),
                recursive=False
            )
            self._observer.start()
    
    def stop_watching(self) -> None:
        """Stop watching config files."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None


# Global config loader instance
_config_loader: Optional[ConfigLoader] = None


def load_config(config_dir: str = "config", env_file: str = ".env") -> AppConfig:
    """Load application configuration.
    
    This is the main entry point for loading configuration.
    Requirements: 17.1
    """
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(config_dir, env_file)
    return _config_loader.load()


def get_config_loader() -> ConfigLoader:
    """Get the global config loader instance."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader
