# ece_client.py

import httpx
from rich.console import Console
from rich.markdown import Markdown
import configparser
import os
import json
import asyncio

def get_orchestrator_url():
    """
    Get the Orchestrator URL from environment variables or a config file.
    """
    url = os.getenv('ECE_ORCHESTRATOR_URL')
    if url:
        return url
    
    config = configparser.ConfigParser()
    if os.path.exists('config.ini'):
        config.read('config.ini')
        if 'client' in config and 'orchestrator_url' in config['client']:
            return config['client']['orchestrator_url']
            
    return "http://localhost:8000/process_prompt"

async def main():
    """
    Main asynchronous function to run the ECE client.
    """
    orchestrator_url = get_orchestrator_url()
    base_url = orchestrator_url.replace("/process_prompt", "")
    print(f"DEBUG: get_orchestrator_url() returned: {orchestrator_url}")
    console = Console()
    console.print(f"[bold green]Connecting to ECE Orchestrator at:[/bold green] {orchestrator_url}")
    console.print("Type 'exit' or 'quit' to terminate the client.")

    async with httpx.AsyncClient(timeout=None) as client:
        while True:
            try:
                prompt_text = console.input("[bold cyan]ECE>[/bold cyan] ")

                if prompt_text.lower() in ['exit', 'quit']:
                    break
                
                if not prompt_text:
                    continue

                params = {"prompt": prompt_text}
                
                console.print("\n[yellow]Sending request to Orchestrator...[/yellow]")
                
                response = await client.get(orchestrator_url, params=params)
                if response.status_code != 200:
                    error_detail = await response.aread()
                    console.print(f"[bold red]HTTP Error: {response.status_code} - {error_detail.decode()}[/bold red]")
                    continue

                response_data = response.json()
                console.print("[bold green]Response from Orchestrator:[/bold green]")
                console.print(response_data.get("response"))

                if "analysis_id" in response_data.get("response", ""):
                    analysis_id = response_data.get("response").split("is ")[-1].replace(".","")
                    console.print(f"\n[yellow]Polling for analysis result with ID: {analysis_id}...[/yellow]")
                    
                    polling_url = f"{base_url}/get_analysis_result"
                    polling_params = {"analysis_id": analysis_id}
                    
                    max_polls = 60 # Poll for a maximum of 2 minutes
                    for _ in range(max_polls):
                        await asyncio.sleep(2)
                        polling_response = await client.get(polling_url, params=polling_params)
                        if polling_response.status_code == 200:
                            polling_data = polling_response.json()
                            if polling_data.get("status") == "complete":
                                console.print("\n[bold green]Analysis complete:[/bold green]")
                                console.print(polling_data.get("response"))
                                break
                        else:
                            console.print(f"[bold red]Error polling for result: {polling_response.status_code}[/bold red]")
                            break
                    else:
                        console.print("[bold red]Analysis timed out.[/bold red]")


            except httpx.RequestError as e:
                console.print(f"\n[bold red]Connection Error:[/bold red] Could not connect to the ECE Orchestrator. Please ensure the ECE is running.")
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nClient terminated.")
