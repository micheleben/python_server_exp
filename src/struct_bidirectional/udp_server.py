# UDP Broadcast Server with command-argument protocol
# Run this in a Jupyter notebook

import socket
import json
import datetime
import time
import threading
from typing import Dict, Any, List, Tuple, Set

# Import the shared protocol and base class
from udp_protocol import (
    MessageType, CommandType, PROTOCOL_SPEC,
    create_message, create_status_message, create_command_message, 
    create_response_message, create_error_message,
    validate_command_args, encode_message, decode_message
)
from udp_base import UDPCommunicator

class UDPServer(UDPCommunicator):
    """UDP Server that broadcasts state and processes client commands"""
    
    def __init__(self, port=37020, broadcast_interval=5, max_runtime=0):
        """Initialize the UDP server
        
        Args:
            port: UDP port to use
            broadcast_interval: Interval between status broadcasts in seconds
            max_runtime: Maximum runtime in seconds (0 = unlimited)
        """
        # Initialize base class
        super().__init__(id_prefix="server", port=port, max_runtime=max_runtime)
        
        # Server-specific attributes
        self.broadcast_interval = broadcast_interval
        self.broadcast_port = port
        self.broadcast_thread = None
        self.stop_broadcast = False
        
        # Server state
        self.current_state = "INITIALIZING"
        self.states = ["ACTIVE", "STANDBY", "MAINTENANCE", "ERROR"]
        self.current_state_index = 0
        self.server_parameters = {}
        
        # Client tracking
        self.known_clients = {}  # Maps client address to info
        self.client_last_seen = {}  # Maps client address to last time seen
        
        # Initialize the server socket
        self._initialize_socket()
        
        # Register server-specific command handlers
        self._register_server_command_handlers()
    
    def _register_server_command_handlers(self):
        """Register server-specific command handlers"""
        # Register base handlers
        super()._register_default_command_handlers()
        
        # Register server-specific handlers
        self.register_command_handler(CommandType.GET_STATUS, self._handle_get_status)
        self.register_command_handler(CommandType.SET_PARAMETER, self._handle_set_parameter)
        self.register_command_handler(CommandType.GET_CLIENTS, self._handle_get_clients)
        self.register_command_handler(CommandType.SHUTDOWN, self._handle_shutdown)
        self.register_command_handler(CommandType.CUSTOM, self._handle_custom)
    
    def _handle_get_status(self, sender_addr: Tuple[str, int], args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_status command
        
        Args:
            sender_addr: Sender's address (ip, port)
            args: Command arguments (should be empty for get_status)
            
        Returns:
            Status information
        """
        return {
            "state": self.current_state,
            "uptime_seconds": time.time() - self.start_time,
            "client_count": len(self.known_clients),
            "parameters": self.server_parameters
        }
    
    def _handle_set_parameter(self, sender_addr: Tuple[str, int], args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set_parameter command
        
        Args:
            sender_addr: Sender's address (ip, port)
            args: Command arguments with param_name and param_value
            
        Returns:
            Result of parameter setting
        """
        param_name = args["param_name"]
        param_value = args["param_value"]
        
        # Update the parameter
        old_value = self.server_parameters.get(param_name, None)
        self.server_parameters[param_name] = param_value
        
        return {
            "success": True,
            "param_name": param_name,
            "old_value": old_value,
            "new_value": param_value
        }
    
    def _handle_get_clients(self, sender_addr: Tuple[str, int], args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_clients command
        
        Args:
            sender_addr: Sender's address (ip, port)
            args: Command arguments (should be empty for get_clients)
            
        Returns:
            List of known clients
        """
        # Clean up stale clients (not seen in last 60 seconds)
        self._cleanup_stale_clients(timeout=60)
        
        return {
            "client_count": len(self.known_clients),
            "clients": self.known_clients
        }
    
    def _handle_shutdown(self, sender_addr: Tuple[str, int], args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle shutdown command
        
        Args:
            sender_addr: Sender's address (ip, port)
            args: Command arguments with reason
            
        Returns:
            Confirmation of shutdown initiation
        """
        reason = args["reason"]
        
        # Log shutdown request
        sender_ip, sender_port = sender_addr
        print(f"\nReceived shutdown request from {sender_ip}:{sender_port}")
        print(f"Reason: {reason}")
        
        # Schedule shutdown after response is sent
        threading.Timer(1.0, self._initiate_shutdown, args=[reason]).start()
        
        return {
            "success": True,
            "message": f"Server shutdown initiated with reason: {reason}",
            "shutdown_time": datetime.datetime.now().isoformat()
        }
    
    def _handle_custom(self, sender_addr: Tuple[str, int], args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle custom command
        
        Args:
            sender_addr: Sender's address (ip, port)
            args: Command arguments with action and data
            
        Returns:
            Custom response
        """
        action = args["action"]
        data = args["data"]
        
        # Log custom command
        sender_ip, sender_port = sender_addr
        print(f"\nReceived custom command '{action}' from {sender_ip}:{sender_port}")
        
        # Process based on action
        if action == "cycle_state":
            # Cycle to next state
            self.current_state_index = (self.current_state_index + 1) % len(self.states)
            self.current_state = self.states[self.current_state_index]
            return {
                "success": True,
                "new_state": self.current_state
            }
        elif action == "set_state":
            # Set specific state
            if isinstance(data, str) and data in self.states:
                self.current_state = data
                self.current_state_index = self.states.index(data)
                return {
                    "success": True,
                    "new_state": self.current_state
                }
            else:
                return {
                    "success": False,
                    "error": f"Invalid state: {data}. Must be one of {self.states}"
                }
        elif action == "echo":
            # Simple echo
            return {
                "success": True,
                "echo": data
            }
        else:
            return {
                "success": False,
                "error": f"Unknown custom action: {action}"
            }
        
    def _handle_status_message(self, message: Dict[str, Any], sender_addr: Tuple[str, int]):
        """Override to handle status messages and ignore our own broadcasts
        
        Args:
            message: The decoded status message
            sender_addr: Sender's address (ip, port)
        """
        # Extract server ID from message details
        details = message.get("details", {})
        sender_server_id = details.get("server_id", "unknown")
        
        # Ignore our own broadcasts
        if sender_server_id == self.id:
            return
        
        # Call the parent implementation for messages from other servers
        super()._handle_status_message(message, sender_addr)


    def handle_received_data(self, sock, mask):
        """Override to filter out our own broadcast messages before processing"""
        try:
            data, addr = sock.recvfrom(4096)
            sender_ip, sender_port = addr
            
            # Try to decode the message to check if it's our own
            try:
                message = decode_message(data)
                msg_type_str = message.get("message_type", "UNKNOWN")
                
                # If it's a status message, check for our own ID
                if msg_type_str == "STATUS":
                    details = message.get("details", {})
                    sender_server_id = details.get("server_id", "unknown")
                    
                    # Ignore our own broadcasts
                    if sender_server_id == self.id:
                        return
            except:
                # If any error in decoding, process normally
                pass
            
            # First call the parent implementation for standard processing
            super().handle_received_data(sock, mask)
            
            # Then update client tracking for non-self messages
            try:
                # Update client tracking
                now = datetime.datetime.now().isoformat()
                if addr not in self.known_clients:
                    # New client
                    self.known_clients[addr] = {
                        "ip": sender_ip,
                        "port": sender_port,
                        "first_seen": now,
                        "message_count": 1
                    }
                    print(f"\nNew client connected: {sender_ip}:{sender_port}")
                else:
                    # Existing client
                    self.known_clients[addr]["message_count"] += 1
                
                # Update last seen time
                self.client_last_seen[addr] = now
                
            except Exception as e:
                print(f"Error updating client tracking: {e}")
                
        except Exception as e:
            print(f"Error in server handle_received_data: {e}")

    def _broadcast_status_thread(self):
        """Thread function for status broadcasting"""
        while not self.stop_broadcast:
            try:
                # Create status details
                details = {
                    "uptime_seconds": time.time() - self.start_time,
                    "client_count": len(self.known_clients),
                    "server_id": self.id
                }
                
                # Broadcast current state
                self.broadcast_status(self.current_state, details, self.broadcast_port)
                
                # Cycle state for demonstration purposes
                # Comment out if you want manual state control only
                self.current_state_index = (self.current_state_index + 1) % len(self.states)
                self.current_state = self.states[self.current_state_index]
                
                # Wait for next broadcast interval
                time.sleep(self.broadcast_interval)
                
            except Exception as e:
                print(f"Error in broadcast thread: {e}")
                time.sleep(1)  # Wait a bit on error
    
    def _initiate_shutdown(self, reason):
        """Initiate server shutdown"""
        print(f"\nShutting down server. Reason: {reason}")
        self.stop_broadcast = True
        
        # Wait for broadcast thread to end
        if self.broadcast_thread and self.broadcast_thread.is_alive():
            self.broadcast_thread.join(timeout=2.0)
        
        # Force exit the run loop in the main thread
        # This is a bit of a hack, but works for our purposes
        # In a more sophisticated implementation, we'd use a proper shutdown mechanism
        raise KeyboardInterrupt("Server shutdown requested")
    
    def handle_received_data(self, sock, mask):
        """Override to track clients when they send messages"""
        # First call the parent implementation
        super().handle_received_data(sock, mask)
        
        # Then do any server-specific processing
        try:
            data, addr = sock.recvfrom(4096)
            sender_ip, sender_port = addr
            
            # Update client tracking
            now = datetime.datetime.now().isoformat()
            if addr not in self.known_clients:
                # New client
                self.known_clients[addr] = {
                    "ip": sender_ip,
                    "port": sender_port,
                    "first_seen": now,
                    "message_count": 1
                }
                print(f"\nNew client connected: {sender_ip}:{sender_port}")
            else:
                # Existing client
                self.known_clients[addr]["message_count"] += 1
            
            # Update last seen time
            self.client_last_seen[addr] = now
            
        except Exception as e:
            # Ignore any errors, main processing is done in parent
            pass
    
    def _cleanup_stale_clients(self, timeout=60):
        """Clean up clients that haven't been seen recently
        
        Args:
            timeout: Timeout in seconds
        """
        now = datetime.datetime.now()
        stale_clients = []
        
        for addr, last_seen in self.client_last_seen.items():
            # Convert ISO timestamp to datetime
            last_seen_time = datetime.datetime.fromisoformat(last_seen)
            
            # Calculate time difference
            diff = (now - last_seen_time).total_seconds()
            
            # If client hasn't been seen in timeout seconds, mark for removal
            if diff > timeout:
                stale_clients.append(addr)
        
        # Remove stale clients
        for addr in stale_clients:
            client_ip, client_port = addr
            print(f"\nRemoving stale client: {client_ip}:{client_port}")
            del self.known_clients[addr]
            del self.client_last_seen[addr]
    
    def start_broadcasting(self):
        """Start the status broadcast thread"""
        if not self.broadcast_thread or not self.broadcast_thread.is_alive():
            self.stop_broadcast = False
            self.broadcast_thread = threading.Thread(target=self._broadcast_status_thread)
            self.broadcast_thread.daemon = True
            self.broadcast_thread.start()
            print(f"Started broadcasting on port {self.broadcast_port} every {self.broadcast_interval} seconds")
    
    def stop_broadcasting(self):
        """Stop the status broadcast thread"""
        if self.broadcast_thread and self.broadcast_thread.is_alive():
            self.stop_broadcast = True
            self.broadcast_thread.join(timeout=2.0)
            print("Stopped broadcasting")
    
    def run(self, between_events_func=None):
        """
        Run the server with broadcasting
        
        Args:
            between_events_func: Optional function to call between checking for events
        """
        # Set start time BEFORE starting broadcasting
        self.start_time = time.time()
        self.execution_stats["start_time"] = datetime.datetime.now().isoformat()

        # Start broadcasting before the main loop
        self.current_state = "ACTIVE"
        self.start_broadcasting()
        
        try:
            # Run the main event loop from the base class
            return super()._run_event_loop(between_events_func)
        
        finally:
            # Make sure to stop broadcasting when the server stops
            self.stop_broadcasting()

# Example usage when run as a script
if __name__ == "__main__":
    # Create and run the server
    server = UDPServer(port=37020, broadcast_interval=5)
    
    print(f"Starting UDP server with ID: {server.id}")
    print(f"Broadcasting states: {server.states}")
    print("Press Ctrl+C to stop")
    
    # Run the server
    server.run()