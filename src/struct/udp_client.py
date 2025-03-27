# UDP Client with command-argument protocol
# Run this in a Jupyter notebook

import socket
import json
import datetime
import time
import threading
from typing import Dict, Any, List, Tuple, Optional

# Import the shared protocol and base class
from udp_protocol import (
    MessageType, CommandType, PROTOCOL_SPEC,
    create_message, create_status_message, create_command_message, 
    create_response_message, create_error_message,
    validate_command_args, encode_message, decode_message
)
from udp_base import UDPCommunicator

class UDPClient(UDPCommunicator):
    """UDP Client that receives broadcasts and sends commands"""
    
    def __init__(self, client_id=None, port=37020, max_runtime=0, max_messages=0):
        """Initialize the UDP client
        
        Args:
            client_id: Client ID (generated if None)
            port: UDP port to use
            max_runtime: Maximum runtime in seconds (0 = unlimited)
            max_messages: Maximum messages to receive (0 = unlimited)
        """
        # Initialize base class with client ID
        super().__init__(
            id_prefix="client", 
            port=port, 
            max_runtime=max_runtime
        )
        
        # Override ID if provided
        if client_id:
            self.id = client_id
        
        # Client-specific attributes
        self.max_messages = max_messages
        self.server_states = {}  # Maps server address to last known state
        self.response_callbacks = {}  # Maps message IDs to callback functions
        self.response_timeout = 10  # Timeout for response callbacks in seconds
        
        # Initialize the client socket
        self._initialize_socket()
        
        # Register client-specific command handlers
        self._register_client_command_handlers()
    
    def _register_client_command_handlers(self):
        """Register client-specific command handlers"""
        # Register base handlers
        super()._register_default_command_handlers()
        
        # Register custom message handlers
        self.register_message_handler(MessageType.STATUS, self._handle_server_status)
    
    def _handle_server_status(self, sender_addr: Tuple[str, int], message: Dict[str, Any]):
        """Handle server status broadcasts
        
        Args:
            sender_addr: Sender's address (ip, port)
            message: The status message
        """
        sender_ip, sender_port = sender_addr
        state = message.get("state", "unknown")
        details = message.get("details", {})
        
        # Update server state tracking
        self.server_states[sender_addr] = {
            "state": state,
            "details": details,
            "last_updated": datetime.datetime.now().isoformat()
        }
        
        # Print out nicely formatted status update
        server_id = details.get("server_id", "unknown")
        
        # Construct status message
        status_display = []
        status_display.append(f"\nServer {server_id} [{sender_ip}:{sender_port}] status: {state}")
        
        if details:
            for key, value in details.items():
                if key != "server_id":  # Already included above
                    status_display.append(f"  {key}: {value}")
        
        print("\n".join(status_display))
    
    def should_exit(self, elapsed_time):
        """Check if we should exit based on runtime or message count
        
        Args:
            elapsed_time: Time elapsed since start
            
        Returns:
            bool: True if should exit, False otherwise
        """
        # First check base class exit conditions (max_runtime)
        if super().should_exit(elapsed_time):
            return True
            
        # Then check client-specific exit conditions (max_messages)
        if self.max_messages > 0 and len(self.received_messages) >= self.max_messages:
            print(f"\nReached maximum message count of {self.max_messages}")
            return True
            
        return False
    
    def send_command_with_callback(self, 
                                  target_addr: Tuple[str, int], 
                                  command: CommandType, 
                                  args: Dict[str, Any] = None,
                                  callback=None,
                                  timeout=None):
        """Send a command and register a callback for the response
        
        Args:
            target_addr: Target address (ip, port)
            command: Command type to send
            args: Command arguments
            callback: Function to call when response is received
                     Should accept (success, response_data, error)
            timeout: Timeout in seconds (None for default)
            
        Returns:
            int: Message ID
        """
        # Default timeout
        if timeout is None:
            timeout = self.response_timeout
            
        # Send the command
        msg_id = self.send_command(target_addr, command, args)
        
        # Register callback if provided
        if callback:
            self.response_callbacks[msg_id] = {
                "callback": callback,
                "expires": time.time() + timeout
            }
            
            # Schedule timeout cleanup
            threading.Timer(timeout, self._handle_response_timeout, args=[msg_id]).start()
        
        return msg_id
    
    def _handle_response_timeout(self, msg_id):
        """Handle response timeout by calling callback with error
        
        Args:
            msg_id: Message ID that timed out
        """
        if msg_id in self.response_callbacks:
            callback_info = self.response_callbacks.pop(msg_id)
            callback = callback_info["callback"]
            
            # Call callback with timeout error
            callback(False, None, "Response timeout")
    
    def _handle_response_message(self, message: Dict[str, Any], sender_addr: Tuple[str, int]):
        """Handle response messages and invoke callbacks
        
        Args:
            message: The response message
            sender_addr: Sender's address (ip, port)
        """
        # Call base class handler first
        super()._handle_response_message(message, sender_addr)
        
        # Extract response details
        in_response_to = message.get("in_response_to")
        success = message.get("success", False)
        data = message.get("data", {})
        
        # Check if we have a callback registered for this message
        if in_response_to in self.response_callbacks:
            callback_info = self.response_callbacks.pop(in_response_to)
            callback = callback_info["callback"]
            
            # Call the callback
            callback(success, data, None)
    
    def _handle_error_message(self, message: Dict[str, Any], sender_addr: Tuple[str, int]):
        """Handle error messages and invoke callbacks if applicable
        
        Args:
            message: The error message
            sender_addr: Sender's address (ip, port)
        """
        # Call base class handler first
        super()._handle_error_message(message, sender_addr)
        
        # Extract error details
        in_response_to = message.get("in_response_to")
        error_code = message.get("error_code")
        error_message = message.get("error_message")
        
        # Check if we have a callback registered for this message
        if in_response_to and in_response_to in self.response_callbacks:
            callback_info = self.response_callbacks.pop(in_response_to)
            callback = callback_info["callback"]
            
            # Call the callback with error
            error = f"Error {error_code}: {error_message}"
            callback(False, None, error)
    
    def cleanup(self):
        """Extended cleanup to handle any pending callbacks"""
        # Call any remaining callbacks with error
        for msg_id, callback_info in list(self.response_callbacks.items()):
            callback = callback_info["callback"]
            callback(False, None, "Client shutting down")
        
        # Clear callbacks
        self.response_callbacks.clear()
        
        # Call base class cleanup
        return super().cleanup()
    
    def get_server_status(self, server_addr: Tuple[str, int], callback=None):
        """Get status from a server
        
        Args:
            server_addr: Server address (ip, port)
            callback: Optional callback for response
            
        Returns:
            int: Message ID
        """
        return self.send_command_with_callback(
            server_addr,
            CommandType.GET_STATUS,
            callback=callback
        )
    
    def set_server_parameter(self, 
                            server_addr: Tuple[str, int], 
                            param_name: str, 
                            param_value: Any,
                            callback=None):
        """Set a parameter on a server
        
        Args:
            server_addr: Server address (ip, port)
            param_name: Parameter name
            param_value: Parameter value
            callback: Optional callback for response
            
        Returns:
            int: Message ID
        """
        args = {
            "param_name": param_name,
            "param_value": param_value
        }
        
        return self.send_command_with_callback(
            server_addr,
            CommandType.SET_PARAMETER,
            args,
            callback
        )
    
    def get_server_clients(self, server_addr: Tuple[str, int], callback=None):
        """Get client list from a server
        
        Args:
            server_addr: Server address (ip, port)
            callback: Optional callback for response
            
        Returns:
            int: Message ID
        """
        return self.send_command_with_callback(
            server_addr,
            CommandType.GET_CLIENTS,
            callback=callback
        )
    
    def send_custom_command(self, 
                           server_addr: Tuple[str, int], 
                           action: str, 
                           data: Any = None,
                           callback=None):
        """Send a custom command to a server
        
        Args:
            server_addr: Server address (ip, port)
            action: Custom action name
            data: Custom data
            callback: Optional callback for response
            
        Returns:
            int: Message ID
        """
        args = {
            "action": action,
            "data": data
        }
        
        return self.send_command_with_callback(
            server_addr,
            CommandType.CUSTOM,
            args,
            callback
        )
    
    def request_server_shutdown(self, 
                               server_addr: Tuple[str, int], 
                               reason: str = "Client requested shutdown",
                               callback=None):
        """Request server shutdown
        
        Args:
            server_addr: Server address (ip, port)
            reason: Shutdown reason
            callback: Optional callback for response
            
        Returns:
            int: Message ID
        """
        args = {
            "reason": reason
        }
        
        return self.send_command_with_callback(
            server_addr,
            CommandType.SHUTDOWN,
            args,
            callback
        )

