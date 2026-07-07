"""Google Sheets integration for Agent 4.

Two tabs in one spreadsheet:
  - "Leads": every qualified lead gets appended as a row here.
  - "Links": the no-code admin panel. One row per channel with the referral
    link to send once qualification finishes. To change a link or add a new
    channel (avito, max, instagram, ...), just edit/add a row - no code changes.
"""

from __future__ import annotations

import datetime as dt
import logging

import gspread
from google.oauth2.service_account import Credentials

from .conversation import LeadData

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DEFAULT_REFERRAL_LINK = "[ссылка]"


class LeadsSheet:
    """Lazily connects to Google Sheets on first actual use.

    Deliberately does not touch the network in `__init__`: if the service
    account file or sheet id are still placeholders (e.g. right after a fresh
    deploy, before real credentials are in `.env`), the bot process can still
    start and talk to Telegram - it only fails, gracefully, the first time
    someone actually finishes the qualification flow.
    """

    def __init__(self, service_account_file: str, sheet_id: str) -> None:
        self._service_account_file = service_account_file
        self._sheet_id = sheet_id
        self._spreadsheet = None

    def _get_spreadsheet(self):
        if self._spreadsheet is None:
            credentials = Credentials.from_service_account_file(self._service_account_file, scopes=SCOPES)
            client = gspread.authorize(credentials)
            self._spreadsheet = client.open_by_key(self._sheet_id)
        return self._spreadsheet

    def get_referral_link(self, channel: str) -> str:
        # Covers the worksheet lookup AND get_all_records() below - a
        # malformed header row (blank/duplicate column name) in the "Links"
        # tab raises from get_all_records(), not just from the lookup, and
        # this must never crash the qualification flow either way.
        try:
            worksheet = self._get_spreadsheet().worksheet("Links")
            for row in worksheet.get_all_records():
                if str(row.get("channel", "")).strip().lower() == channel.lower():
                    return str(row.get("referral_link") or DEFAULT_REFERRAL_LINK)
        except Exception:
            logger.exception("Could not read the 'Links' worksheet, falling back to default link")
        return DEFAULT_REFERRAL_LINK

    def append_lead(
        self,
        *,
        channel: str,
        chat_id: int,
        username: str,
        lead: LeadData,
        referral_link: str,
    ) -> None:
        worksheet = self._get_spreadsheet().worksheet("Leads")
        worksheet.append_row(
            [
                dt.datetime.utcnow().isoformat(),
                channel,
                str(chat_id),
                username or "",
                lead.contact,
                lead.role,
                lead.marketplaces,
                lead.category,
                lead.experience,
                lead.turnover,
                lead.team_size,
                lead.pain_points,
                referral_link,
            ],
            value_input_option="USER_ENTERED",
        )
