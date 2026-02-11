"""Quick script to check OAuth token scopes and validity."""

import asyncio
import aiohttp
import json

async def check_token():
    """Check what scopes the current OAuth token has."""
    
    # Load config
    with open('config/chat_tools_config.json', 'r') as f:
        config = json.load(f)
    
    token = config['oauth_token']
    client_id = config['client_id']
    
    print(f"Checking token for client_id: {client_id}")
    print(f"Token: {token[:10]}...")
    print()
    
    # Validate token with Twitch API
    headers = {
        'Authorization': f'Bearer {token}',
        'Client-Id': client_id
    }
    
    async with aiohttp.ClientSession() as session:
        # Check token validation
        async with session.get(
            'https://id.twitch.tv/oauth2/validate',
            headers={'Authorization': f'OAuth {token}'}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print("✓ Token is valid!")
                print(f"  User ID: {data.get('user_id')}")
                print(f"  Login: {data.get('login')}")
                print(f"  Client ID: {data.get('client_id')}")
                print(f"  Expires in: {data.get('expires_in')} seconds")
                print(f"\n  Scopes granted:")
                scopes = data.get('scopes', [])
                if scopes:
                    for scope in scopes:
                        print(f"    - {scope}")
                else:
                    print("    (none)")
                
                print("\n  Required scopes for EventSub Chat:")
                required = ['user:read:chat', 'user:bot', 'user:write:chat']
                for req in required:
                    status = "✓" if req in scopes else "✗ MISSING"
                    print(f"    {status} {req}")
                
                missing = [r for r in required if r not in scopes]
                if missing:
                    print(f"\n❌ Missing required scopes: {', '.join(missing)}")
                    print("\nYou need to regenerate your OAuth token with these scopes:")
                    print("https://twitchtokengenerator.com/")
                    print("or use Twitch CLI: twitch token -u -s 'user:read:chat user:bot user:write:chat'")
                else:
                    print("\n✓ All required scopes present!")
                    
            else:
                error_text = await resp.text()
                print(f"✗ Token validation failed (status {resp.status})")
                print(f"  Response: {error_text}")
                print("\nToken might be expired or invalid. Generate a new one at:")
                print("https://twitchtokengenerator.com/")

if __name__ == "__main__":
    asyncio.run(check_token())
