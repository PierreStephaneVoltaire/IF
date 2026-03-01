"""Heartbeat system for proactive operator engagement.

When channels are idle for extended periods, the heartbeat system
initiates pondering conversations to maintain engagement and gather
operator context.
"""
from .activity import ActivityTracker
from .runner import HeartbeatRunner

__all__ = ["ActivityTracker", "HeartbeatRunner"]
