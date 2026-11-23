"""Official MCP SDK 2.0 stdio & streamable HTTP transport with open dynamic skills, resources & intent resolution."""
import asyncio
import base64
import inspect
import json
import os
import sys
import io
import anyio
from pathlib import Path
from jsonschema import Draft202012Validator
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from core import Catalog

catalog = Catalog(os.environ.get('GPHOTOS_VISION_DATA') or Path(__file__).parent/'v2'/'data')

DESCRIPTIONS = {
    # --- LAYER 1: GOOGLE PHOTOS CONTEXT & INGESTION ---
    'list_photo_profiles': 'LAYER 1: List configured Google Photos profiles (name & profile_id).',
    'select_photo_profile': 'LAYER 1: Select active Google Photos profile.',
    'create_photo_profile': 'LAYER 1: Create a new Google Photos profile folder (arg: name).',
    'delete_photo_profile': 'LAYER 1: Delete a Google Photos profile and clean up its local folder (arg: profile_id).',
    'open_photo_profile': 'LAYER 1: Launch persistent Chrome for the given Google Photos profile so user/agent can access photos.google.com.',
    'start_photo_scan': 'LAYER 1: Start background metadata scan of Google Photos grid (persists photo/video IDs, labels, URLs in SQLite).',
    'stop_photo_scan': 'LAYER 1: Pause background Google Photos scan.',
    'get_photo_inventory': 'LAYER 1: Return exact Google Photos inventory counts (photos, videos, albums) for a profile.',
    'list_photo_albums': 'LAYER 1 (CONTEXT): List all Google Photos albums with titles, item counts, and URLs (set refresh=true to rescan live).',
    'get_album_items': 'LAYER 1 (CONTEXT): Inspect exact items inside a specific Google Photos album URL.',
    'understand_photos_library': 'LAYER 1 (CONTEXT BLUEPRINT): Analyze total albums, album naming patterns (phone numbers, STT codes, referrals, topics) and media stats so AI understands business context BEFORE classifying inside Eagle.',
    'prefetch_all_photo_thumbnails': 'LAYER 1 (INGEST): Fast parallel download (10x concurrent, HD w1000-no) of missing Google Photos previews.',
    'sync_all_photos_to_eagle': 'LAYER 1 -> 2 (ZERO-DROP PULL): Pulls 100% of ALL Google Photos photos & videos into Eagle DAM without dropping any items, preserving real album context and Google Photos links.',

    # --- LAYER 2: EAGLE-FIRST AI VISION, VIDEO STORYBOARD & CLASSIFICATION ---
    'get_eagle_libraries': 'LAYER 2: Discover current and recent Eagle DAM libraries.',
    'select_eagle_library': 'LAYER 2: Select target Eagle DAM library path.',
    'get_eagle_folder_tree': 'LAYER 2 (EAGLE CONTEXT): Read the complete existing folder hierarchy of the Eagle library with live item counts before classifying.',
    'scan_eagle_library': 'LAYER 2 (EAGLE AUDIT): Audit total photos/videos, AI_Vision_Verified progress, unreviewed remaining count, and real album context coverage.',
    'get_eagle_review_sheet': 'LAYER 2 (AI VISION BATCH): Read up to 24 unreviewed items directly from Eagle DAM as ONE numbered Contact Sheet JPEG (ImageContent) + metadata.',
    'get_eagle_item_detail': 'LAYER 2 (AI VISION ZOOM): Return ONE high-res zoomed JPEG (up to 1200px, ImageContent) of a specific Eagle item + full metadata + chronological neighbors within 35 min (before/after) to read small text or verify details.',
    'get_video_storyboard': 'LAYER 2 (VIDEO VISION): Extract up to 9 evenly-spaced frames from a real local video (.mp4/.mov) in Eagle into ONE 3x3 timestamped Storyboard JPEG (ImageContent) + Faster-Whisper Vietnamese speech & ASMR >4.5kHz intel.',
    'apply_eagle_vision_decisions': 'LAYER 2 (CLEAN OVERWRITE WRITE): Apply AI Vision classifications cleanly (supports standard categories OR dynamic folder_names for any industry), preserves real customer album folders & tags, and marks AI_Vision_Verified.',
    'search_eagle_items': 'LAYER 2 (CONTENT RETRIEVAL): Search classified Eagle items directly by keyword, tag, folder, kind (photo/video), and min_star to pull assets for posts, TikTok, or CapCut.',
    'cluster_treatment_sessions': 'LAYER 2 (TIMELINE): Fast 0.05s 35-minute temporal session clustering for Before/In-Process/After journeys.',

    # --- META: INTENT ROUTING, TAXONOMY & DYNAMIC SKILLS ---
    'resolve_user_intent': 'META: Analyze user query to determine target domain, recommended skill, and optimal MCP tool sequence.',
    'list_taxonomy_projects': 'META: List business industry taxonomies (Spa, Dental, F&B, Gym, etc.).',
    'switch_taxonomy_project': 'META: Switch active industry taxonomy and sync folder structure to Eagle.',
    'register_taxonomy_project': 'META: Dynamically register a new business industry taxonomy without restarting.',
    'list_available_skills': 'META: List all registered AI agent skills.',
    'get_skill_guide': 'META: Read full markdown guide of a skill (e.g. universal-media-classifier).',
    'register_skill': 'META: Dynamically register or update a skill SKILL.md.',
}


