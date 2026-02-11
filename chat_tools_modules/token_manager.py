"""
OAuth Token Manager for Twitch

Handles token validation, refresh, and initial authorization flow.
"""

import asyncio
import aiohttp
import json
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Tuple, Union
from pathlib import Path
from logger_setup import setup_logger

logger = setup_logger(__name__)


class TokenManager:
    """Manages Twitch OAuth tokens with automatic refresh."""
    
    TWITCH_OAUTH_URL = "https://id.twitch.tv/oauth2/authorize"
    TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
    TWITCH_VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
    REDIRECT_URI = "http://localhost:8080"
    
    # Required scopes for EventSub chat
    REQUIRED_SCOPES = [
        'user:read:chat',
        'user:bot',
        'user:write:chat'
    ]
    
    def __init__(self, client_id: str, client_secret: str, config_path: Union[str, Path]):
        """Initialize token manager.
        
        Args:
            client_id: Twitch application client ID
            client_secret: Twitch application client secret
            config_path: Path to config file for saving tokens (str or Path object)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.config_path = config_path
        self.config_path = config_path
    
    async def validate_token(self, access_token: str) -> Optional[dict]:
        """Validate a token and return its details.
        
        Args:
            access_token: The OAuth access token to validate
            
        Returns:
            Dict with token details if valid, None if invalid
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.TWITCH_VALIDATE_URL,
                    headers={'Authorization': f'OAuth {access_token}'}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.debug(f"Token valid, expires in {data.get('expires_in')} seconds")
                        return data
                    else:
                        logger.warning(f"Token validation failed: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return None
    
    async def refresh_token(self, refresh_token: str) -> Optional[Tuple[str, str]]:
        """Refresh an OAuth token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            Tuple of (new_access_token, new_refresh_token) if successful, None otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token
                }
                
                async with session.post(self.TWITCH_TOKEN_URL, data=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        new_access = result['access_token']
                        new_refresh = result['refresh_token']
                        logger.info("Successfully refreshed OAuth token")
                        return (new_access, new_refresh)
                    else:
                        error_text = await resp.text()
                        logger.error(f"Token refresh failed ({resp.status}): {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None
    
    async def ensure_valid_token(
        self, 
        access_token: str, 
        refresh_token: Optional[str] = None
    ) -> Optional[Tuple[str, Optional[str]]]:
        """Ensure token is valid, refreshing if needed.
        
        Args:
            access_token: Current access token
            refresh_token: Current refresh token (optional)
            
        Returns:
            Tuple of (access_token, refresh_token) if valid/refreshed, None if failed
        """
        # First validate current token
        validation = await self.validate_token(access_token)
        
        if validation:
            # Check if token is about to expire (less than 1 hour)
            expires_in = validation.get('expires_in', 0)
            if expires_in > 3600:
                logger.debug("Token is valid and not expiring soon")
                return (access_token, refresh_token)
            else:
                logger.info(f"Token expires in {expires_in} seconds, attempting refresh...")
        else:
            logger.warning("Token is invalid, attempting refresh...")
        
        # Token is invalid or expiring, try to refresh
        if refresh_token:
            result = await self.refresh_token(refresh_token)
            if result:
                new_access, new_refresh = result
                # Save new tokens to config
                await self._save_tokens_to_config(new_access, new_refresh)
                return (new_access, new_refresh)
        
        logger.error("Could not refresh token - refresh token missing or invalid")
        return None
    
    async def _save_tokens_to_config(self, access_token: str, refresh_token: str):
        """Save updated tokens to config file.
        
        Args:
            access_token: New access token
            refresh_token: New refresh token
        """
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            config['oauth_token'] = access_token
            config['refresh_token'] = refresh_token
            
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.debug("Saved updated tokens to config")
        except Exception as e:
            logger.error(f"Failed to save tokens to config: {e}")
    
    def start_oauth_flow(self) -> str:
        """Start OAuth authorization flow.
        
        Opens browser for user to authorize, then waits for callback.
        
        Returns:
            Authorization code from callback
        """
        # Build authorization URL
        scopes = ' '.join(self.REQUIRED_SCOPES)
        auth_url = (
            f"{self.TWITCH_OAUTH_URL}"
            f"?client_id={self.client_id}"
            f"&redirect_uri={self.REDIRECT_URI}"
            f"&response_type=code"
            f"&scope={scopes}"
        )
        
        # Holder for the authorization code
        auth_code = [None]
        auth_error = [None]
        
        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                # Parse the callback URL
                query = parse_qs(urlparse(self.path).query)
                if 'code' in query:
                    auth_code[0] = query['code'][0]
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"""
                        <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                        <h1 style="color: #9146FF;">Authorization Successful!</h1>
                        <p>You can close this window and return to the application.</p>
                        </body></html>
                    """)
                elif 'error' in query:
                    # Capture error
                    error = query['error'][0]
                    error_desc = query.get('error_description', ['Unknown error'])[0]
                    auth_error[0] = f"{error}: {error_desc}"
                    logger.error(f"OAuth error: {auth_error[0]}")
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(f"""
                        <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                        <h1 style="color: red;">Authorization Failed</h1>
                        <p><strong>Error:</strong> {error}</p>
                        <p>{error_desc}</p>
                        <p>Please close this window and check your Twitch app settings.</p>
                        </body></html>
                    """.encode())
                else:
                    auth_error[0] = "No authorization code or error received"
                    self.send_response(400)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"""
                        <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                        <h1 style="color: orange;">Invalid Callback</h1>
                        <p>No authorization data received. Please try again.</p>
                        </body></html>
                    """)
            
            def log_message(self, format, *args):
                pass  # Suppress logs
        
        # Start local server for callback
        server = HTTPServer(('localhost', 8080), CallbackHandler)
        
        # Open browser
        logger.info("Opening browser for OAuth authorization...")
        webbrowser.open(auth_url)
        
        # Wait for callback (with timeout)
        logger.info("Waiting for authorization callback...")
        server.timeout = 120  # 2 minute timeout
        server.handle_request()
        
        if auth_code[0]:
            logger.info("Received authorization code")
            return auth_code[0]
        elif auth_error[0]:
            logger.error(f"OAuth authorization failed: {auth_error[0]}")
            return None
        else:
            logger.error("Did not receive authorization code (timeout or no response)")
            return None
    
    async def exchange_code_for_tokens(self, code: str) -> Optional[Tuple[str, str]]:
        """Exchange authorization code for access and refresh tokens.
        
        Args:
            code: Authorization code from OAuth callback
            
        Returns:
            Tuple of (access_token, refresh_token) if successful, None otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'code': code,
                    'grant_type': 'authorization_code',
                    'redirect_uri': self.REDIRECT_URI
                }
                
                async with session.post(self.TWITCH_TOKEN_URL, data=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        access_token = result['access_token']
                        refresh_token = result['refresh_token']
                        logger.info("Successfully exchanged code for tokens")
                        return (access_token, refresh_token)
                    else:
                        error_text = await resp.text()
                        logger.error(f"Token exchange failed ({resp.status}): {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Token exchange error: {e}")
            return None
    
    async def do_full_oauth_flow(self) -> Optional[Tuple[str, str]]:
        """Perform complete OAuth flow from start to finish.
        
        Returns:
            Tuple of (access_token, refresh_token) if successful, None otherwise
        """
        logger.info("Starting OAuth flow...")
        
        # Step 1: Get authorization code
        code = self.start_oauth_flow()
        if not code:
            logger.error("Failed to get authorization code")
            return None
        
        # Step 2: Exchange code for tokens
        result = await self.exchange_code_for_tokens(code)
        if not result:
            logger.error("Failed to exchange code for tokens")
            return None
        
        access_token, refresh_token = result
        
        # Step 3: Save tokens to config
        await self._save_tokens_to_config(access_token, refresh_token)
        
        logger.info("OAuth flow completed successfully")
        return (access_token, refresh_token)
