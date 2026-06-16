from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable, List

from beavers_choice.domain.models import (
    CatalogItem,
    CatalogMatch,
    ExtractedItem,
    InquiryPlan,
    RequestedItem,
)


PAPER_SUPPLIES = [
    CatalogItem(item_name="A4 paper", category="paper", unit_price=0.05),
    CatalogItem(item_name="Letter-sized paper", category="paper", unit_price=0.06),
    CatalogItem(item_name="Cardstock", category="paper", unit_price=0.15),
    CatalogItem(item_name="Colored paper", category="paper", unit_price=0.10),
    CatalogItem(item_name="Glossy paper", category="paper", unit_price=0.20),
    CatalogItem(item_name="Matte paper", category="paper", unit_price=0.18),
    CatalogItem(item_name="Recycled paper", category="paper", unit_price=0.08),
    CatalogItem(item_name="Eco-friendly paper", category="paper", unit_price=0.12),
    CatalogItem(item_name="Poster paper", category="paper", unit_price=0.25),
    CatalogItem(item_name="Banner paper", category="paper", unit_price=0.30),
    CatalogItem(item_name="Kraft paper", category="paper", unit_price=0.10),
    CatalogItem(item_name="Construction paper", category="paper", unit_price=0.07),
    CatalogItem(item_name="Wrapping paper", category="paper", unit_price=0.15),
    CatalogItem(item_name="Glitter paper", category="paper", unit_price=0.22),
    CatalogItem(item_name="Decorative paper", category="paper", unit_price=0.18),
    CatalogItem(item_name="Letterhead paper", category="paper", unit_price=0.12),
    CatalogItem(item_name="Legal-size paper", category="paper", unit_price=0.08),
    CatalogItem(item_name="Crepe paper", category="paper", unit_price=0.05),
    CatalogItem(item_name="Photo paper", category="paper", unit_price=0.25),
    CatalogItem(item_name="Uncoated paper", category="paper", unit_price=0.06),
    CatalogItem(item_name="Butcher paper", category="paper", unit_price=0.10),
    CatalogItem(item_name="Heavyweight paper", category="paper", unit_price=0.20),
    CatalogItem(item_name="Standard copy paper", category="paper", unit_price=0.04),
    CatalogItem(item_name="Bright-colored paper", category="paper", unit_price=0.12),
    CatalogItem(item_name="Patterned paper", category="paper", unit_price=0.15),
    CatalogItem(item_name="Paper plates", category="product", unit_price=0.10),
    CatalogItem(item_name="Paper cups", category="product", unit_price=0.08),
    CatalogItem(item_name="Paper napkins", category="product", unit_price=0.02),
    CatalogItem(item_name="Disposable cups", category="product", unit_price=0.10),
    CatalogItem(item_name="Table covers", category="product", unit_price=1.50),
    CatalogItem(item_name="Envelopes", category="product", unit_price=0.05),
    CatalogItem(item_name="Sticky notes", category="product", unit_price=0.03),
    CatalogItem(item_name="Notepads", category="product", unit_price=2.00),
    CatalogItem(item_name="Invitation cards", category="product", unit_price=0.50),
    CatalogItem(item_name="Flyers", category="product", unit_price=0.15),
    CatalogItem(item_name="Party streamers", category="product", unit_price=0.05),
    CatalogItem(
        item_name="Decorative adhesive tape (washi tape)",
        category="product",
        unit_price=0.20,
    ),
    CatalogItem(item_name="Paper party bags", category="product", unit_price=0.25),
    CatalogItem(
        item_name="Name tags with lanyards",
        category="product",
        unit_price=0.75,
    ),
    CatalogItem(item_name="Presentation folders", category="product", unit_price=0.50),
    CatalogItem(
        item_name="Large poster paper (24x36 inches)",
        category="large_format",
        unit_price=1.00,
    ),
    CatalogItem(
        item_name="Rolls of banner paper (36-inch width)",
        category="large_format",
        unit_price=2.50,
    ),
    CatalogItem(item_name="100 lb cover stock", category="specialty", unit_price=0.50),
    CatalogItem(item_name="80 lb text paper", category="specialty", unit_price=0.40),
    CatalogItem(item_name="250 gsm cardstock", category="specialty", unit_price=0.30),
    CatalogItem(item_name="220 gsm poster paper", category="specialty", unit_price=0.35),
]


UNSUPPORTED_TERMS = {
    "a3",
    "a5",
    "balloon",
    "balloons",
    "ticket",
    "tickets",
    "cardboard",
}


ALIASES = {
    "a4": "A4 paper",
    "a4 paper": "A4 paper",
    "a4 printing paper": "A4 paper",
    "a4 printer paper": "A4 paper",
    "a4 white paper": "A4 paper",
    "a4 white printer paper": "A4 paper",
    "letter paper": "Letter-sized paper",
    "letter sized paper": "Letter-sized paper",
    "card stock": "Cardstock",
    "cardstock": "Cardstock",
    "heavy cardstock": "Cardstock",
    "heavyweight cardstock": "Cardstock",
    "sturdy cardstock": "Cardstock",
    "white cardstock": "Cardstock",
    "colored cardstock": "Cardstock",
    "colorful cardstock": "Cardstock",
    "high quality white cardstock": "Cardstock",
    "colored paper": "Colored paper",
    "colorful paper": "Colored paper",
    "8.5x11 colored paper": "Colored paper",
    "glossy paper": "Glossy paper",
    "a4 glossy paper": "Glossy paper",
    "glossy a4 paper": "Glossy paper",
    "matte paper": "Matte paper",
    "a4 matte paper": "Matte paper",
    "recycled paper": "Recycled paper",
    "printer paper": "Standard copy paper",
    "printing paper": "Standard copy paper",
    "standard printer paper": "Standard copy paper",
    "standard printing paper": "Standard copy paper",
    "white printer paper": "Standard copy paper",
    "copy paper": "Standard copy paper",
    "poster paper": "Poster paper",
    "colorful poster paper": "Poster paper",
    "poster board": "Large poster paper (24x36 inches)",
    "poster boards": "Large poster paper (24x36 inches)",
    "posters": "Large poster paper (24x36 inches)",
    "24x36 poster board": "Large poster paper (24x36 inches)",
    "streamers": "Party streamers",
    "party streamers": "Party streamers",
    "washi tape": "Decorative adhesive tape (washi tape)",
    "decorative washi tape": "Decorative adhesive tape (washi tape)",
    "decorative adhesive tape": "Decorative adhesive tape (washi tape)",
    "table napkins": "Paper napkins",
    "napkins": "Paper napkins",
    "paper cups": "Paper cups",
    "paper plates": "Paper plates",
    "envelopes": "Envelopes",
    "kraft paper envelopes": "Envelopes",
    "flyers": "Flyers",
}