# Example usage when run as a script
if __name__ == "__main__":
    # Create and run the client
    client = UDPClient(port=37020, max_runtime=300)
    
    print(f"Starting UDP client with ID: {client.id}")
    print("Press Ctrl+C to stop")
    
    # Define a custom between-events function that can interact with servers
    def interactive_mode(client, elapsed_time, event_count):
        """Allow interaction with servers that have been seen"""
        # Only check every 5 seconds
        if int(elapsed_time) % 5 != 0:
            return True
            
        # Get known servers
        servers = list(client.server_states.keys())
        
        if servers and hasattr(interactive_mode, 'last_interaction_time') and \
           int(elapsed_time) - interactive_mode.last_interaction_time >= 10:
            # Choose a server to interact with
            server_addr = servers[0]
            server_ip, server_port = server_addr
            
            # Send a PING command
            print(f"\nSending PING to server at {server_ip}:{server_port}")
            
            def ping_callback(success, data, error):
                if success:
                    print(f"PING response: {data}")
                else:
                    print(f"PING failed: {error}")
                    
            client.send_command_with_callback(
                server_addr,
                CommandType.PING,
                callback=ping_callback
            )
            
            # Update last interaction time
            interactive_mode.last_interaction_time = int(elapsed_time)
            
        # Initialize last interaction time if not set
        if not hasattr(interactive_mode, 'last_interaction_time'):
            interactive_mode.last_interaction_time = int(elapsed_time)
            
        return True  # Continue execution
    
    # Run the client with the interactive mode
    client.run(between_events_func=interactive_mode)