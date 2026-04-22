from pydantic import BaseModel


class SeasonsList(BaseModel):
    season: str
