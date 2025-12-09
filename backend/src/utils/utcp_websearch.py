"""
UTCP Web Search Service for ECE_Core
Simple DuckDuckGo search accessible via UTCP protocol
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import httpx
from bs4 import BeautifulSoup
import asyncio

app = FastAPI(title="UTCP Web Search Service")

class SearchRequest(BaseModel):
    query: str
    max_results: int = 5

class FetchRequest(BaseModel):
    url: str

@app.get("/")
async def root():
    return {"service": "UTCP Web Search", "status": "running"}

@app.get("/utcp")
async def utcp_manual():
    """UTCP Manual - describes available tools"""
    return {
        "service": "websearch",
        "version": "1.0.0",
        "tools": [
            {
                "name": "search_web",
                "description": "Search the web using DuckDuckGo",
                "parameters": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results to return", "default": 5}
                },
                "endpoint": "/search"
            },
            {
                "name": "fetch_url",
                "description": "Fetch and extract text content from a URL",
                "parameters": {
                    "url": {"type": "string", "description": "URL to fetch"}
                },
                "endpoint": "/fetch"
            }
        ]
    }

@app.post("/search")
@app.get("/search")
async def search_web(query: str = None, search_term: str = None, max_results: int = 5):
    """
    Search DuckDuckGo HTML (no API key required).
    Returns list of results with title, snippet, and URL.
    Accepts query or search_term parameter.
    """
    # Accept either 'query' or 'search_term' parameter name
    search_query = query or search_term
    if not search_query:
        raise HTTPException(status_code=400, detail="Missing search query (query or search_term parameter required)")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # DuckDuckGo HTML search
            response = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": search_query},
                headers={"User-Agent": "Mozilla/5.0"}
            )
            response.raise_for_status()
            
            # Parse results
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for result in soup.select('.result')[:max_results]:
                title_elem = result.select_one('.result__a')
                snippet_elem = result.select_one('.result__snippet')
                
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get('href', '')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet
                    })
            
            return {
                "success": True,
                "query": search_query,
                "results": results,
                "count": len(results)
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.post("/fetch")
async def fetch_url(url: str):
    """
    Fetch a URL and extract readable text content.
    Returns cleaned text for LLM consumption.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            response.raise_for_status()
            
            # Parse HTML and extract text
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get text
            text = soup.get_text(separator='\n', strip=True)
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Truncate if too long (max 10k chars for LLM context)
            if len(text) > 10000:
                text = text[:10000] + "\n\n[Content truncated...]"
            
            return {
                "success": True,
                "url": url,
                "content": text,
                "length": len(text)
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8007)
