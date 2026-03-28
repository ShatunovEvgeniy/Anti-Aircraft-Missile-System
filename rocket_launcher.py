from uuid import UUID
from .missile import Missile

class RocketLauncher:
    name: str
    id: UUID
    x: float
    y: float
    z: float
    launcher_type: int
    firing_channel_count: int
    missile_count: int
    missile: Missile
    launch_time: float
    status: int