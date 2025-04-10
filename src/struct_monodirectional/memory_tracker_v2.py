import sys
import gc
from memory_profiler import memory_usage
from datetime import datetime

class MemoryTracked:
    def __init__(self):
        self.memory_history = []
        self.record_memory("initialization")
        
    def record_memory(self, event_name=""):
        """Records the current memory usage of this object and the process"""
        # Force garbage collection to get more accurate results
        gc.collect()
        
        # Get direct object size with sys.getsizeof
        direct_size = sys.getsizeof(self)
        
        # Get total object size with traversal
        total_size = self._calculate_total_size()
        
        # Get process memory using memory_profiler
        process_memory = memory_usage(max_usage=True)
        if isinstance(process_memory, list):
            process_memory = process_memory[0]  # It returns a list
            
        # Record measurements and timestamp
        timestamp = datetime.now()
        entry = {
            'timestamp': timestamp,
            'event': event_name,
            'direct_size_bytes': direct_size,
            'total_size_bytes': total_size,
            'process_memory_mb': process_memory
        }
        self.memory_history.append(entry)
        
        return entry
        
    def _calculate_total_size(self):
        """Helper method to calculate total size of object and all its references"""
        total_size = 0
        objects = [self]
        seen = {id(self)}
        
        while objects:
            obj = objects.pop()
            total_size += sys.getsizeof(obj)
            
            # If object has __dict__, include all its attributes
            if hasattr(obj, '__dict__'):
                for k, v in obj.__dict__.items():
                    if id(v) not in seen and not isinstance(v, type):
                        seen.add(id(v))
                        objects.append(v)
            
            # Handle lists, tuples, sets, etc.
            elif isinstance(obj, (list, tuple, set, frozenset)):
                for item in obj:
                    if id(item) not in seen and not isinstance(item, type):
                        seen.add(id(item))
                        objects.append(item)
                        
            # Handle dictionaries
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    # Check both keys and values
                    for item in (k, v):
                        if id(item) not in seen and not isinstance(item, type):
                            seen.add(id(item))
                            objects.append(item)
        
        return total_size
    
    # ... rest of the class (get_memory_history, plot_memory_history) remains the same