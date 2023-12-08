import os
from dotenv import load_dotenv

load_dotenv()
decode_url = os.getenv("decode_url") if os.getenv("decode_url") else None
grafana_token = os.getenv("grafana_token") if os.getenv("grafana_token") else None
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
