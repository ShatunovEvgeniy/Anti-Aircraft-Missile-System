from  uuid import UUID
from .radiolocator import Radiolocator
from.rocket_launcher import RocketLauncher
from typing import List

class CommandCenter:
    name: str
    id: UUID
    x: float
    y: float
    z: float
    target_distribution_algorithm: Algorithm # type:  ignore
    connected_radiolocators: List[Radiolocator]
    connected_launchers: List[RocketLauncher] 