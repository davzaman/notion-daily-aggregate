from requests import Session
from dateutil import parser
from datetime import datetime
import os

from NotionClient import NotionClient


if __name__ == "__main__":
    """
    Assumes that none of the pages in the daily entries are automatically generated and then never touched again.
    """

    secret = os.environ["NOTION_INTEGRATION_SECRET"]
    nc = NotionClient(secret)
    with Session() as s:
        # Grab all daily page objects from DB in any order
        daily_entries = nc.get_db_entries_from_db_name(s, "Daily SCRUM")

        # delete pages never touched since their creation, excluding "today"
        # deletes unused templates (technically have content) but are "empty"
        delete_responses = [
            nc.delete_block(s, entry["id"])
            for entry in daily_entries
            if entry["last_edited_time"] == entry["created_time"]
            and parser.parse(entry["created_time"]).date() != datetime.today().date()
        ]
