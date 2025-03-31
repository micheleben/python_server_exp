# UDP Broadcast Client using selectors (non-blocking)
# Parameterized for papermill execution with OOP design
# Run this in a separate Jupyter notebook

import socket
import json
import datetime
import uuid
import time
import selectors
import sys

# Parameters cell - tag this with "parameters" in Jupyter for papermill
# These default values will be overridden by papermill when executed
client_id = None  # Will be set by papermill, fallback to random ID
max_runtime = 300  # Default runtime in seconds (0 = unlimited)
client_port = 37020  # Default port to listen on
max_messages = 0  # Maximum messages to receive (0 = unlimited)

class UDP_Client:
    def __init__(self, client_id=None, client_port=37020, max_runtime=300, max_messages=0):
        """Initialize UDP client with configurable parameters"""
        # Client identification and configuration
        self.client_id = client_id if client_id else str(uuid.uuid4())[:8]
        self.client_port = client_port
        self.max_runtime = max_runtime
        self.max_messages = max_messages
        
        # Socket and selector setup
        self.selector = selectors.DefaultSelector()
        self.client_socket = None
        self.response_socket = None
        
        # Message tracking
        self.received_messages = []
        self.last_processed_id = -1
        
        # Execution statistics
        self.start_time = None
        self.execution_stats = {
            "client_id": self.client_id,
            "port": self.client_port
        }
        
        # Initialize the client
        self._initialize_sockets()
    
    def _initialize_sockets(self):
        """Set up the client and response sockets"""
        # Create UDP socket for receiving broadcasts
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind to the client port to receive broadcasts
        self.client_socket.bind(('', self.client_port))
        
        # Create a socket for sending responses back to the server
        self.response_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Register socket with the selector
        self.selector.register(self.client_socket, selectors.EVENT_READ, self.handle_received_data)
        
        print(f"Client {self.client_id} started, listening on port {self.client_port}")
        print(f"Configuration: max_runtime={self.max_runtime}s, max_messages={self.max_messages}")
        print("Press Ctrl+C to stop")
    
    def handle_received_data(self, sock, mask):
        """Handle incoming UDP broadcast data"""
        try:
            data, addr = sock.recvfrom(1024)
            server_ip = addr[0]
            server_port = addr[1]
            
            # Decode and parse the message
            message_str = data.decode('utf-8')
            message = json.loads(message_str)
            
            # Extract timestamp and state
            timestamp = message.get("timestamp", "unknown")
            state = message.get("state", "unknown")
            message_id = message.get("message_id", -1)
            
            # Only process new messages (in case of duplicates)
            if message_id > self.last_processed_id:
                self.last_processed_id = message_id
                
                # Get current time
                receive_time = datetime.datetime.now().isoformat()
                
                # Print received message
                print(f"\nReceived broadcast from {server_ip}:{server_port}")
                print(f"Message ID: {message_id}")
                print(f"Timestamp: {timestamp}")
                print(f"State: {state}")
                
                # Append to message history
                self.received_messages.append({
                    "server_ip": server_ip,
                    "server_port": server_port,
                    "timestamp": timestamp,
                    "receive_time": receive_time,
                    "state": state,
                    "message_id": message_id
                })
                
                # Send response back to the server
                response = f"Client {self.client_id} received message {message_id}"
                self.response_socket.sendto(response.encode('utf-8'), (server_ip, server_port))
                
                # Print statistics
                print(f"Total messages received: {len(self.received_messages)}")
                
                # Display the last 5 states for demonstration
                if len(self.received_messages) >= 5:
                    recent_states = [msg["state"] for msg in self.received_messages[-5:]]
                    print(f"Last 5 states: {recent_states}")
        
        except json.JSONDecodeError:
            print(f"Error: Received invalid JSON data")
        
        except Exception as e:
            print(f"Error: {e}")

    def should_exit(self, elapsed_time):
        """Check if client should exit based on runtime or message count"""
        # Exit if max runtime is reached (if set)
        if self.max_runtime > 0 and elapsed_time > self.max_runtime:
            print(f"\nReached maximum runtime of {self.max_runtime} seconds")
            return True
            
        # Exit if max messages is reached (if set)
        if self.max_messages > 0 and len(self.received_messages) >= self.max_messages:
            print(f"\nReceived {self.max_messages} messages, stopping")
            return True
            
        return False

    def run_client(self, between_events_func=None):
        """
        Main client event loop
        
        Args:
            between_events_func: Optional function to call between checking for events.
                                The function receives the client object, elapsed time, and events count.
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
        def default_between_events(client, elapsed_time, event_count):
            nonlocal indicator_index, last_indicator_time
            current_time = time.time()
            
            # Update waiting indicator every 0.5 seconds
            if current_time - last_indicator_time > 0.5:
                sys.stdout.write(f"\rWaiting for broadcasts {waiting_indicator[indicator_index]} [{int(elapsed_time)}s elapsed] ")
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
            print("\nClient shutting down due to keyboard interrupt...")
    
        finally:
            self.cleanup()
            
    def cleanup(self):
        """Clean up resources and generate final statistics"""
        # Update execution stats
        self.execution_stats["end_time"] = datetime.datetime.now().isoformat()
        self.execution_stats["runtime_seconds"] = time.time() - self.start_time
        self.execution_stats["messages_received"] = len(self.received_messages)
        
        # Clean up the sockets and selector
        self.selector.unregister(self.client_socket)
        self.selector.close()
        self.client_socket.close()
        self.response_socket.close()
        print("Client stopped")
        
        # Print summary
        print(f"\nExecution Summary:")
        print(f"- Client ID: {self.client_id}")
        print(f"- Runtime: {self.execution_stats['runtime_seconds']:.2f} seconds")
        print(f"- Messages received: {len(self.received_messages)}")
        
        # Add this for papermill to capture output
        self.execution_stats["received_messages"] = self.received_messages
        
        # Return the execution stats
        return self.execution_stats



# Example of a custom between-events function
def my_custom_handler(client, elapsed_time, event_count):
    """Custom function to execute between checking for events
    
    Args:
        client: The UDP_Client instance
        elapsed_time: Time elapsed since client started (seconds)
        event_count: Number of events processed so far
        
    Returns:
        bool: True to continue execution, False to stop
    """
    # Example: Print status every 5 seconds
    if int(elapsed_time) % 5 == 0 and hasattr(my_custom_handler, 'last_time') and my_custom_handler.last_time != int(elapsed_time):
        my_custom_handler.last_time = int(elapsed_time)
        print(f"\nStatus update at {int(elapsed_time)}s: {len(client.received_messages)} messages received")
    
    # Store the current time to avoid repeated printing
    if not hasattr(my_custom_handler, 'last_time'):
        my_custom_handler.last_time = 0
    
    # Example: Display a simple progress indicator
    sys.stdout.write(f"\rListening... {int(elapsed_time)}s elapsed | {len(client.received_messages)} msgs ")
    sys.stdout.flush()
    
    # Example: Custom exit condition - stop after 30 seconds even if max_runtime is longer
    # if elapsed_time > 30:
    #     print("\nCustom exit condition met (30s elapsed)")
    #     return False
    
    return True  # Continue execution


if __name__ == "__main__":
    # If client_id not provided (when running manually), generate a random one
    if client_id is None:
        client_id = str(uuid.uuid4())[:8]

    # Create and run the client
    client = UDP_Client(
        client_id=client_id,
        client_port=client_port,
        max_runtime=max_runtime,
        max_messages=max_messages
    )