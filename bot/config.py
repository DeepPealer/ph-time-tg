from dataclasses import dataclass, field
from os import getenv
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    admin_chat_id: int | None
    city_chat_id: int | None
    city_thread_gomel: int | None   # message_thread_id for Gomel topic
    city_thread_minsk: int | None   # message_thread_id for Minsk topic
    admin_ids: list[int]
    database_url: str


def load_config() -> Config:
    raw_ids = getenv("ADMIN_IDS", "")
    admin_ids = [int(x.strip()) for x in raw_ids.split(",") if x.strip().isdigit()]

    chat_raw = getenv("ADMIN_CHAT_ID", "").strip()
    admin_chat_id = int(chat_raw) if chat_raw.lstrip("-").isdigit() else None

    city_raw = getenv("CITY_CHAT_ID", "").strip()
    city_chat_id = int(city_raw) if city_raw.lstrip("-").isdigit() else None

    def _parse_thread(key: str) -> int | None:
        v = getenv(key, "").strip()
        return int(v) if v.isdigit() else None

    return Config(
        bot_token=getenv("BOT_TOKEN", ""),
        admin_chat_id=admin_chat_id,
        city_chat_id=city_chat_id,
        city_thread_gomel=_parse_thread("CITY_THREAD_GOMEL"),
        city_thread_minsk=_parse_thread("CITY_THREAD_MINSK"),
        admin_ids=admin_ids,
        database_url=getenv("DATABASE_URL", "sqlite+aiosqlite:///data/bot.db"),
    )


config = load_config()

