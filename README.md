# project that contains server - client architectures in python
scripts that implement a UDP broadcasting system that can run in separate Jupyter notebooks: UDP Broadcast Server: Sends messages with timestamps and state information to clients UDP Broadcast Client: Receives broadcast messages and displays the information. Create two separate Jupyter notebooks:

1. Server notebook: Copy the server code into it
2. Client notebook(s): Copy the client code into one or more notebooks

## general characteristics
Server:

1. Broadcasts messages every 5 seconds to all clients on the network
2. Each message contains a timestamp, state (cycles through ACTIVE, STANDBY, MAINTENANCE, ERROR), and message ID
3. Listens for client responses (optional)
4. Automatically determines the appropriate broadcast address for your network (when using netiface)

Client:

1. Listens for broadcast messages on port 37020
2. Displays the timestamp and state information when received
3. Sends an acknowledgment back to the server
4. Tracks message history and displays statistics

Features:

1. Reliable Broadcasting: Uses UDP broadcasting to reach multiple clients
2. Two-way Communication: Clients acknowledge receipt of messages
3. Unique Identification: Each client has a unique ID
4. Error Handling: Both server and client handle network timeouts and errors gracefully
5. Message Deduplication: Clients track message IDs to avoid processing duplicates

## use of netiface
the use of netiface requires the installaion of the associated package, but this could be a problem in some cases (toolchain not acvaialbe to compile the wheel)
For this reason there is a version without the netifaces. In this version of the server removes the dependency on netifaces by simplifying the broadcast approach. Instead of dynamically determining the network's broadcast address, it uses the standard broadcast address 255.255.255.255, which will work in most standard network configurations. 
Key Changes:
1. Removed netifaces Dependency: The server no longer requires the netifaces library for determining the broadcast address.
2. Simplified Broadcast Address Selection: Using the standard 255.255.255.255 broadcast address, which is recognized by most networks for local subnet broadcasting.
2. Removed Custom get_broadcast_address() Function: This function was dependent on netifaces and has been replaced with a simpler approach.

### Note on Broadcasting:
With this simplified approach, the broadcast will typically reach devices on the same local subnet. In most typical setups (like a home or small office network), this works well. If you're working in a more complex network environment with multiple subnets, broadcasts might not cross subnet boundaries without additional network configuration.
The client code remains unchanged, as it didn't rely on netifaces in the first place.
This simplified implementation should be easier to deploy since it only uses Python's standard libraries and doesn't require any additional package installations.

## Non-blocking clients
Here is a look to some workarounds to blocking calls in the client
Non-Blocking Client Approaches

### Using selectors module:
Python's selectors module provides a high-level interface for I/O multiplexing
It allows you to monitor multiple socket connections for events without blocking
This is more scalable and efficient than threading for many connections
Good for managing multiple I/O streams simultaneously
#### Advantages:
Uses a simple callback pattern that's easy to understand
Requires no special execution environment
Works well in both script and Jupyter notebook contexts
Very explicit control flow
#### How it works:
Registers the UDP socket with a selector to monitor for read events
When data is available, the callback function is triggered
Uses a small timeout to keep the main loop responsive
Shows an animated waiting indicator between events

### Asynchronous I/O with asyncio:
Uses Python's built-in asyncio library for asynchronous programming
Allows handling network operations without blocking through coroutines
Very clean syntax with async/await keywords
Well-suited for Jupyter notebooks which already have asyncio event loops
#### Advantages:
Uses Python's modern async/await pattern
Cleaner separation of concerns through protocol/transport abstraction
Works especially well in Jupyter notebooks (which use asyncio)
More scalable for complex applications with multiple async operations
#### How it works:
Implements a protocol class that handles datagram events
Uses coroutines for asynchronous operations
Creates a separate task for the waiting indicator
Automatically handles cancellation and cleanup

### Non-blocking socket mode:
Setting the socket to non-blocking mode with socket.setblocking(False)
Using try/except to handle BlockingIOError exceptions
Simpler approach but requires manual polling
### Threading approach:
Using a separate thread for socket operations
Main thread remains responsive while socket operations happen in background
May be overkill for simple UDP client but provides good isolation