def schema(name):
    properties, required = {}, []
    for p in inspect.signature(getattr(catalog,name)).parameters.values():
        if p.name in ('budget','limit','offset','size','extra_budget','max_steps','max_items','threshold','max_gap_minutes','batch_size','concurrency','max_dim','frames','min_star'):
            value={'type':'integer'}
        elif p.name in ('asset_ids','crop'):
            value={'type':'array','items':{'type':'string' if p.name=='asset_ids' else 'number'}}
        elif p.name=='decisions':
            value={'type':'array','items':{'type':'object'}}
        elif p.name in ('refresh','only_cached','only_unreviewed'):
            value={'type':'boolean'}
        else:
            value={'type':'string'}
        if p.default is inspect.Parameter.empty:
            required.append(p.name)
        properties[p.name]=value
    return {'type':'object','properties':properties,'required':required,'additionalProperties':False}


async def list_tools(context, params):
    return types.ListToolsResult(tools=[types.Tool(name=n,description=d,input_schema=schema(n)) for n,d in DESCRIPTIONS.items()])


async def call_tool(context, params):
    try:
        if params.name not in DESCRIPTIONS:
            raise ValueError(f'Unknown tool: {params.name}')
        Draft202012Validator(schema(params.name)).validate(params.arguments or {})
        result=await asyncio.to_thread(getattr(catalog,params.name), **(params.arguments or {}))
        picture=None
        if isinstance(result,tuple):
            result,picture=result
        content=[types.TextContent(type='text',text=json.dumps(result,ensure_ascii=False))]
        if picture:
            content.append(types.ImageContent(type='image',mime_type='image/jpeg',data=base64.b64encode(picture).decode()))
        return types.CallToolResult(content=content,is_error=False)
    except Exception as e:
        return types.CallToolResult(content=[types.TextContent(type='text',text=str(e)[:1000])],is_error=True)


RESOURCES = [
    types.Resource(
        uri="resource://skills/universal-media-classifier",
        name="universal-media-classifier-guide",
        title="Universal Media Classifier Skill Guide (SKILL.md)",
        description="Comprehensive guide, invariants, 6-step workflow, and CapCut annotations for classifying photos and vertical videos.",
        mime_type="text/markdown"
    ),
    types.Resource(
        uri="resource://taxonomy/active",
        name="active-taxonomy-config",
        title="Active Business Taxonomy Configuration",
        description="Configured content pillars, Eagle folder mappings, and keyword matching rules for the active industry domain.",
        mime_type="application/json"
    ),
    types.Resource(
        uri="resource://eagle/tree-structure",
        name="eagle-tree-specification",
        title="Eagle DAM 2-Branch Tree Specification",
        description="Strict hierarchy specification: Photo Studio (100% photos) vs Video Reels & TikTok (100% vertical clips).",
        mime_type="application/json"
    ),
    types.Resource(
        uri="resource://skills/registry",
        name="skills-registry",
        title="Registered Agent Skills Catalog",
        description="Catalog of all available skills installed across shared and local repositories.",
        mime_type="application/json"
    )
]

async def list_resources(context, params):
    return types.ListResourcesResult(resources=RESOURCES)


