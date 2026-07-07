"""Shared data shapes used by every Agent 5 ad-platform connector."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass
class AdMetricRow:
    """One row of the normalized `ad_metrics_daily` schema (see schema.sql)."""

    channel: str
    campaign_id: str
    campaign_name: str
    metric_date: dt.date
    spend: float
    clicks: int
    impressions: int
    conversions: int

    @property
    def cpl(self) -> float | None:
        return round(self.spend / self.conversions, 2) if self.conversions > 0 else None

    @property
    def ctr(self) -> float | None:
        return round((self.clicks / self.impressions) * 100, 4) if self.impressions > 0 else None
