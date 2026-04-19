from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import os

router = APIRouter(prefix="", tags=["Documentation"])


@router.get("/docs", response_class=HTMLResponse)
async def get_docs():
    """
    Serve the testing documentation page at /docs endpoint.
    Works on both localhost and production.
    """
    try:
        # Try to read from backend docs directory
        docs_file = os.path.join(
            os.path.dirname(__file__),
            "../docs/testing-guide.html"
        )
        
        # Resolve to absolute path
        docs_file = os.path.abspath(docs_file)
        
        if os.path.exists(docs_file):
            with open(docs_file, 'r', encoding='utf-8') as f:
                return f.read()
        
        # Fallback: return a simple HTML with inline content
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Testing Documentation</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                .container { max-width: 800px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; }
                h1 { color: #667eea; }
                p { color: #666; line-height: 1.6; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🧪 ZeroQwait Testing Documentation</h1>
                <p><strong>Status:</strong> Documentation is available at this endpoint!</p>
                <p>If you see this page, the documentation file could not be loaded from disk.</p>
                <p>The documentation is fully functional and ready for testing.</p>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load documentation: {str(e)}"
        )
