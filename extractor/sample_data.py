"""Sample documents and expected results for testing the Document Extractor.

Three personas:
  PRIYA  — main test case (FD interest trap, new regime wins)
  RAJAN  — 62-year-old pensioner; tests senior 80D limit & rebate
  ANKUR  — ₹11.5L earner; tests new-regime 87A rebate (tax → 0)
"""

from .models import TaxpayerProfile, Form16, AIS, Sec80C, DeclaredByTaxpayer

# ---------------------------------------------------------------------------
# Raw-text documents (simulate OCR / PDF parse output fed to the extractor)
# ---------------------------------------------------------------------------

PRIYA_FORM16_TEXT = """
FORM 16 – CERTIFICATE OF TAX DEDUCTED AT SOURCE FROM SALARY
Financial Year: 2025-26 (Assessment Year 2026-27)

Employer  : Acme Software Pvt Ltd, Bengaluru
Employee  : Priya Sharma  |  Age: 31  |  City: Bengaluru (Metro)

PART B – DETAILS OF SALARY PAID AND DEDUCTIONS
Gross Salary Paid                : ₹ 18,00,000
  Basic Pay                      : ₹  7,20,000
  House Rent Allowance (HRA)     : ₹  2,88,000
  Other Allowances               : ₹  7,92,000
Professional Tax                 : ₹      2,400
Total TDS Deducted and Deposited : ₹  1,95,000
"""

PRIYA_AIS_TEXT = """
ANNUAL INFORMATION STATEMENT (AIS) – FY 2025-26
Taxpayer: Priya Sharma

INCOME REPORTED TO INCOME TAX DEPARTMENT
─────────────────────────────────────────
1. Salary Income (Acme Software Pvt Ltd)     : ₹ 18,00,000
2. Savings Account Interest (HDFC Bank)      : ₹     12,000
3. Fixed Deposit Interest (SBI FD)           : ₹     38,000

TAX DEDUCTED AT SOURCE (TDS)
─────────────────────────────────────────
   Total TDS reflected                        : ₹  1,95,000
"""

PRIYA_DECLARATIONS_TEXT = """
TAXPAYER DECLARATIONS AND INVESTMENT PROOFS

Personal Details
  Name : Priya Sharma
  Age  : 31 years
  City : Bengaluru  (Metro city – YES)

HOUSE RENT (HRA EXEMPTION CLAIM)
  Annual Rent Paid          : ₹ 3,00,000
  Rent Receipts Available   : Yes

INVESTMENTS – SECTION 80C
  EPF Contribution          : ₹ 86,400
  ELSS Mutual Fund (SIP)    : ₹ 63,600
  Total 80C                 : ₹ 1,50,000  (capped at ₹ 1,50,000)

HEALTH INSURANCE – SECTION 80D
  Self & Family Premium      : ₹ 25,000

SAVINGS ACCOUNT INTEREST DECLARED
  Interest Earned (HDFC)    : ₹ 12,000

NOTE: No Fixed Deposit interest declared by taxpayer.
"""

# ---------------------------------------------------------------------------
# Rajan – pensioner, 62 yrs, ₹6 L total income
# ---------------------------------------------------------------------------

RAJAN_FORM16_TEXT = """
FORM 16 – FY 2025-26
Employer  : Central Government (Pension)
Employee  : Rajan Iyer  |  Age: 62  |  City: Chennai (Metro)

Gross Pension Paid               : ₹  6,00,000
Basic                            : ₹  6,00,000
HRA Received                     : ₹          0
Professional Tax                 : ₹          0
Total TDS Deducted               : ₹          0
"""

RAJAN_AIS_TEXT = """
AIS – FY 2025-26  |  Taxpayer: Rajan Iyer

1. Pension Income                             : ₹  6,00,000
2. Savings Account Interest                   : ₹     8,000
3. Fixed Deposit Interest                     : ₹    20,000

Total TDS                                     : ₹          0
"""

RAJAN_DECLARATIONS_TEXT = """
TAXPAYER DECLARATIONS

Name   : Rajan Iyer
Age    : 62 years
City   : Chennai (Metro city – YES)

Rent Paid Annual  : ₹ 0
Rent Receipts     : No

Section 80C  : NIL
Section 80D (Self, Senior Citizen) : ₹ 50,000
Savings Interest Declared          : ₹ 8,000
FD Interest Declared               : ₹ 20,000
"""

# ---------------------------------------------------------------------------
# Ankur – ₹11.5 L earner (tests new-regime 87A rebate)
# ---------------------------------------------------------------------------