async def read_resource(context, params):
    uri = str(params.uri)
    from intent_engine import IntentEngine
    if uri == "resource://skills/universal-media-classifier":
        content = IntentEngine.get_skill_content("universal-media-classifier") or ""
        return types.ReadResourceResult(contents=[types.TextResourceContents(uri=uri, mime_type="text/markdown", text=content)])
    elif uri == "resource://taxonomy/active":
        from taxonomy_manager import TaxonomyManager
        tax = TaxonomyManager().get_active_project()
        return types.ReadResourceResult(contents=[types.TextResourceContents(uri=uri, mime_type="application/json", text=json.dumps(tax, ensure_ascii=False, indent=2))])
    elif uri == "resource://eagle/tree-structure":
        tree_spec = {
            "root_folders": [
                {
                    "name": "📸 1. KHO HÌNH ẢNH (Photo Studio)",
                    "rule": "100% Still Photos only. No videos allowed.",
                    "subfolders": [
                        "⭐ 1.1 Ảnh 5 Sao Hero (Quảng Cáo & Bìa Bài Viết)",
                        "🔄 1.2 Cặp Ảnh Trước & Sau (Before - After)",
                        "💆‍♀️ 1.3 Thao Tác KTV & Bác Sĩ (Quy Trình Chuẩn Y Khoa)",
                        "🏥 1.4 Cơ Sở Vật Chất & Máy Công Nghệ Cao",
                        "👥 1.5 Hồ Sơ Khách Hàng (Case Studies Theo Ca)"
                    ]
                },
                {
                    "name": "🎬 2. KHO VIDEO CLIPS (Video Reels & TikTok)",
                    "rule": "100% Vertical 9:16 Video Clips only.",
                    "subfolders": [
                        "🔥 2.1 Video Hook 3s Viral (Giữ Chân Người Xem)",
                        "🗣️ 2.2 Video Có Lời Thoại (Đã Bóc Phụ Đề Whisper AI)",
                        "🎧 2.3 Video Âm Thanh ASMR (Dụng Cụ Spa >4.5kHz)",
                        "💆‍♀️ 2.4 Video B-Roll Thao Tác KTV (Cận Cảnh Liệu Trình)",
                        "🔇 2.5 Video Câm (Footage Cần Lồng Nhạc BGM)",
                        "👥 2.6 Video Theo Khách Hàng (Reels Khách Hàng)"
                    ]
                }
            ],
            "deterministic_file_contract": "Disk filename == metadata.json['name'] + '.' + ext. Illegal characters removed."
        }
        return types.ReadResourceResult(contents=[types.TextResourceContents(uri=uri, mime_type="application/json", text=json.dumps(tree_spec, ensure_ascii=False, indent=2))])
    elif uri == "resource://skills/registry":
        skills = IntentEngine.list_skills()
        return types.ReadResourceResult(contents=[types.TextResourceContents(uri=uri, mime_type="application/json", text=json.dumps(skills, ensure_ascii=False, indent=2))])
    else:
        raise ValueError(f"Unknown resource URI: {uri}")


PROMPTS = [
    types.Prompt(
        name="media_classification_workflow",
        title="Universal Media Classification Workflow",
        description="Standard 6-step pipeline to classify images and vertical videos into Eagle DAM with multi-industry taxonomy.",
        arguments=[
            types.PromptArgument(name="user_goal", description="The classification task or customer query", required=True),
            types.PromptArgument(name="industry_domain", description="Optional business domain (e.g. khaihoan_skincare, fb_culinary)", required=False)
        ]
    ),
    types.Prompt(
        name="treatment_session_clustering",
        title="Temporal Treatment Session Clustering Workflow",
        description="Group photo and video bursts into 35-minute cohesive customer sessions with Before/In-Process/After tagging.",
        arguments=[
            types.PromptArgument(name="max_gap_minutes", description="Time window in minutes (default: 35)", required=False)
        ]
    ),
    types.Prompt(
        name="video_hook_asmr_scrubbing",
        title="Video 9:16 Deep Scrubbing, Hook 3s & ASMR Analysis",
        description="Simulate human 5s/10s timeline scrubbing, extract Whisper speech and >4.5kHz ASMR spectrum.",
        arguments=[
            types.PromptArgument(name="video_path", description="Relative or absolute path of the vertical video clip", required=True)
        ]
    )
]

async def list_prompts(context, params):
    return types.ListPromptsResult(prompts=PROMPTS)


