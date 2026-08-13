#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test the WebSocket pipeline by sending an HTML generation request."""

import asyncio
import json
import sys
import io

# Force UTF-8 output to handle unicode chars like ★
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import websockets


async def test_pipeline():
    uri = "ws://localhost:8000/ws"
    
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as ws:
        print("Connected.")
        
        # Send the HTML generation request
        message = {
            "message": "je veux un jeu de basket en un seul fichier html",
            "model": "qwen3.5:9b",
            "provider": "ollama",
            "message_id": "test-html-pipeline"
        }
        
        print(f"Sending: {json.dumps(message, indent=2)}")
        await ws.send(json.dumps(message))
        
        # Listen for events
        print("\n--- Waiting for events ---\n")
        timeout = 600  # 10 minutes
        start_time = asyncio.get_event_loop().time()
        
        files_created = []
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                print(f"\nTimeout after {timeout}s")
                break
            
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
            except asyncio.TimeoutError:
                print("No message for 30s, still waiting...")
                continue
            
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[RAW]: {raw[:200]}...")
                continue
            
            event_type = event.get("type", "unknown")
            
            if event_type == "step":
                step_type = event.get("step_type", "")
                step_status = event.get("status", "")
                title = event.get("title", "")
                print(f"[STEP] {step_type} | {step_status} | {title}")
                
            elif event_type == "token":
                content = event.get("content", "")
                if content:
                    sys.stdout.write(content)
                    sys.stdout.flush()
                    
            elif event_type == "file":
                filename = event.get("filename", "")
                content = event.get("content", "")
                language = event.get("language", "")
                print(f"\n[FILE] {filename} ({language})")
                files_created.append(filename)
                    
            elif event_type == "checkpoint":
                node = event.get("node", "")
                branch = event.get("branch", "")
                status = event.get("status", "")
                state = event.get("state", "")
                print(f"[CHECKPOINT] node={node} branch={branch} status={status}")
                
            elif event_type == "human_input":
                print(f"\n[HUMAN INPUT NEEDED] {event.get('message', '')}")
                
            elif event_type == "completed":
                print(f"\n[COMPLETED] Pipeline finished!")
                break
                
            elif event_type == "error":
                print(f"\n[ERROR] {event.get('message', '')}")
                break
                
            elif event_type == "cancelled":
                print(f"\n[CANCELLED]")
                break
                
            elif event_type == "pong":
                pass
                
            elif event_type == "metadata":
                print(f"[METADATA] {json.dumps(event, indent=2)}")
                
            elif event_type in ("status", "info"):
                msg = event.get("message", event.get("content", ""))
                if msg:
                    print(f"[{event_type.upper()}] {msg}")
                    
            elif event_type == "done":
                print(f"\n[DONE]")
                break
                
            else:
                # Print unknown events
                if event_type not in ("status",):
                    preview = json.dumps(event)[:200]
                    print(f"[{event_type}] {preview}")
        
        print(f"\n\nFiles created: {files_created}")


if __name__ == "__main__":
    asyncio.run(test_pipeline())
