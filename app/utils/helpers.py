import uuid
from datetime import datetime

def generate_uuid() -> str:
    return str(uuid.uuid4())

def get_current_timestamp() -> int:
    return int(datetime.utcnow().timestamp())
