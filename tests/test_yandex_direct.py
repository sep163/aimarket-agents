import datetime as dt

from agent5_marketing_analytics.connectors.yandex_direct import _parse_tsv


def test_parse_tsv_produces_normalized_rows():
    tsv = (
        "CampaignId\tCampaignName\tDate\tImpressions\tClicks\tCost\tConversions\n"
        "123\tТест кампания\t2026-07-06\t1000\t50\t1500.5\t5\n"
        "124\tВторая кампания\t2026-07-06\t0\t0\t0\t0\n"
    )

    rows = _parse_tsv(tsv)

    assert len(rows) == 2
    first = rows[0]
    assert first.channel == "yandex_direct"
    assert first.campaign_id == "123"
    assert first.metric_date == dt.date(2026, 7, 6)
    assert first.spend == 1500.5
    assert first.clicks == 50
    assert first.impressions == 1000
    assert first.conversions == 5
    assert first.cpl == 300.1
    assert first.ctr == 5.0

    second = rows[1]
    assert second.cpl is None  # no conversions -> no CPL
    assert second.ctr is None  # no impressions -> no CTR
