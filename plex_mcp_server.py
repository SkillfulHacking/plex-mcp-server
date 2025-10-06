import argparse
import uvicorn # type: ignore
from anyio import ClosedResourceError
from starlette.applications import Starlette # type: ignore
from starlette.routing import Mount, Route # type: ignore
from mcp.server import Server # type: ignore
from mcp.server.sse import SseServerTransport # type: ignore
from starlette.requests import Request # type: ignore
from starlette.responses import JSONResponse # type: ignore

# Import the main mcp instance from modules
from modules import mcp, connect_to_plex

# Import all tools to ensure they are registered with MCP
# Library module functions
from modules.library import (
    library_list,
    library_get_stats,
    library_refresh,
    library_scan,
    library_get_details,
    library_get_recently_added,
    library_get_contents
)
# User module functions
from modules.user import (
    user_search_users,
    user_get_info,
    user_get_on_deck,
    user_get_watch_history,
    user_get_statistics
)
# Search module functions
from modules.sessions import (
    sessions_get_active,
    sessions_get_media_playback_history
)
# Server module functions
from modules.server import (
    server_get_plex_logs,
    server_get_info,
    server_get_bandwidth,
    server_get_current_resources,
    server_get_butler_tasks,
    server_get_alerts,
    server_run_butler_task
)
# Playlist module functions
from modules.playlist import (
    playlist_list,
    playlist_get_contents,
    playlist_create,
    playlist_delete,
    playlist_add_to,
    playlist_remove_from,
    playlist_edit,
    playlist_upload_poster,
    playlist_copy_to_user
)
# Collection module functions
from modules.collection import (
    collection_list,
    collection_create,
    collection_add_to,
    collection_remove_from,
    collection_edit
)
# Media module functions
from modules.media import (
    media_search,
    media_get_details,
    media_edit_metadata,
    media_delete,
    media_get_artwork,
    media_set_artwork,
    media_list_available_artwork  
)  
# Client module functions
from modules.client import (
    client_list, 
    client_get_details, 
    client_get_timelines,
    client_get_active, 
    client_start_playback, 
    client_control_playback,
    client_navigate, 
    client_set_streams
)

def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    sse = SseServerTransport("/messages/")
    
    async def sse_asgi(scope, receive, send):
        async with sse.connect_sse(scope, receive, send) as (r, w):
            await mcp_server.run(r, w, mcp_server.create_initialization_options())

    async def safe_messages(scope, receive, send):
        # guard: only POST is allowed here
        if scope.get("type") != "http" or scope.get("method") != "POST":
            await JSONResponse({"error": "method not allowed"}, status_code=405)(scope, receive, send)
            return
        try:
            await sse.handle_post_message(scope, receive, send)
        except ClosedResourceError:
            await JSONResponse({"error": "session closed"}, status_code=410)(scope, receive, send)
            
# Sub-app mounted at /sse so the final paths are:
    #   /sse                (SSE open)
    #   /sse/messages/      (POST messages)
    sse_app = Starlette(
        routes=[
            # NOTE: Route(...) is correct here because this endpoint is Request->Response;
            # Starlette will call our ASGI handler with (request), which wraps scope/recv/send.
            Route("/", endpoint=sse_asgi, methods=["GET", "POST"]),
            Mount("/messages/", app=safe_messages),
        ]
    )

    # TOP-LEVEL: only mount the sub-app at /sse. DO NOT also mount /sse/messages/ at root.
    return Starlette(
        debug=debug,
        routes=[Mount("/sse", app=sse_app)],
    )

if __name__ == "__main__":
    # Setup command line arguments
    parser = argparse.ArgumentParser(description='Run Plex MCP Server')
    parser.add_argument('--transport', choices=['stdio', 'sse'], default='sse', 
                        help='Transport method to use (stdio or sse)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (for SSE)')
    parser.add_argument('--port', type=int, default=3001, help='Port to listen on (for SSE)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Initialize and run the server
    print(f"Starting Plex MCP Server with {args.transport} transport...")
    print("Set PLEX_URL and PLEX_TOKEN environment variables for connection")
    
    if args.transport == 'stdio':
        # Run with stdio transport (original method)
        mcp.run(transport='stdio')
    else:
        # Ensure PMS connection & tool registration are ready
        connect_to_plex()
        # Run with SSE transport
        mcp_server = mcp._mcp_server  # Access the underlying MCP server
        starlette_app = create_starlette_app(mcp_server, debug=args.debug)
        print(f"Starting SSE server on http://{args.host}:{args.port}")
        print("Access the SSE endpoint at /sse")
        uvicorn.run(starlette_app, host=args.host, port=args.port)
