from uuid import UUID, uuid1

class Mark:
    """
        Класс Mark отвечает за отметку на карте.
    """
    def __init__(self, x, y, target_id, z = 0, azimuth_angle = 0, velocity = 0):
        self.id: UUID = uuid1()
        self.x: float = x
        self.y: float = y
        self.z: float = z
        self.azimuth_angle: float = azimuth_angle
        self.velocity: float = velocity
        self.target_id = target_id
        print(f"Добавили Mark x = {x}, y = {y} в траекторию цели {target_id}")

    def __del__(self):
        print(f"Mark с id: {self.id} была удалена")

    def __str__(self):
        return f"ID: {self.id}, X: {self.x}, Y: {self.y}, Z: {self.z}"