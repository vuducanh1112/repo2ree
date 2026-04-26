from pydantic import BaseModel


class Dependency(BaseModel):
    name: str
    version: str | None
    source: str | None
