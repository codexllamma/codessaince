import sys
import asyncio
import logging
from pathlib import Path
import uuid
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

BACKEND_DIR = Path(__file__).parent.resolve()
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ocr_engine.executor import run_ephemeral_ocr
from services.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, filename="mcp_server.log")
app = Server("vaanireach-pipeline")

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="trigger_e2e_pipeline",
            description="Trigger the end-to-end VaaniReach video generation pipeline directly.",
            inputSchema={
                "type": "object",
                "properties": {
                    "primary_lang": {
                        "type": "string",
                        "description": "The 2-letter language code of the local test PDF (e.g., 'hi', 'ta', 'en')"
                    },
                    "voice_id": {
                        "type": "string",
                        "description": "The Neural voice ID to use (e.g., 'hi-IN-MadhurNeural')"
                    },
                    "avatar_id": {
                        "type": "string",
                        "description": "The visual presenter ID to use (e.g., 'female_saree_raw')"
                    }
                },
                "required": ["primary_lang", "voice_id", "avatar_id"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name != "trigger_e2e_pipeline":
        raise ValueError(f"Unknown tool: {name}")

    primary_lang = arguments.get("primary_lang")
    voice_id = arguments.get("voice_id")
    avatar_id = arguments.get("avatar_id")
    
    logging.info(f"Triggering E2E pipeline for lang: {primary_lang}, voice: {voice_id}, avatar: {avatar_id}")
    
    pdf_path = BACKEND_DIR / "ocr_engine" / f"extensive_test_{primary_lang}.pdf"
    if not pdf_path.exists():
        pdf_path = BACKEND_DIR / "ocr_engine" / "complex_layout_test.pdf"
        
    ocr_result = run_ephemeral_ocr(str(pdf_path), lang=primary_lang)
    raw_text = ocr_result.get("raw_text", "")
    
    if not raw_text:
        return [types.TextContent(type="text", text="Failed to extract text from PDF.")]
        
    job_id = f"mcp_job_{uuid.uuid4().hex[:6]}"
    
    result = run_pipeline(
        raw_text=raw_text,
        job_id=job_id,
        lang=primary_lang,
        voice_id=voice_id,
        avatar_id=avatar_id,
    )
    
    return [types.TextContent(type="text", text=f"Pipeline completed successfully. Video saved to: {result.video_path}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
