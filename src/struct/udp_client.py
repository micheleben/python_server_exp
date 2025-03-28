# UDP Client with command-argument protocol
# Run this in a Jupyter notebook

import socket
import json
import datetime
import time
import threading
from typing import Dict, Any, List, Tuple, Optional
import selectors

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
        """Initialize the UDP client with two sockets"""
        # Initialize base class
        super().__init__(
            id_prefix="client", 
            port=port + 1,  # Response port
            max_runtime=max_runtime
        )
        
        # Override ID if provided
        if client_id:
            self.id = client_id
        
        # Set up ports
        self.broadcast_port = port
        self.response_port = port + 1
        
        # Client-specific attributes
        self.max_messages = max_messages
        self.server_states = {}
        self.response_callbacks = {}
        self.response_timeout = 10
        
        # Create a separate broadcast socket
        self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        print(f"DEBUG - Binding broadcast socket to 0.0.0.0:{self.broadcast_port}")
        self.broadcast_socket.bind(('0.0.0.0', self.broadcast_port))
        
        # Initialize the response socket (done in base class)
        self._initialize_socket()
        
        # Register the broadcast socket with the selector
        self.selector.register(
            self.broadcast_socket, 
            selectors.EVENT_READ, 
            self.handle_broadcast_data
        )
        
        # Register command handlers
        self._register_client_command_handlers()
    
    def handle_broadcast_data(self, sock, mask):
        """Handle data on the broadcast socket (STATUS messages)"""
        try:
            data, addr = sock.recvfrom(4096)
            print(f"CLIENT DEBUG - Broadcast received from {addr[0]}:{addr[1]}, size: {len(data)} bytes")
            
            try:
                # Decode message
                message = decode_message(data)
                msg_type_str = message.get("message_type", "UNKNOWN")
                
                # Only process STATUS messages on broadcast socket
                if msg_type_str == "STATUS":
                    self._handle_status_message(message, addr)
                
            except Exception as e:
                print(f"Error processing broadcast: {e}")
                
        except Exception as e:
            print(f"Error in handle_broadcast_data: {e}")

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
        """Send a command and register a callback with cancelable timeout"""
        if timeout is None:
            timeout = self.response_timeout
            
        # Send the command
        msg_id = self.send_command(target_addr, command, args)
        
        # Register callback if provided
        if callback:
            print(f"CLIENT DEBUG - Registered callback for message {msg_id}")
            
            # Create the timeout timer but don't start it yet
            timer = threading.Timer(timeout, self._handle_response_timeout, args=[msg_id])
            
            # Store both callback and timer
            self.response_callbacks[msg_id] = {
                "callback": callback,
                "expires": time.time() + timeout,
                "timer": timer
            }
            
            # Start the timer
            timer.start()
        
        return msg_id
    
    def _handle_status_message(self, message: Dict[str, Any], sender_addr: Tuple[str, int]):
        """Handle server status broadcasts
        
        Args:
            message: The decoded status message
            sender_addr: Sender's address (ip, port)
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
        
        print(f"DEBUG - Added/updated server {sender_ip}:{sender_port} in server_states dictionary")
        
        # Print out nicely formatted status update
        server_id = details.get("server_id", "unknown")
        
        print(f"Received status from {sender_ip}:{sender_port}: {state}")
        print(f"Status details: {details}")
        
        if server_id != "unknown":
            print(f"\nServer {server_id} [{sender_ip}:{sender_port}] status: {state}")
            for key, value in details.items():
                if key != "server_id":  # Already included above
                    print(f"  {key}: {value}")

    def _handle_response_message(self, message: Dict[str, Any], sender_addr: Tuple[str, int]):
        """Handle response messages and cancel timeouts"""
        in_response_to = message.get("in_response_to")
        success = message.get("success", False)
        data = message.get("data", {})
        
        print(f"RESPONSE HANDLER - Message ID: {in_response_to}")
        print(f"RESPONSE HANDLER - Success: {success}, Data: {data}")
        print(f"RESPONSE HANDLER - Callbacks: {list(self.response_callbacks.keys())}")
        
        if in_response_to in self.response_callbacks:
            # Get callback info and remove from callbacks dict
            callback_info = self.response_callbacks.pop(in_response_to)
            callback = callback_info["callback"]
            
            # Cancel timeout timer if it exists
            if "timer" in callback_info and callback_info["timer"] is not None:
                print(f"RESPONSE HANDLER - Canceling timeout timer for message {in_response_to}")
                callback_info["timer"].cancel()
            
            # Execute callback
            try:
                print(f"RESPONSE HANDLER - Executing callback")
                callback(success, data, None)
                print(f"RESPONSE HANDLER - Callback executed successfully")
            except Exception as e:
                print(f"RESPONSE HANDLER - Error in callback: {repr(e)}")
        else:
            print(f"RESPONSE HANDLER - No callback found for message {in_response_to}")
    
    def _handle_response_message(self, message: Dict[str, Any], sender_addr: Tuple[str, int]):
        """Simplified response handler"""
        # Extract response details
        in_response_to = message.get("in_response_to")
        success = message.get("success", False)
        data = message.get("data", {})
        
        print(f"RESPONSE HANDLER - Message ID: {in_response_to}")
        print(f"RESPONSE HANDLER - Success: {success}, Data: {data}")
        print(f"RESPONSE HANDLER - Callbacks: {list(self.response_callbacks.keys())}")
        
        # Check for callback with simple error handling
        if in_response_to in self.response_callbacks:
            try:
                # Get the callback and remove it from the dictionary
                callback_func = self.response_callbacks[in_response_to]["callback"]
                del self.response_callbacks[in_response_to]
                
                # Execute the callback directly
                print(f"RESPONSE HANDLER - Executing callback")
                callback_func(success, data, None)
                print(f"RESPONSE HANDLER - Callback executed successfully")
            except Exception as e:
                print(f"RESPONSE HANDLER - Error in callback: {repr(e)}")
                import traceback
                traceback.print_exc()
        else:
            print(f"RESPONSE HANDLER - No callback found for message {in_response_to}")
    
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
        """Extended cleanup to handle broadcast socket"""
        # Close the broadcast socket
        if hasattr(self, 'broadcast_socket'):
            try:
                self.selector.unregister(self.broadcast_socket)
                self.broadcast_socket.close()
            except Exception as e:
                print(f"Error closing broadcast socket: {e}")
        
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

    def handle_received_data(self, sock, mask):
        """Override to debug all incoming packets on the response socket"""
        try:
            data, addr = sock.recvfrom(4096)
            sender_ip, sender_port = addr
            print(f"CLIENT DEBUG - Raw packet received on response socket from {sender_ip}:{sender_port}, size: {len(data)} bytes")
            
            try:
                # Decode the message
                message = decode_message(data)
                msg_type_str = message.get("message_type", "UNKNOWN")
                print(f"CLIENT DEBUG - Decoded message type: {msg_type_str}")
                
                if msg_type_str == "RESPONSE":
                    in_response_to = message.get("in_response_to")
                    print(f"CLIENT DEBUG - Response to message: {in_response_to}, callbacks: {list(self.response_callbacks.keys())}")
                    
                    # Check if we have a callback for this message ID
                    if in_response_to in self.response_callbacks:
                        print(f"CLIENT DEBUG - Found callback for message {in_response_to}")
                    else:
                        print(f"CLIENT DEBUG - No callback found for message {in_response_to}")
            
            except Exception as e:
                print(f"CLIENT DEBUG - Error decoding message: {e}")
                
            # Continue with normal processing
            super().handle_received_data(sock, mask)
            
        except Exception as e:
            print(f"CLIENT ERROR in handle_received_data: {e}")

def interactive_mode(client, elapsed_time, event_count):
    """Allow interaction with servers that have been seen"""
    # Only check every 5 seconds
    if int(elapsed_time) % 5 != 0:
        return True
        
    # Initialize last interaction time if not set
    if not hasattr(interactive_mode, 'last_interaction_time'):
        interactive_mode.last_interaction_time = 0
    
    # Get known servers
    servers = list(client.server_states.keys())
    print(f"DEBUG - Interactive mode: Found {len(servers)} servers, elapsed time: {int(elapsed_time)}")
    
    # Send PING if we have servers and enough time has passed
    if servers and int(elapsed_time) - interactive_mode.last_interaction_time >= 10:
        # Choose a server to interact with
        server_addr = servers[0]
        server_ip, server_port = server_addr
        
        print(f"DEBUG - Will send PING to server {server_ip}:{server_port}")
        
        # Send a PING command
        print(f"\nSending PING to server at {server_ip}:{server_port}")
        
        def ping_callback(success, data, error):
            print(f"PING CALLBACK EXECUTED - Success: {success}, Data: {data}, Error: {error}")
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
    else:
        if not servers:
            print(f"DEBUG - No servers found in server_states dictionary")
        elif int(elapsed_time) - interactive_mode.last_interaction_time < 10:
            print(f"DEBUG - Not enough time passed since last interaction (last: {interactive_mode.last_interaction_time}, current: {int(elapsed_time)})")
        
    return True  # Continue execution

# At the bottom of your client implementation or in your main script
if __name__ == "__main__":
    # Create and run the client
    client = UDPClient(port=37020, max_runtime=300)
    
    print(f"Starting UDP client with ID: {client.id}")
    print("Press Ctrl+C to stop")
    
    # Run the client with the interactive mode
    client.run(between_events_func=interactive_mode)