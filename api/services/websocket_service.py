# api/services/websocket_service.py
import asyncio
import json
from typing import Dict, List, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

from utils.logger import get_logger

logger = get_logger("websocket_service")

class ConnectionManager:
    """Manage WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Store active connections by user ID and connection ID
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        # Store request IDs that each connection is subscribed to
        self.request_subscriptions: Dict[str, Set[str]] = {}
        # Store user subscriptions to request IDs
        self.user_subscriptions: Dict[str, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str) -> str:
        """Accept a WebSocket connection and store it"""
        await websocket.accept()
        
        # Generate a unique connection ID
        connection_id = f"{user_id}_{id(websocket)}"
        
        # Initialize user's connections if not exists
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
            self.user_subscriptions[user_id] = set()
        
        # Store the connection
        self.active_connections[user_id][connection_id] = websocket
        self.request_subscriptions[connection_id] = set()
        
        logger.info(f"WebSocket connection established: {connection_id}")
        
        return connection_id
    
    async def disconnect(self, connection_id: str, user_id: str) -> None:
        """Remove a WebSocket connection"""
        if user_id in self.active_connections and connection_id in self.active_connections[user_id]:
            # Remove the connection
            del self.active_connections[user_id][connection_id]
            
            # Clean up empty user entries
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
            
            # Clean up subscriptions
            if connection_id in self.request_subscriptions:
                del self.request_subscriptions[connection_id]
            
            logger.info(f"WebSocket connection closed: {connection_id}")
    
    async def subscribe(self, connection_id: str, user_id: str, request_id: str) -> None:
        """Subscribe a connection to updates for a specific request ID"""
        if connection_id in self.request_subscriptions:
            self.request_subscriptions[connection_id].add(request_id)
        
        if user_id in self.user_subscriptions:
            self.user_subscriptions[user_id].add(request_id)
            
        logger.info(f"Connection {connection_id} subscribed to request {request_id}")
    
    async def unsubscribe(self, connection_id: str, user_id: str, request_id: str) -> None:
        """Unsubscribe a connection from updates for a specific request ID"""
        if connection_id in self.request_subscriptions:
            self.request_subscriptions[connection_id].discard(request_id)
        
        # Check if any other connections from this user are still subscribed
        still_subscribed = False
        if user_id in self.active_connections:
            for conn_id in self.active_connections[user_id]:
                if conn_id != connection_id and request_id in self.request_subscriptions.get(conn_id, set()):
                    still_subscribed = True
                    break
        
        # If no other connections are subscribed, remove from user subscriptions
        if not still_subscribed and user_id in self.user_subscriptions:
            self.user_subscriptions[user_id].discard(request_id)
            
        logger.info(f"Connection {connection_id} unsubscribed from request {request_id}")
    
    async def broadcast_to_subscribers(self, request_id: str, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connections subscribed to a request ID"""
        # Find all users subscribed to this request
        for user_id, subscriptions in self.user_subscriptions.items():
            if request_id in subscriptions:
                # Find all connections for this user
                for connection_id, websocket in self.active_connections.get(user_id, {}).items():
                    # Check if this connection is subscribed
                    if request_id in self.request_subscriptions.get(connection_id, set()):
                        try:
                            await websocket.send_json(message)
                        except Exception as e:
                            logger.error(f"Error sending message to {connection_id}: {str(e)}")
    
    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connections for a user"""
        if user_id in self.active_connections:
            for connection_id, websocket in self.active_connections[user_id].items():
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to {connection_id}: {str(e)}")
    
    async def send_personal_message(self, connection_id: str, user_id: str, message: Dict[str, Any]) -> None:
        """Send a message to a specific connection"""
        if user_id in self.active_connections and connection_id in self.active_connections[user_id]:
            try:
                await self.active_connections[user_id][connection_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending personal message to {connection_id}: {str(e)}")


# Create a global connection manager
manager = ConnectionManager()


async def handle_websocket_connection(websocket: WebSocket, user_id: str):
    """Handle an individual WebSocket connection"""
    connection_id = await manager.connect(websocket, user_id)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connection_established",
            "connection_id": connection_id
        })
        
        # Handle messages from the client
        while True:
            try:
                # Receive message
                message = await websocket.receive_json()
                
                # Process message based on type
                if message.get("type") == "subscribe":
                    request_id = message.get("request_id")
                    if request_id:
                        await manager.subscribe(connection_id, user_id, request_id)
                        await websocket.send_json({
                            "type": "subscribed",
                            "request_id": request_id
                        })
                
                elif message.get("type") == "unsubscribe":
                    request_id = message.get("request_id")
                    if request_id:
                        await manager.unsubscribe(connection_id, user_id, request_id)
                        await websocket.send_json({
                            "type": "unsubscribed",
                            "request_id": request_id
                        })
                
                elif message.get("type") == "ping":
                    # Simple ping message to keep connection alive
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": message.get("timestamp")
                    })
                    
                else:
                    # Unknown message type
                    await websocket.send_json({
                        "type": "error",
                        "message": "Unknown message type"
                    })
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
                
    except WebSocketDisconnect:
        await manager.disconnect(connection_id, user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await manager.disconnect(connection_id, user_id)


async def send_status_update(request_id: str, status: str, progress: float, result: Optional[Dict] = None, error: Optional[str] = None):
    """Send a status update to all subscribers of a request"""
    message = {
        "type": "status_update",
        "request_id": request_id,
        "status": status,
        "progress": progress
    }
    
    if result:
        message["result"] = result
        
    if error:
        message["error"] = error
    
    await manager.broadcast_to_subscribers(request_id, message)


async def send_story_completed(user_id: str, story_id: str, story_data: Dict[str, Any]):
    """Send a notification that a story has been completed"""
    message = {
        "type": "story_completed",
        "story_id": story_id,
        "story": story_data
    }
    
    await manager.broadcast_to_user(user_id, message)