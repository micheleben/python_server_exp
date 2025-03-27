# UDP Base Communication Class
# Shared functionality for both Server and Client

import socket
import selectors
import json
import datetime
import uuid
import time
import sys
from typing import Dict, Any, Callable, Optional, List, Tuple

# Import the protocol (assuming it's saved as udp_protocol.py)
from udp_protocol import (
    MessageType, CommandType, PROTOCOL_SPEC,
    create_message, create_status_message, create_command_message, 
    create_response_message, create_error_message,
    validate_command_args, encode_message, decode_message
)

class UDPCommunicator:
    """Base class for UDP communication with shared functionality"""
    
    def __init__(self, id_prefix="node", port=37020, max_runtime=0):
        """Initialize UDP communicator with shared functionality
        
        Args:
            id_prefix: Prefix for the node ID (e.g., 'server' or 'client')
            port: UDP port to use
            max_runtime: Maximum runtime in seconds (0 = unlimited)
        """
        # Node identification and configuration
        self.id = f"{id_prefix}_{str(uuid.uuid4())[:8]}"
        self.port = port
        self.max_runtime = max_runtime
        
        # Socket and selector setup
        self.selector = selectors.DefaultSelector()
        self.socket = None
        
        # Message tracking
        self.received_messages = []
        self.sent_messages = []
        self.last_processed_id = -1
        self.message_handlers = {}
        
        # Execution statistics
        self.start_time = None
        self.execution_stats = {
            "node_id": self.id,
            "port": self.port
        }
        
        # Command handlers map
        self.command_handlers = {}
        
        # Register default command handlers
        self._register_default_command_handlers()
    
    def _initialize_socket(self, bind_addr='0.0.0.0'):
        """Initialize the UDP socket with appropriate options"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind socket to address and port
        self.socket.bind((bind_addr, self.port))
        
        # Register with selector
        self.selector.register(self.socket, selectors.EVENT_READ, self.handle_received_data)
    
    def _register_default_command_handlers(self):
        """Register default command handlers"""
        # Register handlers for basic commands
        self.register_command_handler(CommandType.PING, self._handle_ping)
    
    def register_command_handler(self, command_type: CommandType, handler_func: Callable):
        """Register a handler function for a specific command type
        
        Args:
            command_type: The type of command to handle
            handler_func: Function to call when this command is received
                          Should accept (sender_addr, command_args) and return a response dict
        """
        self.command_handlers[command_type] = handler_func
    
    def register_message_handler(self, message_type: MessageType, handler_func: Callable):
        """Register a handler function for a specific message type
        
        Args:
            message_type: The type of message to handle
            handler_func: Function to call when this message type is received
                          Should accept (sender_addr, message_dict) and return None
        """
        self.message_handlers[message_type] = handler_func
    
    def _handle_ping(self, sender_addr: Tuple[str, int], args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping command - responds with a simple pong
        
        Args:
            sender_addr: Sender's address (ip, port)
            args: Command arguments (should be empty for ping)
            
        Returns:
            Response data
        """
        sender_ip, sender_port = sender_addr
        return {
            "status": "pong",
            "timestamp": datetime.datetime.now().isoformat(),
            "node_id": self.id
        }
    
    def handle_received_data(self, sock, mask):
        """Handle incoming UDP data
        
        Args:
            sock: Socket that received data
            mask: Event mask from selector
        """
        try:
            data, addr = sock.recvfrom(4096)  # Larger buffer for more complex messages
            sender_ip, sender_port = addr
            
            try:
                # Decode the message
                message = decode_message(data)
                
                # Extract message type and ID
                msg_type_str = message.get("message_type", "UNKNOWN")
                msg_id = message.get("message_id", -1)
                
                # Ensure message_id is an integer
                if not isinstance(msg_id, int):
                    try:
                        msg_id = int(msg_id)
                    except (ValueError, TypeError):
                        print(f"Warning: Received non-integer message_id: {msg_id}")
                        msg_id = -1
                
                # Only process new messages or messages with no ID
                if msg_id > self.last_processed_id or msg_id == -1:
                    if msg_id > 0:
                        self.last_processed_id = msg_id
                    
                    # Add to received messages list
                    self.received_messages.append({
                        "message": message,
                        "sender": addr,
                        "receive_time": datetime.datetime.now().isoformat()
                    })
                    
                    # Process based on message type
                    try:
                        msg_type = MessageType[msg_type_str]
                        
                        # Log receipt of message
                        print(f"\nReceived {msg_type.name} message from {sender_ip}:{sender_port}")
                        
                        # Handle based on message type
                        if msg_type == MessageType.COMMAND:
                            self._handle_command_message(message, addr)
                        elif msg_type == MessageType.RESPONSE:
                            self._handle_response_message(message, addr)
                        elif msg_type == MessageType.STATUS:
                            self._handle_status_message(message, addr)
                        elif msg_type == MessageType.ERROR:
                            self._handle_error_message(message, addr)
                        
                        # Call custom message handler if registered
                        if msg_type in self.message_handlers:
                            self.message_handlers[msg_type](addr, message)
                    
                    except KeyError:
                        print(f"Error: Unknown message type: {msg_type_str}")
                        
                        # Send error response for unknown message type
                        error_msg = create_error_message(
                            error_code=1001,
                            error_message=f"Unknown message type: {msg_type_str}",
                            in_response_to=msg_id
                        )
                        self.send_message(error_msg, addr)
                
            except json.JSONDecodeError:
                print(f"Error: Received invalid JSON data from {sender_ip}:{sender_port}")
                # No response sent as we can't parse the message ID
        
        except Exception as e:
            print(f"Error in handle_received_data: {e}")
    
    def _handle_command_message(self, message: Dict[str, Any], sender_addr: Tuple[str, int]):
        """Handle a command message
        
        Args:
            message: The decoded command message
            sender_addr: Sender's address (ip, port)
        """
        sender_ip, sender_port = sender_addr
        msg_id = message.get("message_id")
        command_str = message.get("command")
        args = message.get("args", {})
        
        print(f"Received command: {command_str} with args: {args}")
        
        try:
            # Convert command string to enum
            command = CommandType[command_str]
            
            # Validate command arguments
            is_valid, error_msg = validate_command_args(command, args)
            
            if not is_valid:
                # Send error response for invalid arguments
                error_msg = create_error_message(
                    error_code=1002,
                    error_message=error_msg,
                    in_response_to=msg_id
                )
                self.send_message(error_msg, sender_addr)
                return
            
            # Check if we have a handler for this command
            if command in self.command_handlers:
                # Call the handler and get response data
                try:
                    response_data = self.command_handlers[command](sender_addr, args)
                    
                    # Send success response
                    response = create_response_message(
                        in_response_to=msg_id,
                        success=True,
                        data=response_data
                    )
                    self.send_message(response, sender_addr)
                    
                except Exception as e:
                    # Send error response if handler raises exception
                    error_msg = create_error_message(
                        error_code=1003,
                        error_message=f"Error processing command: {str(e)}",
                        in_response_to=msg_id
                    )
                    self.send_message(error_msg, sender_addr)
            else:
                # Send error response for unhandled command
                error_msg = create_error_message(
                    error_code=1004,
                    error_message=f"No handler for command: {command_str}",
                    in_response_to=msg_id
                )
                self.send_message(error_msg, sender_addr)
        
        except KeyError:
            # Send error response for unknown command
            error_msg = create_error_message(
                error_code=1005,
                error_message=f"Unknown command: {command_str}",
                in_response_to=msg_id
            )
            self.send_message(error_msg, sender_addr)
    
    def _handle_response_message(self, message: Dict[str, Any], sender_addr: Tuple[str, int]):
        """Handle a response message (default implementation just logs it)
        
        Args:
            message: The decoded response message
            sender_addr: Sender's address (ip, port)
        """
        sender_ip, sender_port = sender_addr
        msg_id = message.get("message_id")
        in_response_to = message.get("in_response_to")
        success = message.get("success", False)
        data = message.get("data", {})
        
        if success:
            print(f"Received successful response to message {in_response_to}: {data}")
        else:
            print(f"Received failed response to message {in_response_to}: {data}")
    
    def _handle_status_message(self, message: Dict[str, Any], sender_addr: Tuple[str, int]):
        """Handle a status message (default implementation just logs it)
        
        Args:
            message: The decoded status message
            sender_addr: Sender's address (ip, port)
        """
        sender_ip, sender_port = sender_addr
        state = message.get("state", "unknown")
        details = message.get("details", {})
        
        print(f"Received status from {sender_ip}:{sender_port}: {state}")
        if details:
            print(f"Status details: {details}")
    
    def _handle_error_message(self, message: Dict[str, Any], sender_addr: Tuple[str, int]):
        """Handle an error message (default implementation just logs it)
        
        Args:
            message: The decoded error message
            sender_addr: Sender's address (ip, port)
        """
        sender_ip, sender_port = sender_addr
        error_code = message.get("error_code")
        error_message = message.get("error_message")
        in_response_to = message.get("in_response_to")
        
        if in_response_to:
            print(f"Received error for message {in_response_to}: [{error_code}] {error_message}")
        else:
            print(f"Received error: [{error_code}] {error_message}")
    
    def send_message(self, message: Dict[str, Any], target_addr: Tuple[str, int]):
        """Send a message to a specific target address
        
        Args:
            message: Message dictionary to send
            target_addr: Target address (ip, port)
        """
        try:
            # Encode the message
            data = encode_message(message)
            
            # Send the message
            self.socket.sendto(data, target_addr)
            
            # Log the sent message
            self.sent_messages.append({
                "message": message,
                "target": target_addr,
                "send_time": datetime.datetime.now().isoformat()
            })
            
            # Extract message type for logging
            msg_type_str = message.get("message_type", "UNKNOWN")
            try:
                msg_type = MessageType[msg_type_str].name
            except KeyError:
                msg_type = msg_type_str
                
            target_ip, target_port = target_addr
            print(f"Sent {msg_type} message to {target_ip}:{target_port}")
            
        except Exception as e:
            print(f"Error sending message: {e}")
    
    def send_command(self, target_addr: Tuple[str, int], command: CommandType, args: Dict[str, Any] = None):
        """Send a command to a specific target
        
        Args:
            target_addr: Target address (ip, port)
            command: Command type to send
            args: Command arguments
        """
        # Create command message
        cmd_msg = create_command_message(command, args)
        
        # Send the message
        self.send_message(cmd_msg, target_addr)
        
        return cmd_msg["message_id"]  # Return message ID for tracking responses
    
    def broadcast_status(self, state: str, details: Dict[str, Any] = None, port: int = None):
        """Broadcast a status message to the network
        
        Args:
            state: State string to broadcast
            details: Additional status details
            port: Port to broadcast to (defaults to self.port)
        """
        if port is None:
            port = self.port
            
        # Create status message
        status_msg = create_status_message(state, details)
        
        # Broadcast address
        broadcast_addr = ('255.255.255.255', port)
        
        # Send the message
        self.send_message(status_msg, broadcast_addr)
    
    def should_exit(self, elapsed_time):
        """Check if we should exit based on runtime
        
        Args:
            elapsed_time: Time elapsed since start
            
        Returns:
            bool: True if should exit, False otherwise
        """
        # Exit if max runtime is reached (if set)
        if self.max_runtime > 0 and elapsed_time > self.max_runtime:
            print(f"\nReached maximum runtime of {self.max_runtime} seconds")
            return True
            
        return False
    
    def cleanup(self):
        """Clean up resources and generate final statistics"""
        # Update execution stats
        self.execution_stats["end_time"] = datetime.datetime.now().isoformat()
        if self.start_time:
            self.execution_stats["runtime_seconds"] = time.time() - self.start_time
        self.execution_stats["messages_received"] = len(self.received_messages)
        self.execution_stats["messages_sent"] = len(self.sent_messages)
        
        # Clean up the socket and selector
        if self.socket:
            self.selector.unregister(self.socket)
            self.socket.close()
        self.selector.close()
        
        print(f"Cleaned up resources for {self.id}")
        
        # Return the execution stats
        return self.execution_stats
    
    def run(self, between_events_func=None):
        """
        Main event loop
        
        Args:
            between_events_func: Optional function to call between checking for events.
                                The function receives the node object, elapsed time, and events count.
                                If None, a default waiting indicator is displayed.
        """
        # Set start time
        self.start_time = time.time()
        self.execution_stats["start_time"] = datetime.datetime.now().isoformat()
        
        # Indicator for user that we're waiting for messages (used in default behavior)
        waiting_indicator = ['|', '/', '-', '*']
        indicator_index = 0
        last_indicator_time = time.time()
        event_count = 0
        
        # Default function for between events if none provided
        def default_between_events(node, elapsed_time, event_count):
            nonlocal indicator_index, last_indicator_time
            current_time = time.time()
            
            # Update waiting indicator every 0.5 seconds
            if current_time - last_indicator_time > 0.5:
                sys.stdout.write(f"\rWaiting {waiting_indicator[indicator_index]} [{int(elapsed_time)}s elapsed] ")
                sys.stdout.flush()
                indicator_index = (indicator_index + 1) % len(waiting_indicator)
                last_indicator_time = current_time
                return True  # Continue execution
            return True
        
        # Use provided function or default
        between_func = between_events_func if between_events_func else default_between_events
        
        try:
            while True:
                # Check current time and calculate elapsed time
                current_time = time.time()
                elapsed_time = current_time - self.start_time
                
                # Check if we should exit
                if self.should_exit(elapsed_time):
                    break
                
                # Check for events with a small timeout (50ms)
                events = self.selector.select(timeout=0.05)
                event_count += len(events)
                
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, mask)
    
                # Execute the between-events function
                # If it returns False, exit the loop
                if not between_func(self, elapsed_time, event_count):
                    print("\nExiting due to between_events_func returning False")
                    break
    
        except KeyboardInterrupt:
            print("\nShutting down due to keyboard interrupt...")
    
        finally:
            return self.cleanup()