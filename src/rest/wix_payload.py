from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class WixData(BaseModel):
    site_email: Optional[str] = Query(None, alias="site.email")
    site_name: Optional[str] = Query(None, alias="site.name")
    meta_site_id: Optional[str] = Query(None, alias="metaSiteId")

    contact_country: Optional[str] = Query(None, alias="contact.Address[0].Country")
    contact_email: Optional[str] = Query(None, alias="contact.Email[0]")
    contact_first_name: Optional[str] = Query(None, alias="contact.Name.First")
    contact_last_name: Optional[str] = Query(None, alias="contact.Name.Last")
    contact_id: Optional[str] = Query(None, alias="contact.Id")
    start_date: Optional[str] = Query(None, alias="start.date")

    payment_method: Optional[str] = Query(None, alias="paidplan.paymentmethod")
    description: Optional[str] = Query(None, alias="paidplan.description")
    order_id: Optional[str] = Query(None, alias="paidplan.orderid")
    id: Optional[str] = Query(None, alias="paidplan.id")
    title: Optional[str] = Query(None, alias="paidplan.title")
    valid_for: Optional[str] = Query(None, alias="paidplan.validfor")
    paidplan_start_date: Optional[str] = Query(None, alias="paidplan.startdate")
    price: Optional[str] = Query(None, alias="paidplan.price")
    subscription_id: Optional[str] = Query(None, alias="paidplan.subscriptionid")
    price_amount: Optional[int] = Query(None, alias="paidplan.priceamount")
    valid_until: Optional[str] = Query(None, alias="paidplan.validuntil")


class WixPayload(BaseModel):
    data: Optional[WixData]
