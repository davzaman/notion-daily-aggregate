from typing import List, Dict
from collections import deque
from requests import Session
import os
from tqdm import tqdm

from NotionClient import NotionClient


def _create_date_block(page_object: Dict) -> Dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {
                    # https://developers.notion.com/reference/rich-text#date-mentions
                    "type": "mention",
                    "mention": {
                        "type": "date",
                        # https://developers.notion.com/reference/property-value-object#date-property-values
                        "date": {
                            "start": page_object["created_time"],
                            "time_zone": "America/Los_Angeles",
                        },
                    },
                    "annotations": {
                        "bold": False,
                        "italic": False,
                        "strikethrough": False,
                        "underline": False,
                        "code": False,
                        "color": "default",
                    },
                },
            ],
            "color": "default",
        },
    }


def _create_new_page_content(contents_per_project: Dict[str, List[Dict]]) -> List[Dict]:
    # Create new page with all amassed info for each project
    # Structure is as a toggled heading with all the gathered blocks under each relevant project
    new_page_content = []
    for project_id, project_contents in contents_per_project.items():
        if project_contents:
            new_page_content.append(
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        # https://developers.notion.com/reference/rich-text
                        "rich_text": [
                            {
                                "type": "mention",
                                "mention": {
                                    "type": "page",
                                    "page": {"id": project_id},
                                },
                                "annotations": {
                                    "bold": False,
                                    "italic": False,
                                    "strikethrough": False,
                                    "underline": False,
                                    "code": False,
                                    "color": "default",
                                },
                                # "plain_text": "Autopopulus",
                                # "href": "https://www.notion.so/b85c071b41ce4ff4aad7c483cda47987",
                            },
                        ],
                        "color": "default",
                        "is_toggleable": True,
                        "children": project_contents,
                    },
                }
            )
    return new_page_content


if __name__ == "__main__":
    # TODO: how do update this on new days instead of rerunning it on everything?
    # TODO: how to delete empty entries (but have content because of the template)
    # TODO: created synced_blocks to original comments instead of copying and pasting everything over (API limitation as of 1/3/23)

    secret = os.environ["NOTION_INTEGRATION_SECRET"]
    nc = NotionClient(secret)
    with Session() as s:
        # Grab all daily page objects from DB descending
        # when they are added again later they will also be descending
        daily_entries = nc.get_db_entries_from_db_name(
            s, "Daily SCRUM", [(False, "Created")]
        )
        # Grab ids from each project page object
        project_page_ids = [
            project["id"] for project in nc.get_db_entries_from_db_name(s, "Projects")
        ]

        # Maps project id to all the amassed blocks across all daily entries
        # We will build this up in a moment
        contents_per_project: Dict[str, List[Dict]] = {
            project_page_id: [] for project_page_id in project_page_ids
        }

        # Go through each daily entry and grab all mentions of any relevant project from the project DB
        for page_obj in tqdm(daily_entries, unit="entry"):
            # Get elements from page id and dive in
            blocks = nc.get_block_contents(
                s, page_obj["id"], recursive=True, strip_block=True
            )

            has_entry_for_this_day = {
                project_id: False for project_id in project_page_ids
            }

            # BFS through the page contents because any mentions will also grab children content (therefore not DFS)
            q = deque(blocks)
            while q:
                pulled_block = q.popleft()
                content = pulled_block[pulled_block["type"]]
                # Grab the whole block if part of the text mentions a project
                if "rich_text" in content:
                    for text_entry in content["rich_text"]:
                        # Looks for text_entry[mention][page][id] if it exists
                        # Empty string if it doesn't exist, which will be ignored
                        mention_page_id = (
                            text_entry.get("mention", {})
                            .get("page", {})
                            .get("id", None)
                        )
                        # If there is a mention add the whole block under the contents for that project
                        if mention_page_id in contents_per_project:
                            if not has_entry_for_this_day[mention_page_id]:
                                date_block = _create_date_block(page_obj)
                                contents_per_project[mention_page_id].append(date_block)
                                has_entry_for_this_day[mention_page_id] = True
                            contents_per_project[mention_page_id].append(pulled_block)
                if "children" in content:
                    for child in content["children"]:
                        q.append(child)

        new_page_content = _create_new_page_content(contents_per_project)
        parent_id = nc.get_page_obj_json(s, "Home")["results"][0]["id"]
        nc.create_new_subpage(
            s, parent_id, "Project Thought Aggregate", new_page_content
        )
