from typing import Optional

from pydantic import BaseModel


class WixData(BaseModel):
    email: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    start_date: Optional[str]
    order_id: Optional[str]
    plan_name: Optional[str]
    appendix: Optional[str]


class WixPayLoad(BaseModel):
    data: Optional[WixData]
