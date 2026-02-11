"""
Twitch Bot Module

Encapsulates TwitchIO bot implementation with EventSub WebSocket support.
Handles Twitch authentication, chat message subscriptions, and message sending.
"""

import asyncio
import time
from typing import Optional, Any, Callable
from collections import deque
from twitchio.ext import commands
from twitchio import eventsub, ChatMessage
import aiohttp
from logger_setup import setup_logger

logger = setup_logger(__name__)


class TwitchChatBot(commands.Bot):
    """Twitch chat bot with EventSub WebSocket and custom message sending.
    
    This bot uses:
    - OAuth2 token authentication (not IRC passwords)
    - Twitch Helix API for sending messages (more reliable than IRC)
    - EventSub WebSocket for receiving chat messages
    - Separate event loop in dedicated thread
    
    Current Limitations (TODO):
    - Single OAuth token limits available scopes
    - Missing dual OAuth (bot + broadcaster tokens) for advanced features
    - Cannot access subscriber lists, polls, predictions, hype trains without broadcaster token
    """
    
    def __init__(
        self,
        config: dict,
        on_ready_callback: Callable[[], None],
        on_message_callback: Callable[[str, str], None],
        on_error_callback: Callable[[str], None],
        command_handler: Optional[Callable[[Any], Any]] = None,
        activity_tracker: Optional[deque] = None
    ):
        """Initialize the Twitch bot.
        
        Args:
            config: Configuration dict with client_id, client_secret, bot_id, oauth_token, channel
            on_ready_callback: Called when bot successfully connects
            on_message_callback: Called for each chat message (username, content)
            on_error_callback: Called on bot errors
            command_handler: Optional async function to handle commands
            activity_tracker: Optional deque to track chat activity timestamps
        """
        super().__init__(
            token=config['oauth_token'],
            client_id=config['client_id'],
            client_secret=config['client_secret'],
            bot_id=config['bot_id'],
            prefix='!'
        )
        
        self.config = config
        self.oauth_token = config['oauth_token']
        self.broadcaster_id: Optional[str] = None
        self._setup_successful = False
        
        # Callbacks
        self.on_ready_callback = on_ready_callback
        self.on_message_callback = on_message_callback
        self.on_error_callback = on_error_callback
        self.command_handler = command_handler
        self.activity_tracker = activity_tracker
        
        logger.debug(f"Bot initialized for channel: {config['channel']}")
    
    async def send_message(self, message: str) -> bool:
        """Send a message to the configured channel using Twitch Helix API.
        
        Uses the /helix/chat/messages endpoint instead of IRC for reliability.
        Requires broadcaster_id to be set (done in setup_hook).
        
        Args:
            message: The message text to send
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.broadcaster_id:
            logger.error("Broadcaster ID not set - cannot send message")
            return False
        
        url = "https://api.twitch.tv/helix/chat/messages"
        headers = {
            "Authorization": f"Bearer {self.oauth_token}",
            "Client-Id": self.config['client_id'],
            "Content-Type": "application/json"
        }
        payload = {
            "broadcaster_id": self.broadcaster_id,
            "sender_id": self.config['bot_id'],
            "message": message
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        logger.debug(f"Message sent successfully: {message[:50]}...")
                        return True
                    else:
                        error_text = await resp.text()
                        logger.error(f"Failed to send message: {resp.status} - {error_text}")
                        return False
        except Exception as e:
            logger.error(f"Exception sending message: {e}")
            return False
    
    async def setup_hook(self):
        """Called before connecting - subscribe to chat messages via EventSub WebSocket.
        
        Fetches channel information and subscribes to channel.chat.message events.
        Stores broadcaster_id for message sending.
        
        TODO: Implement dual OAuth token support for bot and streamer accounts
        TODO: Currently using single bot account token which limits channel data access
        TODO: Bot token should be used for chat operations (current behavior)
        TODO: Streamer token should be used for:
        TODO:   - ChannelSubscribeSubscription
        TODO:   - ChannelPredictionBeginSubscription  
        TODO:   - ChannelPollBeginSubscription
        TODO:   - HypeTrainBeginSubscription
        TODO:   - ChannelPointsRedemptionAddSubscription
        TODO:   - ChannelCheerSubscription (bits)
        TODO: Bot must be moderator in streamer's channel for moderator:read:followers scope
        """
        logger.debug(f"setup_hook called")
        
        channel_name = self.config['channel']
        logger.debug(f"Fetching channel info for: {channel_name}")
        
        try:
            users = await self.fetch_users(logins=[channel_name])
            if users:
                broadcaster = users[0]
                self.broadcaster_id = broadcaster.id
                logger.debug(f"Found broadcaster: {broadcaster.name} (ID: {broadcaster.id})")
                
                # Subscribe to chat messages via EventSub WebSocket
                payload = eventsub.ChatMessageSubscription(
                    broadcaster_user_id=broadcaster.id,
                    user_id=self.config['bot_id']
                )
                
                await self.subscribe_websocket(
                    payload=payload,
                    as_bot=True
                )
                logger.info(f"Successfully subscribed to chat messages via EventSub")
                self._setup_successful = True
                
                # TODO: Add additional EventSub subscriptions when dual OAuth implemented
                
            else:
                error_msg = f"Could not find channel: {channel_name}"
                logger.error(error_msg)
                self.on_error_callback(error_msg)
        except Exception as e:
            error_msg = f"Failed to subscribe to chat: {e}"
            logger.error(error_msg)
            self.on_error_callback(error_msg)
            import traceback
            traceback.print_exc()
    
    async def event_ready(self):
        """Called when bot is ready and connected."""
        logger.info(f"Bot ready event triggered for channel #{self.config['channel']}")
        
        # Only call success callback if setup completed successfully
        if self._setup_successful:
            self.on_ready_callback()
        else:
            logger.warning("Bot ready event triggered but setup was not successful")
    
    async def event_message(self, message: ChatMessage):
        """Handle incoming chat messages from EventSub.
        
        Args:
            message: ChatMessage object with .chatter and .text attributes
        """
        logger.debug(f"Message event received")
        
        try:
            username = message.chatter.name
            content = message.text
            logger.debug(f"Chat: {username}: {content}")
            
            # Track chat activity if tracker provided
            if self.activity_tracker is not None:
                self.activity_tracker.append(time.time())
            
            # Call message callback
            self.on_message_callback(username, content)
            
            # Handle commands if handler provided
            if self.command_handler:
                await self.command_handler(message)
        
        except Exception as e:
            logger.error(f"Failed to process message: {e}")
            import traceback
            traceback.print_exc()
    
    async def event_error(self, payload):
        """Handle errors from twitchio.
        
        Args:
            payload: Error payload with .error and .listener attributes
        """
        if hasattr(payload, 'error'):
            actual_error = payload.error
            logger.error(f"Actual error: {actual_error}")
            error_msg = str(actual_error)
        else:
            error_msg = str(payload)
            logger.error(f"Bot error: {payload}")
        
        if hasattr(payload, 'listener'):
            logger.error(f"Failed listener: {payload.listener}")
        
        self.on_error_callback(error_msg)
