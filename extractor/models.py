"""Pydantic models for TaxPilot Document Extractor (P2)."""

from __future__ import annotations
from pydantic import BaseModel, Field, computed_field
from typing import Optional


class Form16(BaseModel):
    employer: str
    gross_salary: int
    basic: int
    hra_received: int
    professional_tax: int
    tds_deducted: int


class AIS(BaseModel):
    salary: int
    savings_interest: int = 0
    fd_interest: int = 0
    dividend_income: int = 0
    tds_total: int


class Sec80C(BaseModel):
    epf: int = 0
    elss: int = 0
    lic: int = 0
    ppf: int = 0
    nsc: int = 0
    home_loan_principal: int = 0

    @computed_field
    @property
    def total(self) -> int:
        return self.epf + self.elss + self.lic + self.ppf + self.nsc + self.home_loan_principal


class DeclaredByTaxpayer(BaseModel):
    rent_paid_annual: int = 0
    rent_receipts_available: bool = False
    sec_80c: Sec80C = Field(default_factory=Sec80C)
    sec_80d_self: int = 0
    sec_80d_parents: int = 0
    savings_interest: int = 0
    fd_interest: int = 0
    nps_80ccd1b: int = 0


class TaxpayerProfile(BaseModel):
    name: str
    age: int
    city: str
    metro: bool
    fy: str = "2025-26"
    form16: Form16
    ais: AIS
    declared: DeclaredByTaxpayer


class MismatchItem(BaseModel):
    income_type: str
    ais_amount: int
    declared_amount: int
    difference: int = Field(description="AIS amount minus declared amount; positive means undeclared income")
    description: str


class AISMismatchReport(BaseModel):
    mismatches: list[MismatchItem] = Field(default_factory=list)
    total_undeclared_income: int = 0
    has_mismatches: bool = False
