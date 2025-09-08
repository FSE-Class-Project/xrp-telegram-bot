"""Background task processing"""
from typing import Any
import asyncio
from collections import deque

class TaskQueue:
    def __init__(self):
        self.queue: deque = deque()
        self.processing = False
    
    async def add_task(self, func, *args, **kwargs):
        """Add task to queue"""
        self.queue.append((func, args, kwargs))
        if not self.processing:
            asyncio.create_task(self.process_queue())
    
    async def process_queue(self):
        """Process queued tasks"""
        self.processing = True
        while self.queue:
            func, args, kwargs = self.queue.popleft()
            try:
                await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Task failed: {e}")
        self.processing = False

task_queue = TaskQueue()