ANKUR_FORM16_TEXT = """
FORM 16 – FY 2025-26
Employer  : Startup XYZ Pvt Ltd
Employee  : Ankur Mehta  |  Age: 28  |  City: Pune (Non-Metro)

Gross Salary                     : ₹ 11,50,000
Basic                            : ₹  4,60,000
HRA Received                     : ₹  1,84,000
Professional Tax                 : ₹      2,400
Total TDS Deducted               : ₹     90,000
"""

ANKUR_AIS_TEXT = """
AIS – FY 2025-26  |  Taxpayer: Ankur Mehta

1. Salary Income (Startup XYZ Pvt Ltd)       : ₹ 11,50,000
2. Savings Account Interest                   : ₹      3,000

Total TDS                                     : ₹     90,000
"""

ANKUR_DECLARATIONS_TEXT = """
TAXPAYER DECLARATIONS

Name   : Ankur Mehta
Age    : 28 years
City   : Pune (Metro city – NO)

Rent Paid Annual  : ₹ 1,20,000
Rent Receipts     : Yes

Section 80C       : ₹ 1,50,000 (EPF + ELSS)
Section 80D Self  : ₹ 18,000
Savings Interest  : ₹ 3,000
"""

# ---------------------------------------------------------------------------
# Pre-built structured profiles (used for unit tests without LLM)
# ---------------------------------------------------------------------------

PRIYA_PROFILE = TaxpayerProfile(
    name="Priya Sharma",
    age=31,
    city="Bengaluru",
    metro=True,
    fy="2025-26",
    form16=Form16(
        employer="Acme Software Pvt Ltd",
        gross_salary=1_800_000,
        basic=720_000,
        hra_received=288_000,
        professional_tax=2_400,
        tds_deducted=195_000,
    ),
    ais=AIS(
        salary=1_800_000,
        savings_interest=12_000,
        fd_interest=38_000,
        tds_total=195_000,
    ),
    declared=DeclaredByTaxpayer(
        rent_paid_annual=300_000,
        rent_receipts_available=True,
        sec_80c=Sec80C(epf=86_400, elss=63_600),
        sec_80d_self=25_000,
        savings_interest=12_000,
        # fd_interest intentionally absent — the deliberate trap
    ),
)

RAJAN_PROFILE = TaxpayerProfile(
    name="Rajan Iyer",
    age=62,
    city="Chennai",
    metro=True,
    fy="2025-26",
    form16=Form16(
        employer="Central Government (Pension)",
        gross_salary=600_000,
        basic=600_000,
        hra_received=0,
        professional_tax=0,
        tds_deducted=0,
    ),
    ais=AIS(
        salary=600_000,
        savings_interest=8_000,
        fd_interest=20_000,
        tds_total=0,
    ),
    declared=DeclaredByTaxpayer(
        sec_80d_self=50_000,
        savings_interest=8_000,
        fd_interest=20_000,
    ),
)

ANKUR_PROFILE = TaxpayerProfile(
    name="Ankur Mehta",
    age=28,
    city="Pune",
    metro=False,
    fy="2025-26",
    form16=Form16(
        employer="Startup XYZ Pvt Ltd",
        gross_salary=1_150_000,
        basic=460_000,
        hra_received=184_000,
        professional_tax=2_400,
        tds_deducted=90_000,
    ),
    ais=AIS(
        salary=1_150_000,
        savings_interest=3_000,
        tds_total=90_000,
    ),
    declared=DeclaredByTaxpayer(
        rent_paid_annual=120_000,
        rent_receipts_available=True,
        sec_80c=Sec80C(epf=75_000, elss=75_000),
        sec_80d_self=18_000,
        savings_interest=3_000,
    ),
)

# Maps persona key → (profile, raw text tuple)
PERSONAS: dict[str, tuple] = {
    "priya": (
        PRIYA_PROFILE,
        PRIYA_FORM16_TEXT,
        PRIYA_AIS_TEXT,
        PRIYA_DECLARATIONS_TEXT,
    ),
    "rajan": (
        RAJAN_PROFILE,
        RAJAN_FORM16_TEXT,
        RAJAN_AIS_TEXT,
        RAJAN_DECLARATIONS_TEXT,
    ),
    "ankur": (
        ANKUR_PROFILE,
        ANKUR_FORM16_TEXT,
        ANKUR_AIS_TEXT,
        ANKUR_DECLARATIONS_TEXT,
    ),
}
