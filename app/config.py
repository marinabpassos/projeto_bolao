"""Configuração lida de variáveis de ambiente (.env em dev, painel da Vercel em prod)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    session_secret: str = "dev-insecure-secret-change-me"
    google_client_id: str = ""
    google_client_secret: str = ""
    admin_emails: str = ""
    base_url: str = "http://localhost:8000"
    dev_login: bool = False  # libera /auth/dev-login (apenas para testes locais)
    football_data_token: str = ""  # token gratuito da football-data.org (sync de fixtures/resultados)

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().casefold() for e in self.admin_emails.split(",") if e.strip()}

    def is_admin(self, email: str | None) -> bool:
        return bool(email) and email.casefold() in self.admin_email_set


@lru_cache
def get_settings() -> Settings:
    return Settings()
