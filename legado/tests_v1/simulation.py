"""Reloj acelerado de obra, exclusivo para pruebas reproducibles."""
from datetime import datetime, timedelta, timezone
import random

class ConstructionClock:
    """Un minuto lógico equivale a un día de obra; no altera el reloj real del sistema."""
    def __init__(self, seed: int = 20260712):
        self._random = random.Random(seed)
        self.real_start = datetime.now(timezone.utc)
        self.logical_minutes = 0

    def next_event(self):
        increment = self._random.randint(1, 3)
        self.logical_minutes += increment
        simulated = self.real_start + timedelta(days=self.logical_minutes)
        return simulated, increment

    @property
    def simulated_days(self):
        return self.logical_minutes
