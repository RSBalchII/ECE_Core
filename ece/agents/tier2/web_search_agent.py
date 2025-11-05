"""
Local Web Search Agent for the External Context Engine (ECE).

This module implements the WebSearchAgent using a completely local web search implementation
that replaces the previous Tavily API dependency with DuckDuckGo search and local scraping.
"""

import os
import httpx
import logging
from typing import Dict, List, Optional
import asyncio
import requests
from bs4 import BeautifulSoup
from readability import Document
import time
import re
from urllib.parse import urljoin, urlparse

# Import UTCP data models for manual creation
from utcp.data.utcp_manual import UtcpManual
from utcp.data.tool import Tool
from utcp_http.http_call_template import HttpCallTemplate

# Import and set up ECE logging system
try:
    from ece.common.logging_config import get_logger

    logger = get_logger("web_search")
except ImportError:
    # Fallback if logging config not available
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning("Could not import ECE logging system, using default logging")


class LocalWebScraper:
    """
    A local web scraper that can fetch, parse, and extract meaningful content from websites.
    """

    def __init__(self, timeout: int = 30, max_content_length: int = 5000):
        """
        Initialize the web scraper.

        Args:
            timeout: Request timeout in seconds
            max_content_length: Maximum length of content to extract
        """
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    def _is_valid_url(self, url: str) -> bool:
        """
        Check if the URL is valid and safe to scrape.

        Args:
            url: URL to validate

        Returns:
            True if the URL is valid, False otherwise
        """
        try:
            parsed = urlparse(url)
            return all([parsed.scheme in ["http", "https"], parsed.netloc])
        except Exception:
            return False

    def _extract_content_from_html(self, html: str, url: str) -> Dict[str, str]:
        """
        Extract meaningful content from HTML using readability and BeautifulSoup.

        Args:
            html: Raw HTML content
            url: Source URL

        Returns:
            Dictionary with extracted content
        """
        try:
            # Use readability to extract the main content
            doc = Document(html)
            title = doc.title()
            summary = doc.summary()

            # Parse with BeautifulSoup for additional processing
            soup = BeautifulSoup(html, "html.parser")

            # Get the main content
            content = BeautifulSoup(summary, "html.parser").get_text()

            # Additional cleanup
            content = content.replace("\n", " ").replace("\t", " ").strip()
            content = " ".join(content.split())  # Remove extra whitespace

            # Limit content length
            if len(content) > self.max_content_length:
                content = content[: self.max_content_length] + "... [truncated]"

            return {"title": title, "content": content, "url": url}
        except Exception as e:
            logger.error(f"Error extracting content from {url} using readability: {e}")
            # Fallback to basic extraction
            try:
                soup = BeautifulSoup(html, "html.parser")

                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()

                title = soup.title.string if soup.title else "No Title"
                content = soup.get_text()

                # Clean up the text
                content = content.replace("\n", " ").replace("\t", " ").strip()
                content = " ".join(content.split())

                # Limit content length
                if len(content) > self.max_content_length:
                    content = content[: self.max_content_length] + "... [truncated]"

                return {"title": title, "content": content, "url": url}
            except Exception as e2:
                logger.error(f"Fallback content extraction also failed for {url}: {e2}")
                return {
                    "title": "Error Processing Page",
                    "content": f"Could not extract content from {url}: {str(e2)}",
                    "url": url,
                }

    def scrape_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        Scrape a single URL and extract meaningful content.

        Args:
            url: URL to scrape

        Returns:
            Dictionary with scraped content or None if failed
        """
        if not self._is_valid_url(url):
            logger.warning(f"Invalid URL provided for scraping: {url}")
            return None

        try:
            logger.info(f"Scraping URL: {url}")

            # Make request
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            # Extract content
            content_data = self._extract_content_from_html(response.text, url)

            logger.info(
                f"Successfully scraped {len(content_data['content'])} characters from {url}"
            )
            return content_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error while scraping {url}: {e}")
            return {
                "title": "Request Error",
                "content": f"Could not fetch content from {url}: {str(e)}",
                "url": url,
            }
        except Exception as e:
            logger.error(f"Unexpected error while scraping {url}: {e}")
            return {
                "title": "Scraping Error",
                "content": f"Could not scrape {url}: {str(e)}",
                "url": url,
            }

    def scrape_urls(self, urls: List[str]) -> List[Dict[str, str]]:
        """
        Scrape multiple URLs and return their content.

        Args:
            urls: List of URLs to scrape

        Returns:
            List of dictionaries with scraped content
        """
        results = []
        for url in urls:
            result = self.scrape_url(url)
            if result:
                results.append(result)
            time.sleep(0.5)  # Be respectful to servers
        return results


class DuckDuckGoSearchEngine:
    """
    A DuckDuckGo search engine that uses DuckDuckGo to find relevant URLs and then scrapes them.
    """

    def __init__(self, scraper: LocalWebScraper):
        """
        Initialize the search engine.

        Args:
            scraper: LocalWebScraper instance to use for scraping
        """
        self.scraper = scraper
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """
        Perform a DuckDuckGo search and return scraped content from results.

        Args:
            query: Search query
            num_results: Number of results to return

        Returns:
            List of dictionaries with scraped content
        """
        logger.info(f"Performing local search for: {query}")

        try:
            # Formulate DuckDuckGo search URL
            search_url = (
                f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
            )

            # Make the search request
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()

            # Parse the search results page
            soup = BeautifulSoup(response.text, "html.parser")

            # Look for search result links
            result_links = []
            for link_element in soup.find_all("a", {"class": "result__a"}):
                href = link_element.get("href")
                if href and href.startswith("http"):
                    result_links.append(href)

                # Limit the number of links collected
                if len(result_links) >= num_results:
                    break

            # If we couldn't find links with the expected class, try alternative selectors
            if not result_links:
                for link_element in soup.find_all("a", href=True):
                    href = link_element["href"]
                    # Filter out non-web links
                    if href.startswith("http") and "duckduckgo.com" not in href:
                        result_links.append(href)

                    if len(result_links) >= num_results:
                        break

            # Limit to requested number of results
            result_links = result_links[:num_results]

            if not result_links:
                logger.warning(f"No results found for query: {query}")
                return []

            # Scrape the found URLs
            results = self.scraper.scrape_urls(result_links)
            return results

        except Exception as e:
            logger.error(f"Error performing search for query '{query}': {e}")
            # Return some fallback results based on query keywords
            return self._get_keyword_based_fallbacks(query, num_results)

    def _get_keyword_based_fallbacks(
        self, query: str, num_results: int
    ) -> List[Dict[str, str]]:
        """
        Fallback method to return some results based on query keywords.

        Args:
            query: Search query
            num_results: Number of results to return

        Returns:
            List of dictionaries with scraped content
        """
        logger.info(f"Using keyword-based fallback for query: {query}")

        # Map common query keywords to example URLs
        keyword_to_urls = {
            "python": [
                "https://docs.python.org/3/",
                "https://realpython.com/",
                "https://www.python.org/",
            ],
            "ai": [
                "https://ai.google/",
                "https://openai.com/research/",
                "https://www.deeplearning.ai/",
            ],
            "machine learning": [
                "https://scikit-learn.org/stable/",
                "https://www.tensorflow.org/",
                "https://pytorch.org/",
            ],
            "web development": [
                "https://developer.mozilla.org/en-US/",
                "https://www.w3schools.com/",
                "https://css-tricks.com/",
            ],
            "javascript": [
                "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
                "https://nodejs.org/",
                "https://www.javascript.com/",
            ],
            "react": [
                "https://reactjs.org/",
                "https://create-react-app.dev/",
                "https://www.npmjs.com/package/react",
            ],
            "news": [
                "https://www.bbc.com/news",
                "https://www.reuters.com/",
                "https://www.cnn.com/",
            ],
        }

        # Find matching keywords in the query
        query_lower = query.lower()
        matched_urls = []

        for keyword, urls in keyword_to_urls.items():
            if keyword in query_lower:
                matched_urls.extend(urls)

        # Remove duplicates while preserving order
        seen_urls = set()
        unique_urls = []
        for url in matched_urls:
            if url not in seen_urls:
                seen_urls.add(url)
                unique_urls.append(url)

        # Limit to requested number of results
        unique_urls = unique_urls[:num_results]

        if unique_urls:
            return self.scraper.scrape_urls(unique_urls)
        else:
            # Return a single result indicating no specific results found
            return [
                {
                    "title": f"No specific results found for '{query}'",
                    "content": f"Could not find specific web content for the query '{query}'. Consider trying a more specific search term or providing more context.",
                    "url": "none",
                }
            ]


class WebSearchAgent:
    """
    The WebSearchAgent provides web search capabilities using a local implementation
    that replaces the previous Tavily API dependency.
    """

    def __init__(self, model: str, api_base: str = "http://localhost:8085/v1"):
        """
        Initialize the WebSearchAgent.

        Args:
            model: The model to use for processing search results
            api_base: The API base URL for the LLM server
        """
        self.model = model
        self.api_base = api_base

        # Initialize the local web scraper and search engine
        self.scraper = LocalWebScraper(timeout=30, max_content_length=5000)
        self.search_engine = DuckDuckGoSearchEngine(self.scraper)

    async def search(
        self,
        *,
        query: str,
        system_prompt: str = "You are a helpful AI assistant that answers questions based on web search results.",
    ) -> dict:
        """
        Perform a web search using the local implementation.

        Args:
            query: The search query to perform
            system_prompt: The system prompt to use for the LLM

        Returns:
            Dictionary containing the search results and processed answer
        """
        print(f"WebSearchAgent searching for: '{query}'")
        try:
            # Perform the local search
            search_results = self.search_engine.search(query, num_results=5)

            if not search_results:
                return {
                    "success": False,
                    "answer": f"No results found for query: {query}",
                    "websites_searched": [],
                    "error": "No search results found",
                }

            # Extract content from search results
            context = " ".join([result["content"] for result in search_results])

            # Extract websites from search results
            websites_searched = [result["url"] for result in search_results]

            # Create prompt for the LLM to process the search results
            prompt = f"Based on the following context, please answer the user's query.\n\nContext:\n{context}\n\nQuery:\n{query}"

            # Prepare the payload for the LLM
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"num_gpu": 37},
            }

            # Determine the correct URL based on the API base
            if "ollama" in self.api_base:
                url = f"{self.api_base}/api/chat"
            else:
                url = f"{self.api_base}/chat/completions"

            # Make the request to the LLM
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                answer = data.get("message", {}).get("content", "")

                return {
                    "success": True,
                    "answer": answer,
                    "websites_searched": websites_searched,
                    "raw_results": search_results,
                }

        except httpx.HTTPStatusError as e:
            logging.error(
                f"HTTP error occurred: {e.response.status_code} for URL {e.request.url}"
            )
            return {
                "success": False,
                "answer": f"A web search error occurred (HTTP {e.response.status_code}).",
                "websites_searched": [],
                "error": f"HTTP error {e.response.status_code}",
            }
        except httpx.RequestError as e:
            logging.error(
                f"Request error occurred: {e.__class__.__name__} for URL {e.request.url}"
            )
            return {
                "success": False,
                "answer": "A web search error occurred (could not connect).",
                "websites_searched": [],
                "error": "Connection error",
            }
        except Exception as e:
            logging.error(
                f"An unexpected error occurred during web search: {e}", exc_info=True
            )
            return {
                "success": False,
                "answer": "An unexpected error occurred during web search.",
                "websites_searched": [],
                "error": str(e),
            }
