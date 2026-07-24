"""
Seed script: populates `branches` and `head_office_directorates` tables.

Usage (run as a module, from the project root, so relative imports work):
    python -m app.seed_org_structure
    (adjust "app" to whatever your package is actually called)
"""

import asyncio
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import AsyncSessionLocal
from .models import Branch, HeadOfficeDirectorate


def make_code(name: str, existing_codes: set[str]) -> str:
    """Generate a short unique uppercase code from a name, e.g. 'Adama Branch' -> 'ADA'."""
    base = re.sub(r"\b(Branch|Directorate|Office)\b", "", name).strip()
    words = base.split()
    if len(words) == 1:
        code = words[0][:3].upper()
    else:
        code = "".join(w[0] for w in words).upper()[:5]

    candidate = code
    i = 1
    while candidate in existing_codes:
        i += 1
        candidate = f"{code}{i}"
    existing_codes.add(candidate)
    return candidate


BRANCH_NAMES = [
    "Adama Branch", "Ambo Branch", "Assela Branch", "Assosa Branch",
    "Bahir Dar Branch", "Bale Robe Branch", "Bishoftu Branch", "Bule Hora Branch",
    "Burayu Branch", "Dessie Branch", "Dire Dawa Branch", "Dodola Branch",
    "Furi Branch", "Gafarsa Branch", "Gambella Branch", "Gelan Branch",
    "Gimbi Branch", "Harar Branch", "Hawassa Branch", "Holeta Branch",
    "Abdisa Aga Branch", "Africa Godana Branch", "Birbirsa Branch", "Bole Branch",
    "Bulbula Branch", "Chaffe Branch", "Chalchali Branch", "Doka Bora Branch",
    "Dollo Biddena Branch", "Ejersa Branch", "Figa Branch", "Finfinne Branch",
    "General Tadesse Biru Branch", "Gerji Branch", "Gofa Branch", "Gofa Gebriel Branch",
    "Gulele Branch", "Head Office Branch", "Jamo Branch", "Kality Branch",
    "Kersa Branch", "Kolfe Branch", "Kotobe Branch", "Lebu Branch",
    "Lemi Kura Branch", "Merkato Branch", "Muda Branch", "Saris Branch",
    "Tullu Meti Branch", "Wadessa Branch", "Jigjiga Branch", "Jimma Branch",
    "Legatafo Branch", "Mekele Branch", "Meki Branch", "Mettu Branch",
    "Modjo Branch", "Nekemte Branch", "Sebeta Branch", "Selale Branch",
    "Shashemene Branch", "Woliso Branch",
]  # 62 total, including Head Office Branch

DIRECTORATE_NAMES = [
    "Agriculture & Microinsurance Directorate",
    "Chief Executive Office",
    "Chief Operations Office",
    "Chief Resources Office",
    "Claims Management Directorate",
    "Company Secretary Office",
    "Engineering Services Directorate",
    "Finance Directorate",
    "Headquarters Project Office",
    "Human Resource Directorate",
    "Information Technology Directorate",
    "Internal Audit Directorate",
    "Investment & Projects Management Directorate",
    "Legal Services Directorate",
    "Life & Health Insurance Directorate",
    "Marketing & Business Development Directorate",
    "Property & Facilities Management Directorate",
    "Reinsurance Services Directorate",
    "Risk Management & Compliance Directorate",
    "Strategy & Change Management Directorate",
    "Takaful Insurance Directorate",
    "Underwriting & Branches Support Directorate",
]


async def seed_branches(session: AsyncSession) -> None:
    existing_codes: set[str] = set()
    result = await session.execute(select(Branch.name))
    existing_names = {row[0] for row in result.all()}

    to_add = []
    for name in BRANCH_NAMES:
        if name in existing_names:
            continue
        code = make_code(name, existing_codes)
        to_add.append(Branch(name=name, code=code))

    session.add_all(to_add)
    print(f"Branches: {len(to_add)} added, {len(existing_names)} already existed.")


async def seed_directorates(session: AsyncSession) -> None:
    existing_codes: set[str] = set()
    result = await session.execute(select(HeadOfficeDirectorate.name))
    existing_names = {row[0] for row in result.all()}

    to_add = []
    for name in DIRECTORATE_NAMES:
        if name in existing_names:
            continue
        code = make_code(name, existing_codes)
        to_add.append(HeadOfficeDirectorate(name=name, code=code))

    session.add_all(to_add)
    print(f"Directorates: {len(to_add)} added, {len(existing_names)} already existed.")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_branches(session)
        await seed_directorates(session)
        await session.commit()
    print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(main())