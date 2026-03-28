from uuid import UUID, uuid1
from typing import List
from mark  import Mark

class Target:
    id: UUID
    trajectory: List[Mark]
    type: int
    rcs: float
    cur_pos_x: float
    cur_pos_y: float
    
    def __init__(self, type, rcs):
        self.id = uuid1()
        self.trajectory = []
        self.type = type
        self.rcs = rcs

    def add_mark(self, mark: Mark):
        pass

    def remove_mark(self, mark: Mark):
        pass

    def update_mark(self, mark: Mark):
        pass

    