async def get_prompt(context, params):
    name = params.name
    args = params.arguments or {}
    if name == "media_classification_workflow":
        goal = args.get("user_goal", "Phân loại tư liệu vào Eagle DAM")
        domain = args.get("industry_domain", "khaihoan_skincare")
        msg = (
            f"Bạn là Chuyên Gia Quản Trị Dữ Liệu Đa Phương Thức (Media Intelligence & DAM Coordinator Agent).\n"
            f"Nhiệm vụ: {goal}\n"
            f"Ngành mục tiêu: {domain}\n\n"
            f"Hãy thực thi theo đúng quy trình chuẩn:\n"
            f"1. Gọi resolve_user_intent(user_query=...) để nhận diện intent và kế hoạch công cụ tối ưu.\n"
            f"2. Gọi switch_taxonomy_project(project_id='{domain}') nếu cần kích hoạt ngành nghề.\n"
            f"3. Gọi cluster_treatment_sessions(max_gap_minutes=35) để gom cụm chuỗi thời gian (0.05s, 0% RAM).\n"
            f"4. Gọi filter_burst_duplicates để lọc ảnh 5 sao Hero.\n"
            f"5. Đối với video dọc 9:16, gọi analyze_video_asset để tua nhanh 5s/10s bóc keyframes, phụ đề Whisper và ASMR >4.5kHz.\n"
            f"6. Gọi reorganize_eagle_tree để đảm bảo sơ đồ cây 2 nhánh rạch ròi 100%."
        )
        return types.GetPromptResult(
            description="Media classification prompt",
            messages=[types.PromptMessage(role="user", content=types.TextContent(type="text", text=msg))]
        )
    elif name == "treatment_session_clustering":
        gap = args.get("max_gap_minutes", "35")
        msg = (
            f"Hãy thực hiện gom cụm phiên điều trị bằng thuật toán thời gian với cửa sổ {gap} phút:\n"
            f"1. Gọi cluster_treatment_sessions(max_gap_minutes={gap}).\n"
            f"2. Kiểm tra các phiên có điểm neo khách hàng VIP và phân chia Before/In-Process/After.\n"
            f"3. Đồng bộ sơ đồ cây qua reorganize_eagle_tree."
        )
        return types.GetPromptResult(
            description="Session clustering prompt",
            messages=[types.PromptMessage(role="user", content=types.TextContent(type="text", text=msg))]
        )
    elif name == "video_hook_asmr_scrubbing":
        vpath = args.get("video_path", "")
        msg = (
            f"Hãy phân tích video dọc 9:16 tại '{vpath}':\n"
            f"1. Gọi analyze_video_asset(video_path='{vpath}').\n"
            f"2. Kiểm tra keyframes tại các mốc 00:01, 00:03, 00:08 để xác định Hook 3s Viral.\n"
            f"3. Kiểm tra phụ đề tiếng Việt từ Faster-Whisper và phổ tần số âm thanh ASMR >4.5kHz.\n"
            f"4. Soạn thảo Annotation hướng dẫn CapCut cho Editor."
        )
        return types.GetPromptResult(
            description="Video scrubbing prompt",
            messages=[types.PromptMessage(role="user", content=types.TextContent(type="text", text=msg))]
        )
    else:
        raise ValueError(f"Unknown prompt name: {name}")


SYSTEM_INSTRUCTIONS = """
Universal Media Intelligence & Eagle DAM Coordinator Agent (Official MCP Gateway).
Role: Autonomous inspection, scrubbing, acoustic analysis, and categorization of photos & vertical 9:16 videos into Eagle DAM.

CORE ARCHITECTURAL INVARIANTS:
1. STRICT 2-BRANCH TREE:
   - Root 1: '📸 1. KHO HÌNH ẢNH (Photo Studio)': 100% Still Photos only. Never put videos here.
   - Root 2: '🎬 2. KHO VIDEO CLIPS (Video Reels & TikTok)': 100% Vertical 9:16 video footage. Never put photos here.
2. DETERMINISTIC FILE CONTRACT:
   - Disk file name strictly matches metadata.json["name"] + "." + metadata.json["ext"].
   - Illegal characters [:*?"<>|/\\] must be stripped. Mismatch causes broken thumbnail eye-icon in Eagle.
3. EXTENSIBLE INTENT & SKILL ROUTING:
   - For ANY user query, call 'resolve_user_intent(user_query=...)' to get the optimal tool call sequence, matching skill, and architectural invariants.
   - To inspect skills or rules, read 'resource://skills/universal-media-classifier' or call 'get_skill_guide'.
   - To register new skills or business industries, call 'register_skill' or 'register_taxonomy_project'.
4. ZERO-RAM HIGH EFFICIENCY:
   - Never load heavy deep learning models (no local CLIP, no optical flow) on user laptops.
   - Use 'cluster_treatment_sessions' (0.05s, 0% RAM) for patient/customer journey timeline grouping.
   - Use 'filter_burst_duplicates' (Laplacian sharpness) to pick 5-star Hero photos without AI tokens.
"""

server = Server(
    'gphotos-content-vision',
    version='2.2.0',
    instructions=SYSTEM_INSTRUCTIONS,
    on_list_tools=list_tools,
    on_call_tool=call_tool,
    on_list_resources=list_resources,
    on_read_resource=read_resource,
    on_list_prompts=list_prompts,
    on_get_prompt=get_prompt
)


async def main():
    reader_stream = anyio.wrap_file(io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8'))
    writer_stream = anyio.wrap_file(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True))
    async with stdio_server(reader_stream, writer_stream) as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == '__main__':
    asyncio.run(main())
