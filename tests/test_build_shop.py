import datetime as dt
import unittest

from scripts import build_shop


def make_item(
    code,
    name,
    *,
    classification="H5",
    taxonomy_type="Ordinary chondrite",
    price=None,
    mass=None,
    listed_at=None,
    found_at=None,
    lookup_status="ok",
    rarity_note="",
):
    item = {
        "slug": f"item-{code}",
        "title": name,
        "name": name,
        "status": "available",
        "classification": classification,
        "taxonomy": {"type": taxonomy_type},
        "metbull_lookup": {"status": lookup_status},
        "metbull": {"code": str(code), "official_name": name},
    }
    if price is not None:
        item["price_usd"] = price
    if mass is not None:
        item["weight_g"] = mass
    if listed_at:
        item["listed_at"] = listed_at
    if found_at:
        item["found_at"] = found_at
    if rarity_note:
        item["rarity_note"] = rarity_note
    return item


def reason_codes(result):
    return [reason["code"] for reason in result["items"][0].get("reasons", [])]


class ShopHighlightTests(unittest.TestCase):
    def setUp(self):
        self.today = dt.datetime.now(dt.UTC).date()
        self.today_iso = self.today.isoformat()

    def test_low_price_requires_eight_distinct_matched_peers(self):
        items = [make_item(1, "Target", price=10, mass=10, listed_at=self.today_iso)]
        items.extend(
            make_item(index + 2, f"Peer {index}", price=100 + index * 10, mass=10)
            for index in range(8)
        )

        result = build_shop.build_shop_highlights(items)

        self.assertIn("LOW_PPG_IN_INVENTORY", reason_codes(result))
        self.assertEqual(result["items"][0]["metrics"]["price_peer_count"], 8)

    def test_unmatched_candidate_cannot_receive_automatic_price_flag(self):
        target = make_item(
            1,
            "Unmatched target",
            price=10,
            mass=10,
            listed_at=self.today_iso,
            lookup_status="not_found",
        )
        target["metbull"] = {}
        peers = [
            make_item(index + 2, f"Peer {index}", price=100 + index * 10, mass=10)
            for index in range(8)
        ]

        result = build_shop.build_shop_highlights([target, *peers])

        self.assertEqual(reason_codes(result), ["NO_EXACT_METBULL_MATCH"])

    def test_rarity_requires_large_varied_matched_inventory(self):
        items = [
            make_item(
                100,
                "Rare target",
                classification="Angrite",
                taxonomy_type="Angrite",
                listed_at=self.today_iso,
                rarity_note="Documented scarce classification.",
            ),
            make_item(101, "Rare peer", classification="Angrite", taxonomy_type="Angrite"),
        ]
        items.extend(
            make_item(200 + index, f"Common {index}", taxonomy_type=f"Type {index % 4}")
            for index in range(18)
        )

        result = build_shop.build_shop_highlights(items)

        self.assertEqual(reason_codes(result), ["RARE_IN_INVENTORY", "RARITY_NOTE"])

    def test_future_dates_are_excluded_and_new_window_is_45_dates(self):
        future = (self.today + dt.timedelta(days=1)).isoformat()
        newest_in_window = (self.today - dt.timedelta(days=44)).isoformat()
        first_outside_window = (self.today - dt.timedelta(days=45)).isoformat()
        items = [
            make_item(1, "Future", listed_at=future),
            make_item(2, "Window edge", listed_at=newest_in_window),
            make_item(3, "Outside window", listed_at=first_outside_window),
        ]

        result = build_shop.build_shop_highlights(items)
        by_slug = {item["slug"]: item for item in result["items"]}

        self.assertNotIn("item-1", by_slug)
        self.assertEqual(by_slug["item-2"]["recency_labels"], ["New listing"])
        self.assertNotIn("recency_labels", by_slug["item-3"])

    def test_highlights_limit_and_sort_by_latest_date(self):
        items = [
            make_item(
                index,
                f"Item {index}",
                listed_at=(self.today - dt.timedelta(days=index)).isoformat(),
            )
            for index in range(8)
        ]

        result = build_shop.build_shop_highlights(items)

        self.assertEqual(len(result["items"]), build_shop.HIGHLIGHT_LIMIT)
        self.assertEqual(result["items"][0]["slug"], "item-0")
        self.assertEqual(result["items"][-1]["slug"], "item-5")

    def test_not_found_cache_expires_after_seven_days(self):
        now = dt.datetime.now(dt.UTC)
        recent = {
            "status": "not_found",
            "cached_at": (now - dt.timedelta(days=6)).isoformat(),
        }
        stale = {
            "status": "not_found",
            "cached_at": (now - dt.timedelta(days=8)).isoformat(),
        }

        self.assertTrue(
            build_shop.cache_entry_is_recent(
                recent,
                "not_found",
                build_shop.NOT_FOUND_RETRY_SECONDS,
                now,
            )
        )
        self.assertFalse(
            build_shop.cache_entry_is_recent(
                stale,
                "not_found",
                build_shop.NOT_FOUND_RETRY_SECONDS,
                now,
            )
        )


if __name__ == "__main__":
    unittest.main()
