import os
import json
import requests

def main(params):
    # Log the raw incoming payload for debugging
    print("=== Incoming params ===")
    print(json.dumps(params, indent=2, default=str))
    
    # --- Extract COS notification from various payload formats ---
    notification = {}
    
    # Format 1: IBM Event Notifications webhook envelope (most common)
    # EN sends: { "notification": { "data": { "notification": { "object_name": ... } } } }
    en_data = (params.get("notification", {})
                     .get("data", {})
                     .get("notification", {}))
    if en_data.get("object_name"):
        notification = en_data
        print("Detected Format 1: Event Notifications webhook envelope")
    
    # Format 2: Direct / manual test format
    # curl sends: { "data": { "notification": { "object_name": ... } } }
    if not notification.get("object_name"):
        notification = params.get("data", {}).get("notification", {})
        if notification.get("object_name"):
            print("Detected Format 2: Direct test format")
    
    # Format 3: Alternative EN format (sometimes EN sends this)
    # { "data": { "object_name": ... } }
    if not notification.get("object_name"):
        data = params.get("data", {})
        if data.get("object_name"):
            notification = data
            print("Detected Format 3: Alternative EN format")
    
    # Format 4: Top-level notification
    # { "object_name": ... }
    if not notification.get("object_name"):
        if params.get("object_name"):
            notification = params
            print("Detected Format 4: Top-level format")
    
    object_key = notification.get("object_name", "")
    bucket     = notification.get("bucket_name", "")
    
    print(f"Extracted object_key={object_key}, bucket={bucket}")
    
    # If we still don't have an object_key, log the full payload structure
    if not object_key:
        print("ERROR: Could not extract object_name from payload")
        print("Payload keys:", list(params.keys()))
        if "notification" in params:
            print("notification keys:", list(params["notification"].keys()))
        if "data" in params:
            print("data keys:", list(params["data"].keys()))
        return {
            "status": "error",
            "reason": "Could not extract object_name from payload",
            "payload_keys": list(params.keys())
        }
    
    if object_key.endswith("/"):
        print(f"Skipping directory marker: {object_key}")
        return {"status": "skipped", "reason": "directory marker"}
    
    langflow_url     = os.environ.get("LANGFLOW_URL")
    langflow_api_key = os.environ.get("LANGFLOW_API_KEY")
    component_id     = os.environ.get("COS_COMPONENT_ID", "IBMCOSFile")
    
    if not langflow_url or not langflow_api_key:
        print("ERROR: Missing LANGFLOW_URL or LANGFLOW_API_KEY environment variables")
        return {
            "status": "error",
            "reason": "Missing required environment variables"
        }
    
    print(f"Calling Langflow: {langflow_url}")
    print(f"Component ID: {component_id}")
    
    payload = {
        "input_value": f"New file uploaded: {object_key}",
        "tweaks": {
            component_id: {
                "cos_object_key": object_key
            }
        }
    }
    
    try:
        resp = requests.post(
            langflow_url,
            json=payload,
            headers={
                "x-api-key": langflow_api_key,
                "Content-Type": "application/json"
            },
            timeout=30
        )
        
        print(f"Langflow response status: {resp.status_code}")
        print(f"Langflow response: {resp.text[:500]}")  # First 500 chars
        
        return {
            "status": "triggered",
            "object_key": object_key,
            "bucket": bucket,
            "langflow_status": resp.status_code,
            "langflow_response": resp.text[:200]  # Truncate for response
        }
    except Exception as e:
        print(f"ERROR calling Langflow: {str(e)}")
        return {
            "status": "error",
            "reason": f"Failed to call Langflow: {str(e)}",
            "object_key": object_key,
            "bucket": bucket
        }

# Made with Bob
