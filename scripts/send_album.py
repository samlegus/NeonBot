#!/usr/bin/env python3
"""
Telegram Album Sender - Wrapper script for sending media groups via Telegram Bot API
Usage: python send_album.py <chat_id> <image1> [image2] [image3] ...
"""

import os
import sys
import json
import requests
from pathlib import Path

# Load token from env file (create .env in parent directory with TELEGRAM_BOT_TOKEN=your_token_here)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN not found in .env file or environment")
    sys.exit(1)

API_BASE = f"https://api.telegram.org/bot{TOKEN}"


def send_album(chat_id, image_paths):
    """Send multiple images as a Telegram album/media group"""
    
    if len(image_paths) > 10:
        print("Error: Telegram allows max 10 images per album")
        sys.exit(1)
    
    if len(image_paths) < 2:
        print("Error: Need at least 2 images for an album (use regular send for single images)")
        sys.exit(1)
    
    # Build media JSON array
    media = []
    files = {}
    
    for i, img_path in enumerate(image_paths):
        img_path = Path(img_path)
        if not img_path.exists():
            print(f"Error: Image not found: {img_path}")
            sys.exit(1)
        
        # Open file for multipart upload
        files[f"photo{i}"] = open(img_path, 'rb')
        
        media_item = {
            "type": "photo",
            "media": f"attach://photo{i}"
        }
        if i == 0:
            media_item["caption"] = img_path.name  # Caption only on first image
        media.append(media_item)
    
    # Send request
    url = f"{API_BASE}/sendMediaGroup"
    data = {
        "chat_id": chat_id,
        "media": json.dumps(media)  # Proper JSON array as string
    }
    
    try:
        response = requests.post(url, data=data, files=files)
        result = response.json()
        
        if result.get('ok'):
            print(f"✅ Album sent successfully! {len(image_paths)} images")
            return True
        else:
            print(f"❌ Error: {result.get('description', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False
    finally:
        # Close all file handles
        for f in files.values():
            f.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python send_album.py <chat_id> <image1> [image2] ...")
        print("Example: python send_album.py 142810831 img1.png img2.png img3.png")
        sys.exit(1)
    
    chat_id = sys.argv[1]
    image_paths = sys.argv[2:]
    
    success = send_album(chat_id, image_paths)
    sys.exit(0 if success else 1)
