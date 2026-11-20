import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class BotConfig:
    token: str = field(repr=False)
    database_url: str = field(repr=False)
    admin_password: str | None = field(default=None, repr=False)
    proxy_url: str | None = field(default=None, repr=False)

    @classmethod
    def load(cls):
        values = {**dotenv_values(Path(__file__).resolve().parents[1] / ".env"), **os.environ}
        for key in ("BOT_TOKEN", "DATABASE_URL"):
            if not values.get(key):
                raise ValueError(f"{key} is required")
        return cls(
            token=values["BOT_TOKEN"],
            database_url=values["DATABASE_URL"],
            admin_password=values.get("BOT_ADMIN_PASSWORD") or None,
            proxy_url=values.get("PROXY_URL") or None,
        )
