"""Directive management API endpoints.

Provides REST API for directive management:
- POST /v1/directives/reload - Reload directives from DynamoDB
- GET /v1/directives - List all active directives
- GET /v1/directives/{alpha}/{beta}/history - Get version history
"""
from fastapi import APIRouter, HTTPException

from storage.factory import get_directive_store

router = APIRouter(prefix="/v1/directives", tags=["directives"])


@router.post("/reload")
async def reload_directives():
    """Reload directives from DynamoDB.
    
    Forces a reload of all directives from DynamoDB cache.
    Useful after manual DynamoDB edits.
    
    Returns:
        Dict with status and count of active directives
    """
    try:
        store = get_directive_store()
        directives = store.load()
        return {
            "status": "reloaded",
            "active_count": len(directives)
        }
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Directive store not available: {str(e)}"
        )


@router.get("/")
async def list_directives(alpha: int = None):
    """List all active directives.
    
    Args:
        alpha: Optional alpha tier filter (0-5)
    
    Returns:
        Dict with list of active directives
    """
    try:
        store = get_directive_store()
        directives = store.get_all(alpha=alpha)
        return {
            "directives": [
                {
                    "alpha": d.alpha,
                    "beta": d.beta,
                    "version": d.version,
                    "label": d.label,
                    "content": d.content,
                    "created_by": d.created_by,
                    "created_at": d.created_at,
                }
                for d in directives
            ]
        }
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Directive store not available: {str(e)}"
        )


@router.get("/{alpha}/{beta}")
async def get_directive(alpha: int, beta: int):
    """Get a specific directive.
    
    Args:
        alpha: Alpha tier (0-5)
        beta: Beta number
    
    Returns:
        Dict with directive details
    """
    try:
        store = get_directive_store()
        directive = store.get(alpha, beta)
        
        if not directive:
            raise HTTPException(
                status_code=404,
                detail=f"Directive {alpha}-{beta} not found"
            )
        
        return {
            "alpha": directive.alpha,
            "beta": directive.beta,
            "version": directive.version,
            "label": directive.label,
            "content": directive.content,
            "created_by": directive.created_by,
            "created_at": directive.created_at,
        }
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Directive store not available: {str(e)}"
        )


@router.get("/{alpha}/{beta}/history")
async def get_directive_history(alpha: int, beta: int):
    """Get all versions of a directive (audit history).
    
    Returns the complete version history for a directive,
    including superseded versions.
    
    Args:
        alpha: Alpha tier (0-5)
        beta: Beta number
    
    Returns:
        Dict with directive ID and list of all versions
    """
    try:
        store = get_directive_store()
        versions = store.get_history(alpha, beta)
        
        if not versions:
            raise HTTPException(
                status_code=404,
                detail=f"Directive {alpha}-{beta} not found"
            )
        
        return {
            "directive": f"{alpha}-{beta}",
            "versions": [
                {
                    "version": v.version,
                    "label": v.label,
                    "content": v.content,
                    "active": v.active,
                    "created_by": v.created_by,
                    "created_at": v.created_at,
                    "superseded_at": v.superseded_at,
                }
                for v in versions
            ]
        }
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Directive store not available: {str(e)}"
        )
