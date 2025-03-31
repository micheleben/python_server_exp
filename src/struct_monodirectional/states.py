
import sys
import datetime
from transitions import Machine

class ServerState:
    """Class to track and manage server state using a finite state machine"""
    
    # Define the states
    states = ['UNKNOWN', 'ACTIVE', 'STANDBY', 'MAINTENANCE', 'ERROR']
    
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
    
    def update_state(self, new_state):
        """Update the FSM state based on server broadcast"""
        if new_state not in ServerState.states:
            print(f"Warning: Received unknown state '{new_state}'")
            return False
        
        current_time = datetime.datetime.now()
        
        # Call the appropriate transition method
        try:
            # Get the method for this transition (e.g., set_active, set_standby)
            transition_method = getattr(self, f'set_{new_state.lower()}')
            transition_method()
            
            # Update successful
            self.last_update_time = current_time
            return True
        except AttributeError:
            print(f"Error: Cannot transition to state '{new_state}'")
            return False
    
    def log_transition(self):
        """Log the state transition"""
        current_time = datetime.datetime.now().isoformat()
        self.state_history.append({
            'time': current_time,
            'from_state': self.state_history[-1]['to_state'] if self.state_history else 'UNKNOWN',
            'to_state': self.state
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