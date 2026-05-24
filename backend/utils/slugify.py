"""utils/slugify.py"""
import re


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


async def make_unique_slug(base: str, db, model) -> str:
    """Generate a unique slug by appending a counter if needed."""
    from sqlalchemy import select
    slug = slugify(base)
    candidate = slug
    counter = 1
    while True:
        result = await db.execute(select(model).where(model.slug == candidate))
        if not result.scalar_one_or_none():
            return candidate
        candidate = f"{slug}-{counter}"
        counter += 1
