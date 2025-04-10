import sys
import gc
from memory_profiler import memory_usage


class MemoryTracked:
    def __init__(self):
        self.memory_history = []
        self.record_memory()
        
    def record_memory(self):
        """Records the current memory usage of this object"""
        # Force garbage collection to get more accurate results
        gc.collect()
        
        # Get object size in bytes using sys.getsizeof
        # Note: This only gets the direct memory usage, not nested objects
        direct_size = sys.getsizeof(self)
        
        # For more accurate measurement including nested objects
        # This is more expensive but more accurate
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
        
        # Record both measurements and timestamp
        from datetime import datetime
        timestamp = datetime.now()
        self.memory_history.append({
            'timestamp': timestamp,
            'direct_size_bytes': direct_size,
            'total_size_bytes': total_size
        })
        
        return total_size
    
    def get_memory_history(self):
        """Returns the memory usage history"""
        return self.memory_history
    
    def plot_memory_history(self):
        """Plots the memory usage over time"""
        try:
            import matplotlib.pyplot as plt
            import pandas as pd
            
            # Convert to DataFrame for easier plotting
            df = pd.DataFrame(self.memory_history)
            
            # Plot
            plt.figure(figsize=(10, 6))
            plt.plot(df['timestamp'], df['total_size_bytes'] / (1024*1024), 'b-', label='Total Size (MB)')
            plt.plot(df['timestamp'], df['direct_size_bytes'] / (1024*1024), 'r--', label='Direct Size (MB)')
            plt.xlabel('Time')
            plt.ylabel('Memory Usage (MB)')
            plt.title('Object Memory Usage Over Time')
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            plt.show()
        except ImportError:
            print("Matplotlib or pandas not available for plotting")
            print(self.memory_history)