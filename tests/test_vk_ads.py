import datetime as dt

from agent5_marketing_analytics.connectors.vk_ads import normalize


def test_normalize_produces_rows_from_nested_payload():
    payload = {
        "items": [
            {
                "id": 555,
                "name": "Тестовый план",
                "rows": [
                    {"date": "2026-07-06", "base": {"spent": 800.25, "clicks": 30, "shows": 4000, "goals": 3}},
                ],
            }
        ]
    }

    rows = normalize(payload)

    assert len(rows) == 1
    row = rows[0]
    assert row.channel == "vk_ads"
    assert row.campaign_id == "555"
    assert row.campaign_name == "Тестовый план"
    assert row.metric_date == dt.date(2026, 7, 6)
    assert row.spend == 800.25
    assert row.clicks == 30
    assert row.impressions == 4000
    assert row.conversions == 3
    assert row.cpl == 266.75


def test_normalize_handles_empty_payload():
    assert normalize({}) == []
    assert normalize({"items": []}) == []
