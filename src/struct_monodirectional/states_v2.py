import sys
import datetime
from transitions import Machine

class ServerState:
    """Class to track and manage server state using a finite state machine"""
    
    # Define the states
    states = ['UNKNOWN', 'ACTIVE', 'STANDBY', 'MAINTENANCE', 'ERROR']
    
    # Define the expected loop sequence
    LOOP_SEQUENCE = ['ACTIVE', 'STANDBY', 'MAINTENANCE', 'ERROR', 'ACTIVE']
    
    def __init__(self):
        """Initialize the server state machine"""
        # Initialize the state machine
        self.machine = Machine(
            model=self,
            states=ServerState.states,
            initial='UNKNOWN'
        )
        
        # Define transitions based on the server's broadcast state
        # All states can transition to any other state based on the broadcast
        for source in ServerState.states:
            for dest in ServerState.states:
                if source != dest:
                    self.machine.add_transition(
                        trigger=f'set_{dest.lower()}',
                        source=source,
                        dest=dest,
                        before='log_transition'
                    )
        
        # State history tracking
        self.state_history = []
        self.last_update_time = None
        
        # Loop tracking
        self.loop_count = 0
        self.current_loop_position = 0  # Position in the LOOP_SEQUENCE
        self.loop_in_progress = False
    
    def update_state(self, new_state):
        """Update the FSM state based on server broadcast
        
        Returns:
            dict: Result with keys 'success', 'changed', and 'loop_completed'
        """
        if new_state not in ServerState.states:
            print(f"Warning: Received unknown state '{new_state}'")
            return {'success': False, 'changed': False, 'loop_completed': False}
        
        # Check if this is actually a state change
        current_state = self.state
        is_state_change = (current_state != new_state)
        
        # If it's the same state, consider it a success but not a change
        if not is_state_change:
            return {'success': True, 'changed': False, 'loop_completed': False}
        
        current_time = datetime.datetime.now()
        loop_completed = False
        
        # Call the appropriate transition method
        try:
            # Get the method for this transition (e.g., set_active, set_standby)
            transition_method = getattr(self, f'set_{new_state.lower()}')
            transition_method()
            
            # Update successful
            self.last_update_time = current_time
            
            # Track loop progress
            loop_completed = self._track_loop_progress(current_state, new_state)
            
            return {'success': True, 'changed': True, 'loop_completed': loop_completed}
        except AttributeError:
            print(f"Error: Cannot transition to state '{new_state}'")
            return {'success': False, 'changed': False, 'loop_completed': False}
    
    def _track_loop_progress(self, from_state, to_state):
        """Track progress through the expected loop sequence
        
        Args:
            from_state: The state we're transitioning from
            to_state: The state we're transitioning to
            
        Returns:
            bool: True if a complete loop was just finished
        """
        # If we're at the beginning of a potential loop
        if not self.loop_in_progress and to_state == self.LOOP_SEQUENCE[0]:
            self.loop_in_progress = True
            self.current_loop_position = 0
            print(f"Starting potential loop at {to_state}")
            return False
            
        # If we're already tracking a loop
        if self.loop_in_progress:
            expected_current = self.LOOP_SEQUENCE[self.current_loop_position]
            expected_next = self.LOOP_SEQUENCE[self.current_loop_position + 1] if self.current_loop_position + 1 < len(self.LOOP_SEQUENCE) else None
            
            # Check if the transition follows the expected sequence
            if from_state == expected_current and to_state == expected_next:
                self.current_loop_position += 1
                
                # Check if we've completed the loop
                if self.current_loop_position == len(self.LOOP_SEQUENCE) - 1:  # Last index is ACTIVE again
                    self.loop_count += 1
                    self.loop_in_progress = False  # Reset for next loop
                    self.current_loop_position = 0
                    print(f"🔄 Completed full loop #{self.loop_count}: ACTIVE→STANDBY→MAINTENANCE→ERROR→ACTIVE")
                    return True
                else:
                    print(f"Loop progress: {self.current_loop_position}/{len(self.LOOP_SEQUENCE)-1} ({to_state})")
                    return False
            else:
                # Unexpected transition - reset loop tracking
                print(f"⚠️ Loop broken: Expected {expected_current}→{expected_next} but got {from_state}→{to_state}")
                if to_state == self.LOOP_SEQUENCE[0]:
                    # If we jump back to the start, begin a new potential loop
                    self.loop_in_progress = True
                    self.current_loop_position = 0
                    print(f"Starting new potential loop at {to_state}")
                else:
                    # Otherwise, we're no longer in a potential loop sequence
                    self.loop_in_progress = False
                return False
                
        return False
    
    def log_transition(self):
        """Log the state transition"""
        current_time = datetime.datetime.now().isoformat()
        self.state_history.append({
            'time': current_time,
            'from_state': self.state_history[-1]['to_state'] if self.state_history else 'UNKNOWN',
            'to_state': self.state,
            'loop_count': self.loop_count
        })
    
    def get_current_state(self):
        """Get the current server state"""
        return self.state
    
    def get_state_history(self, count=None):
        """Get the state history
        
        Args:
            count: Optional number of most recent state changes to return
        """
        if count is None:
            return self.state_history
        return self.state_history[-count:]
    
    def get_time_in_state(self):
        """Get the time spent in the current state"""
        if self.last_update_time is None:
            return None
        
        current_time = datetime.datetime.now()
        return (current_time - self.last_update_time).total_seconds()
    
    def get_loop_count(self):
        """Get the number of complete loops observed"""
        return self.loop_count
    
    def get_loop_progress(self):
        """Get the current progress through a loop
        
        Returns:
            tuple: (in_progress, position, total_positions)
        """
        return (self.loop_in_progress, 
                self.current_loop_position, 
                len(self.LOOP_SEQUENCE) - 1)  # -1 because ACTIVE appears twice