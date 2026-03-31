import os
import re
from notion_client import Client

def get_rich_text(rich_text_array):
    text = ""
    for rt in rich_text_array:
        plain_text = rt.get("plain_text", "")
        annotations = rt.get("annotations", {})
        
        if annotations.get("code"):
            plain_text = f"`{plain_text}`"
        else:
            if annotations.get("bold"):
                plain_text = f"**{plain_text}**"
            if annotations.get("italic"):
                plain_text = f"*{plain_text}*"
            if annotations.get("strikethrough"):
                plain_text = f"~~{plain_text}~~"
                
        link = rt.get("href")
        if link:
            plain_text = f"[{plain_text}]({link})"
            
        text += plain_text
    return text

def parse_blocks(notion_client, blocks, indent=""):
    md_content = ""
    for block in blocks:
        block_type = block.get("type")
        block_data = block.get(block_type, {})
        has_children = block.get("has_children", False)
        
        rich_text = block_data.get("rich_text", [])
        text = get_rich_text(rich_text)
        
        if block_type == "paragraph":
            md_content += f"{indent}{text}\n\n"
        elif block_type == "heading_1":
            md_content += f"{indent}# {text}\n\n"
        elif block_type == "heading_2":
            md_content += f"{indent}## {text}\n\n"
        elif block_type == "heading_3":
            md_content += f"{indent}### {text}\n\n"
        elif block_type == "bulleted_list_item":
            md_content += f"{indent}- {text}\n"
        elif block_type == "numbered_list_item":
            md_content += f"{indent}1. {text}\n"
        elif block_type == "to_do":
            checked = "x" if block_data.get("checked") else " "
            md_content += f"{indent}- [{checked}] {text}\n"
        elif block_type == "toggle":
            md_content += f"{indent}<details><summary>{text}</summary>\n\n"
        elif block_type == "code":
            language = block_data.get("language", "")
            md_content += f"{indent}```{language}\n{text}\n{indent}```\n\n"
        elif block_type == "quote":
            quoted = "\n".join([f"{indent}> {line}" for line in text.split("\n")])
            md_content += f"{quoted}\n\n"
        elif block_type == "divider":
            md_content += f"{indent}---\n\n"
        else:
            if text:
                md_content += f"{indent}{text}\n\n"
        
        if has_children:
            try:
                # Fetch children recursive
                children = notion_client.blocks.children.list(block_id=block["id"]).get("results", [])
                
                if block_type in ["bulleted_list_item", "numbered_list_item", "to_do"]:
                    md_content += parse_blocks(notion_client, children, indent=indent + "    ")
                elif block_type == "toggle":
                    md_content += parse_blocks(notion_client, children, indent=indent + "  ")
                    md_content += f"{indent}</details>\n\n"
                else:
                    md_content += parse_blocks(notion_client, children, indent=indent + "    ")
            except Exception as e:
                print(f"Error fetching children for block {block['id']}: {e}")

    return md_content

def fetch_page_markdown(access_token, page_id):
    """지정된 토큰과 페이지 ID로 데이터를 마크다운 변환하여 돌려줍니다."""
    notion = Client(auth=access_token)
    
    # 1. Fetch metadata (Title)
    try:
        page = notion.pages.retrieve(page_id=page_id)
        props = page.get("properties", {})
        
        title = "Untitled Page"
        for prop_name, prop_data in props.items():
            if prop_data.get("type") == "title":
                title_arr = prop_data.get("title", [])
                title = get_rich_text(title_arr) if title_arr else "Untitled"
                break
    except Exception as e:
        print(f"Failed to fetch page metadata: {e}")
        return None, f"# Error\n페이지를 찾을 수 없거나 열람이 허가되지 않았습니다. 상세 오류: {e}"

    # 2. Extract blocks
    blocks = []
    has_more = True
    next_cursor = None
    
    try:
        while has_more:
            response = notion.blocks.children.list(
                block_id=page_id,
                start_cursor=next_cursor
            )
            blocks.extend(response.get("results", []))
            has_more = response.get("has_more", False)
            next_cursor = response.get("next_cursor")
            
        markdown_body = parse_blocks(notion, blocks)
        final_md = f"# {title}\n\n{markdown_body}"
        return title, final_md
    except Exception as e:
        return title, f"Error parsing content: {e}"
