"""SQLAlchemy models for the loyalty prototype.

This module defines a simplified version of the data model described in the MVP.  It uses
SQLite as the backing store for demonstration purposes but can be swapped out for
PostgreSQL by changing the database URL in `main.py`.

Relationships:
  * A `Tenant` owns many `User`, `Product`, `Campaign`, `Offer`, `Voucher`,
    `Redemption` and `Transaction` records.
  * A `Campaign` may have many associated `Offer` objects.
  * An `Offer` may generate many `Voucher` objects for individual users.
  * When a voucher is redeemed, a `Redemption` row is created linking the
    redemption back to the offer and voucher.
  * A `Transaction` captures a purchase.  It can optionally reference a
    `Redemption` and capture the attribution (campaign/offer/voucher) in a
    JSON field.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


def generate_uuid() -> str:
    """Generate a UUID string suitable for primary keys."""
    return str(uuid.uuid4())


class Tenant(Base):
    __tablename__ = "tenants"

    id: str = Column(String, primary_key=True, default=generate_uuid)
    name: str = Column(String, nullable=False, unique=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    users = relationship("User", back_populates="tenant")
    products = relationship("Product", back_populates="tenant")
    campaigns = relationship("Campaign", back_populates="tenant")
    offers = relationship("Offer", back_populates="tenant")
    vouchers = relationship("Voucher", back_populates="tenant")
    redemptions = relationship("Redemption", back_populates="tenant")
    transactions = relationship("Transaction", back_populates="tenant")


class User(Base):
    __tablename__ = "users"
    id: str = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: str = Column(String, ForeignKey("tenants.id"), nullable=False)
    email: Optional[str] = Column(String, nullable=True)
    phone: Optional[str] = Column(String, nullable=True)
    attributes: Any = Column(JSON, default=dict)
    consent_push: bool = Column(Boolean, default=False)
    consent_mktg: bool = Column(Boolean, default=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="users")
    vouchers = relationship("Voucher", back_populates="user")
    redemptions = relationship("Redemption", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")


class Product(Base):
    __tablename__ = "products"
    id: str = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: str = Column(String, ForeignKey("tenants.id"), nullable=False)
    sku: str = Column(String, nullable=False)
    name: str = Column(String, nullable=False)
    category: Optional[str] = Column(String, nullable=True)
    price_cents: int = Column(Integer, nullable=False)
    attributes: Any = Column(JSON, default=dict)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uix_tenant_sku"),
    )

    tenant = relationship("Tenant", back_populates="products")


class Campaign(Base):
    __tablename__ = "campaigns"
    id: str = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: str = Column(String, ForeignKey("tenants.id"), nullable=False)
    name: str = Column(String, nullable=False)
    status: str = Column(String, default="draft")  # draft|active|paused|ended
    target: Any = Column(JSON, default=dict)  # {type: all|segment|users, ids:[...]}
    start_at: Optional[datetime] = Column(DateTime, nullable=True)
    end_at: Optional[datetime] = Column(DateTime, nullable=True)
    deeplink_url: Optional[str] = Column(String, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="campaigns")
    offers = relationship("Offer", back_populates="campaign")
    push_notifications = relationship("PushNotification", back_populates="campaign")


class Offer(Base):
    __tablename__ = "offers"
    id: str = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: str = Column(String, ForeignKey("tenants.id"), nullable=False)
    campaign_id: Optional[str] = Column(String, ForeignKey("campaigns.id"), nullable=True)
    type: str = Column(String, nullable=False)  # personal|group
    benefit: Any = Column(JSON, nullable=False)  # {kind:%|fixed, value:int}
    limits: Any = Column(JSON, default=dict)  # {per_user:int, total:int, min_spend_cents:int}
    applies_to: Any = Column(JSON, default=list)  # list of SKUs
    valid_from: datetime = Column(DateTime, nullable=False)
    valid_to: datetime = Column(DateTime, nullable=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="offers")
    campaign = relationship("Campaign", back_populates="offers")
    vouchers = relationship("Voucher", back_populates="offer")
    redemptions = relationship("Redemption", back_populates="offer")


class Voucher(Base):
    __tablename__ = "vouchers"
    id: str = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: str = Column(String, ForeignKey("tenants.id"), nullable=False)
    offer_id: str = Column(String, ForeignKey("offers.id"), nullable=False)
    user_id: str = Column(String, ForeignKey("users.id"), nullable=False)
    code: str = Column(String, unique=True, nullable=False)
    state: str = Column(String, default="issued")  # issued|redeemed|expired|void
    redemption_id: Optional[str] = Column(String, ForeignKey("redemptions.id"), nullable=True)
    issued_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="vouchers")
    offer = relationship("Offer", back_populates="vouchers")
    user = relationship("User", back_populates="vouchers")
    redemption = relationship("Redemption", back_populates="voucher")


class PushNotification(Base):
    __tablename__ = "push_notifications"
    id: str = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: str = Column(String, ForeignKey("tenants.id"), nullable=False)
    campaign_id: Optional[str] = Column(String, ForeignKey("campaigns.id"), nullable=True)
    payload: Any = Column(JSON, nullable=False)  # {title, body, deeplink}
    scheduled_at: Optional[datetime] = Column(DateTime, nullable=True)
    sent_at: Optional[datetime] = Column(DateTime, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant")
    campaign = relationship("Campaign", back_populates="push_notifications")


class Redemption(Base):
    __tablename__ = "redemptions"
    id: str = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: str = Column(String, ForeignKey("tenants.id"), nullable=False)
    offer_id: str = Column(String, ForeignKey("offers.id"), nullable=False)
    user_id: Optional[str] = Column(String, ForeignKey("users.id"), nullable=True)
    voucher_id: Optional[str] = Column(String, ForeignKey("vouchers.id"), nullable=True)
    pos_ref: Optional[str] = Column(String, nullable=True)
    status: str = Column(String, nullable=False)  # approved|denied|settled
    reason: Optional[str] = Column(String, nullable=True)
    redeemed_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="redemptions")
    offer = relationship("Offer", back_populates="redemptions")
    user = relationship("User", back_populates="redemptions")
    voucher = relationship("Voucher", back_populates="redemption")
    transaction = relationship("Transaction", back_populates="redemption", uselist=False)


class Transaction(Base):
    __tablename__ = "transactions"
    id: str = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: str = Column(String, ForeignKey("tenants.id"), nullable=False)
    user_id: Optional[str] = Column(String, ForeignKey("users.id"), nullable=True)
    pos_txn_id: str = Column(String, nullable=False)
    store_id: Optional[str] = Column(String, nullable=True)
    purchased_at: datetime = Column(DateTime, nullable=False)
    total_cents: int = Column(Integer, nullable=False)
    currency: str = Column(String, default="USD", nullable=False)
    lines: Any = Column(JSON, nullable=False)  # list of {sku, qty, unit_price_cents}
    attribution: Any = Column(JSON, default=dict)  # {campaign_id, offer_id, redemption_id}
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)
    redemption_id: Optional[str] = Column(String, ForeignKey("redemptions.id"), nullable=True)

    tenant = relationship("Tenant", back_populates="transactions")
    user = relationship("User", back_populates="transactions")
    redemption = relationship("Redemption", back_populates="transaction")
