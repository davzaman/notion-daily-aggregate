from requests import Session
from typing import List, Dict, Optional, Tuple

# Just bookkeeping for reference
RICH_TEXT_BLOCK_TYPES = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "callout",
    "quote",
    "bulleted_list_item",
    "numbered_list_item",
    "to_do",
    "toggle",
    "code",
    "column",
    "template",
    "synced_block",
}
CAN_HAVE_CHILDREN = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "callout",
    "quote",
    "bulleted_list_item",
    "numbered_list_item",
    "to_do",
    "toggle",
    "column_list",
    "column",
    "template",
    "synced_block",
    "table",
}


class NotionClient:

    API_URL = "https://api.notion.com/v1"
    NOTION_API_VERSION = (
        "2022-06-28"  # https://developers.notion.com/reference/versioning
    )

    def __init__(self, notion_integration_token: str) -> None:
        self.headers = {
            "Authorization": f"Bearer {notion_integration_token}",
            "Notion-Version": self.NOTION_API_VERSION,
            "Content-Type": "application/json",
        }

    def get_page_obj_json(
        self, session: Session, page_name: Optional[str] = None, is_db: bool = False
    ) -> Dict:
        """
        SEARCH endpoint.
        https://developers.notion.com/reference/post-search
        Page objects are separate from their content.
        """
        payload = {}
        if page_name:
            payload["query"] = page_name
        if is_db:
            payload["filter"] = {"property": "object", "value": "database"}

        res = session.post(f"{self.API_URL}/search", headers=self.headers, json=payload)
        res.raise_for_status()
        return res.json()

    def get_db_entries(
        self, session: Session, db_id: str, sort_pairs: List[Tuple[bool, str]] = None
    ) -> List[Dict]:
        """
        DB QUERY endpoint.
        https://developers.notion.com/reference/post-database-query
        Gives you all the page objects in that database.
        Sort pairs of boolean for is_ascending, and string name of Property (table column) title to sort by.
        """
        payload = {}
        # is ascending true = index 1
        direction = ["descending", "ascending"]
        if sort_pairs:
            payload["sorts"] = [
                {"property": property_name, "direction": direction[is_ascending]}
                for is_ascending, property_name in sort_pairs
            ]

        res = session.post(
            f"{self.API_URL}/databases/{db_id}/query",
            headers=self.headers,
            json=payload,
        )
        res.raise_for_status()
        return res.json()

    def get_db_entries_from_db_name(
        self, session: Session, db_name: str, sort_pairs: List[Tuple[bool, str]] = None
    ) -> List[Dict]:
        """
        Gives you all the page objects in that database using its names instad of db_id.
        Sort pairs of boolean for is_ascending, and string name of Property (table column) title to sort by.
        """
        db = self.get_page_obj_json(session, db_name, is_db=True)
        assert len(db["results"]) == 1  # ensure DB page is just the db
        db_id = db["results"][0]["id"]
        entries = self.get_db_entries(session, db_id, sort_pairs)
        return entries["results"]

    def get_block_contents(
        self,
        session: Session,
        block_id: str,
        recursive: bool = False,
        strip_block: bool = False,
    ) -> List:
        """
        TODO: optimize to be a bit faster?
        Get all children.
        https://developers.notion.com/reference/get-block-children
        Will recursively add child nodes so you can plug it right into the api for adding blocks.
        Strip block strips all the metadata that's not necessary when you want to add new blocks using existing ones with the API.
        """
        res = session.get(
            f"https://api.notion.com/v1/blocks/{block_id}/children",
            headers=self.headers,
        )
        res.raise_for_status()

        elements = []
        for el in res.json()["results"]:
            if el["has_children"]:
                child_content = self.get_block_contents(
                    session, el["id"], recursive, strip_block
                )

                if recursive:
                    # Note: children must be added under the type content (nested), and not the high-level block for this to work properly with the API
                    # In other wordds el["children"] will NOT work/is incorrect.
                    el[el["type"]]["children"] = child_content
                else:  # Otherwise, all children are considered just high-level content and not nested
                    elements += child_content
            if strip_block:
                # Strips to only necessary key,values: object, type, and that type content
                stripped_block = {
                    "object": el["object"],
                    "type": el["type"],
                    el["type"]: el[el["type"]],
                }
                elements.append(stripped_block)
            else:
                elements.append(el)

        return elements

    def create_new_subpage(
        self,
        session: Session,
        parent_page_id: str,
        page_title: str,
        page_content: Optional[List[Dict]] = None,
    ) -> str:
        """
        CREATE PAGE endpoint.
        https://developers.notion.com/reference/post-page
        """
        payload = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "properties": {"title": {"title": [{"text": {"content": page_title}}]}},
        }
        if page_content:
            payload["children"] = page_content

        res = session.post(f"{self.API_URL}/pages", headers=self.headers, json=payload)
        res.raise_for_status()
        return res.text
