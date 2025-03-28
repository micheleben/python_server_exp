import serial
import time

# Create the serial connection outside the handler
# This should be done at the module level before creating the client
try:
    # Configure this according to your serial device requirements
    ser = serial.Serial(
        port='COM3',        # Change to your COM port
        baudrate=9600,      # Set appropriate baudrate
        timeout=0.1         # Short timeout to avoid blocking
    )
    serial_available = True
except Exception as e:
    print(f"Warning: Could not open serial port: {e}")
    serial_available = False

def my_custom_handler(client, elapsed_time, event_count):
    """Custom function to execute between checking for events
    
    Args:
        client: The UDP_Client instance
        elapsed_time: Time elapsed since client started (seconds)
        event_count: Number of events processed so far
        
    Returns:
        bool: True to continue execution, False to stop
    """
    # Initialize static variables if not already set
    if not hasattr(my_custom_handler, 'last_serial_poll_time'):
        my_custom_handler.last_serial_poll_time = time.time()
        my_custom_handler.last_status_time = 0
        my_custom_handler.serial_data_log = []
    
    current_time = time.time()
    
    # Poll serial port precisely every 1.0 second
    if serial_available and (current_time - my_custom_handler.last_serial_poll_time >= 1.0):
        # Calculate actual jitter for diagnostics
        actual_interval = current_time - my_custom_handler.last_serial_poll_time
        jitter_ms = abs(actual_interval - 1.0) * 1000  # jitter in milliseconds
        
        # Record the polling time immediately before polling
        # This reduces accumulated drift
        my_custom_handler.last_serial_poll_time = current_time
        
        try:
            # Check if data is available without blocking
            if ser.in_waiting > 0:
                # Read available data (non-blocking)
                serial_data = ser.read(ser.in_waiting)
                
                # Process the data however needed
                timestamp = time.time()
                data_entry = {
                    "timestamp": timestamp,
                    "data": serial_data.hex(),  # Store as hex for logging
                    "jitter_ms": jitter_ms
                }
                my_custom_handler.serial_data_log.append(data_entry)
                
                # Optionally print the data
                print(f"\nSerial data received: {serial_data.hex()}, jitter: {jitter_ms:.2f}ms")
            else:
                # No data available, just log the poll
                if jitter_ms > 5:  # Only log significant jitter
                    print(f"\nSerial poll (no data), jitter: {jitter_ms:.2f}ms")
                
        except Exception as e:
            print(f"\nError reading serial port: {e}")
    
    # Status update every 5 seconds (this is the original functionality)
    if int(elapsed_time) % 5 == 0 and my_custom_handler.last_status_time != int(elapsed_time):
        my_custom_handler.last_status_time = int(elapsed_time)
        print(f"\nStatus update at {int(elapsed_time)}s: {len(client.received_messages)} UDP messages received")
        if hasattr(my_custom_handler, 'serial_data_log'):
            print(f"Serial polls: {len(my_custom_handler.serial_data_log)}, avg jitter: {calculate_avg_jitter(my_custom_handler.serial_data_log):.2f}ms")
    
    # Simple progress indicator
    sys.stdout.write(f"\rListening... {int(elapsed_time)}s elapsed | {len(client.received_messages)} UDP msgs ")
    sys.stdout.flush()
    
    return True  # Continue execution

def calculate_avg_jitter(data_log):
    """Calculate average jitter from the data log"""
    if not data_log:
        return 0
    jitter_values = [entry.get("jitter_ms", 0) for entry in data_log]
    return sum(jitter_values) / len(jitter_values)