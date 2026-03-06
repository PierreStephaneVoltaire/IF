"""Terminal-specific configuration.

Configuration options for the Open Terminal container system.

Reference: https://github.com/open-webui/open-terminal
"""
from dataclasses import dataclass
import os


@dataclass
class TerminalConfig:
    """Configuration for terminal container management.
    
    All settings can be overridden via environment variables with
    the TERMINAL_ prefix.
    
    Containers use named Docker volumes (not bind mounts) so the 
    filesystem at /home/user survives container removal and recreation.
    
    Attributes:
        image: Docker image for Open Terminal containers
        network: Docker network for container communication
        mem_limit: Memory limit per container
        cpu_quota: CPU quota (100000 = 1 CPU, 50000 = 0.5 CPU)
        idle_timeout: Seconds before idle containers are stopped
        startup_timeout: Seconds to wait for container health check
        max_containers: Maximum number of concurrent containers
    """
    
    image: str = "ghcr.io/open-webui/open-terminal:latest"
    network: str = "if-terminal-net"
    mem_limit: str = "512m"
    cpu_quota: int = 50000  # 0.5 CPU
    idle_timeout: int = 3600  # 1 hour
    startup_timeout: float = 30.0
    max_containers: int = 20
    
    @classmethod
    def from_env(cls) -> "TerminalConfig":
        """Load configuration from environment variables.
        
        Environment variables:
            TERMINAL_IMAGE: Docker image
            TERMINAL_NETWORK: Docker network name
            TERMINAL_MEM_LIMIT: Memory limit per container
            TERMINAL_CPU_QUOTA: CPU quota
            TERMINAL_IDLE_TIMEOUT: Idle timeout in seconds
            TERMINAL_STARTUP_TIMEOUT: Startup timeout in seconds
            TERMINAL_MAX_CONTAINERS: Maximum concurrent containers
        
        Returns:
            TerminalConfig instance with values from environment
        """
        return cls(
            image=os.getenv("TERMINAL_IMAGE", cls.image),
            network=os.getenv("TERMINAL_NETWORK", cls.network),
            mem_limit=os.getenv("TERMINAL_MEM_LIMIT", cls.mem_limit),
            cpu_quota=int(os.getenv("TERMINAL_CPU_QUOTA", str(cls.cpu_quota))),
            idle_timeout=int(os.getenv("TERMINAL_IDLE_TIMEOUT", str(cls.idle_timeout))),
            startup_timeout=float(os.getenv("TERMINAL_STARTUP_TIMEOUT", str(cls.startup_timeout))),
            max_containers=int(os.getenv("TERMINAL_MAX_CONTAINERS", str(cls.max_containers))),
        )
