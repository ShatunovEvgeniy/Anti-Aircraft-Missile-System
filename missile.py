from uuid import UUID

class Missile: 
    id: UUID
    type: int
    max_range: float
    min_range: float
    max_velocity: float
    shootdown_probability: float
    aiming_type: int
    launcher_id: UUID