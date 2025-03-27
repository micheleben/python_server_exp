# UDP Communication Protocol
# Shared file to be imported by both server and clients

import json
import datetime
from enum import Enum, auto
from typing import Dict, Any, List, Tuple, Union, Optional

class MessageType(Enum):
    """Defines the types of messages in the protocol"""
    STATUS = auto()         # Server status broadcast
    COMMAND = auto()        # Command message
    RESPONSE = auto()       # Response to a command
    ERROR = auto()          # Error message
    INFO = auto()           # Informational message

class CommandType(Enum):
    """Defines available commands in the protocol"""
    PING = auto()           # Simple ping command
    GET_STATUS = auto()     # Request server status
    SET_PARAMETER = auto()  # Set a parameter on server
    GET_CLIENTS = auto()    # Get list of connected clients
    SHUTDOWN = auto()       # Request shutdown
    CUSTOM = auto()         # Custom command with arbitrary data

# Protocol specification - defines commands and their expected argument types
PROTOCOL_SPEC = {
    CommandType.PING: {
        "args": {},
        "description": "Simple ping to check connectivity"
    },
    CommandType.GET_STATUS: {
        "args": {},
        "description": "Request current server status"
    },
    CommandType.SET_PARAMETER: {
        "args": {
            "param_name": str,
            "param_value": object
        },
        "description": "Set a parameter on the server"
    },
    CommandType.GET_CLIENTS: {
        "args": {},
        "description": "Get list of connected clients"
    },
    CommandType.SHUTDOWN: {
        "args": {
            "reason": str
        },
        "description": "Request server or client shutdown"
    },
    CommandType.CUSTOM: {
        "args": {
            "action": str,
            "data": object
        },
        "description": "Custom command with arbitrary data"
    }
}

def create_message(msg_type: MessageType, msg_id: int = None, **kwargs) -> Dict[str, Any]:
    """
    Create a message according to the protocol
    
    Args:
        msg_type: Type of message
        msg_id: Optional message ID (generated if not provided)
        **kwargs: Additional fields for the message
        
    Returns:
        Dict representing the message
    """
    # Generate message ID if not provided
    if msg_id is None:
        # Use timestamp-based ID if not provided
        timestamp = datetime.datetime.now().timestamp()
        msg_id = int(timestamp * 1000)  # milliseconds since epoch
        
    # Base message structure
    message = {
        "message_type": msg_type.name,
        "message_id": msg_id,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # Add additional fields
    message.update(kwargs)
    
    return message

def create_status_message(state: str, details: Dict[str, Any] = None, msg_id: int = None) -> Dict[str, Any]:
    """Create a status broadcast message"""
    return create_message(
        MessageType.STATUS,
        msg_id=msg_id,
        state=state,
        details=details or {}
    )

def create_command_message(command: CommandType, command_args: Dict[str, Any] = None, 
                          msg_id: int = None) -> Dict[str, Any]:
    """Create a command message"""
    return create_message(
        MessageType.COMMAND,
        msg_id=msg_id,
        command=command.name,
        args=command_args or {}
    )

def create_response_message(in_response_to: int, success: bool, 
                           data: Dict[str, Any] = None, msg_id: int = None) -> Dict[str, Any]:
    """Create a response message"""
    return create_message(
        MessageType.RESPONSE,
        msg_id=msg_id,
        in_response_to=in_response_to,
        success=success,
        data=data or {}
    )

def create_error_message(error_code: int, error_message: str, 
                        in_response_to: int = None, msg_id: int = None) -> Dict[str, Any]:
    """Create an error message"""
    return create_message(
        MessageType.ERROR,
        msg_id=msg_id,
        error_code=error_code,
        error_message=error_message,
        in_response_to=in_response_to
    )

def validate_command_args(command: CommandType, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate command arguments against protocol specification
    
    Args:
        command: Command type to validate
        args: Arguments to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if command not in PROTOCOL_SPEC:
        return False, f"Unknown command: {command}"
        
    spec = PROTOCOL_SPEC[command]["args"]
    
    # Check if all required arguments are present
    for arg_name, arg_type in spec.items():
        if arg_name not in args:
            return False, f"Missing required argument: {arg_name}"
            
        # Type checking (skip for object type which can be anything)
        if arg_type != object and not isinstance(args[arg_name], arg_type):
            return False, f"Argument {arg_name} should be of type {arg_type.__name__}"
            
    return True, None

def encode_message(message: Dict[str, Any]) -> bytes:
    """Encode a message to bytes for transmission"""
    return json.dumps(message).encode('utf-8')

def decode_message(data: bytes) -> Dict[str, Any]:
    """Decode a received message from bytes"""
    return json.loads(data.decode('utf-8'))