def normalize_phrase(value: str) -> str:
    """Normalize customer/catalog wording for deterministic matching."""
    normalized = value.casefold()
    normalized = normalized.replace('"', "")
    normalized = normalized.replace("'", "")
    normalized = re.sub(r"\([^)]*\)", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


class CatalogMatchingService:
    """Map raw customer product phrases to exact catalog names."""

    def __init__(
        self,
        catalog_items: Iterable[CatalogItem] = PAPER_SUPPLIES,
        threshold: float = 0.82,
    ) -> None:
        self.catalog_items = list(catalog_items)
        self.threshold = threshold
        self.by_normalized = {
            normalize_phrase(item.item_name): item for item in self.catalog_items
        }
        self.aliases = {
            normalize_phrase(alias): target for alias, target in ALIASES.items()
        }
        self.sorted_aliases = sorted(
            self.aliases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

    def catalog_names(self) -> List[str]:
        return [item.item_name for item in self.catalog_items]

    def catalog_by_name(self) -> dict[str, CatalogItem]:
        return {item.item_name.casefold(): item for item in self.catalog_items}

    def match_item(self, extracted_item: ExtractedItem) -> CatalogMatch:
        normalized = normalize_phrase(extracted_item.item_description)
        tokens = set(normalized.split())
        if tokens & UNSUPPORTED_TERMS:
            return CatalogMatch(
                original_description=extracted_item.item_description,
                confidence=0.0,
                strategy="unmatched",
                reason="Unsupported size or product family.",
            )

        exact_item = self.by_normalized.get(normalized)
        if exact_item:
            return CatalogMatch(
                original_description=extracted_item.item_description,
                item_name=exact_item.item_name,
                confidence=1.0,
                strategy="exact",
                reason="Exact catalog name match.",
            )

        alias_target = self.aliases.get(normalized)
        if alias_target:
            return CatalogMatch(
                original_description=extracted_item.item_description,
                item_name=alias_target,
                confidence=0.95,
                strategy="alias",
                reason="Known catalog alias match.",
            )

        for alias, alias_target in self.sorted_aliases:
            if alias and re.search(rf"\b{re.escape(alias)}\b", normalized):
                return CatalogMatch(
                    original_description=extracted_item.item_description,
                    item_name=alias_target,
                    confidence=0.90,
                    strategy="alias",
                    reason="Known catalog alias found inside customer phrase.",
                )

        for catalog_key, catalog_item in sorted(
            self.by_normalized.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if catalog_key and re.search(rf"\b{re.escape(catalog_key)}\b", normalized):
                return CatalogMatch(
                    original_description=extracted_item.item_description,
                    item_name=catalog_item.item_name,
                    confidence=0.88,
                    strategy="alias",
                    reason="Catalog name found inside customer phrase.",
                )

        best_name = None
        best_score = 0.0
        for catalog_key, catalog_item in self.by_normalized.items():
            score = SequenceMatcher(None, normalized, catalog_key).ratio()
            if score > best_score:
                best_score = score
                best_name = catalog_item.item_name

        if best_name and best_score >= self.threshold:
            return CatalogMatch(
                original_description=extracted_item.item_description,
                item_name=best_name,
                confidence=round(best_score, 3),
                strategy="fuzzy",
                reason="Fuzzy catalog match above threshold.",
            )

        return CatalogMatch(
            original_description=extracted_item.item_description,
            confidence=round(best_score, 3),
            strategy="unmatched",
            reason="No catalog match exceeded confidence threshold.",
        )

    def normalize_items(self, items: Iterable[ExtractedItem]) -> tuple[list[RequestedItem], list[str], list[CatalogMatch]]:
        requested_items: list[RequestedItem] = []
        unmatched_items: list[str] = []
        match_details: list[CatalogMatch] = []

        for extracted_item in items:
            match = self.match_item(extracted_item)
            match_details.append(match)
            if match.item_name:
                requested_items.append(
                    RequestedItem(
                        item_name=match.item_name,
                        quantity=extracted_item.quantity,
                        requested_description=extracted_item.item_description,
                    )
                )
            else:
                unmatched_items.append(extracted_item.item_description)

        return requested_items, unmatched_items, match_details

    def normalize_plan(self, extracted_plan) -> InquiryPlan:
        requested, unmatched, matches = self.normalize_items(extracted_plan.items)
        return InquiryPlan(
            route=extracted_plan.route,
            request_date=extracted_plan.request_date,
            required_by=extracted_plan.required_by,
            items=requested,
            unmatched_items=[*extracted_plan.unmatched_items, *unmatched],
            customer_summary=extracted_plan.customer_summary,
            match_details=matches,
        )
