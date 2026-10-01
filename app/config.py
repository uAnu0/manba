import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    app_name: str = os.getenv("APP_NAME", "Manba")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    # When set, every /api/verify call must send it in the X-Access-Token header. Set it whenever the app is
    # reachable from the internet with a shared OPENROUTER_API_KEY: otherwise anyone with the URL can spend it.
    api_access_token: str = os.getenv("API_ACCESS_TOKEN", "")


settings = Settings()
