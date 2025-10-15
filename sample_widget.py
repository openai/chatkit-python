from pydantic import BaseModel

class SampleWidget(BaseModel):
    id: str
    data: dict