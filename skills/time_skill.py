import datetime
from skills.base_skill import BaseSkill
from typing import Any, Optional

class TimeSkill(BaseSkill):
    name = "time"
    keywords = ["time"]

    async def handle(self, text: str, jarvis: Any) -> Optional[str]:
        return datetime.datetime.now().strftime("%H:%M")