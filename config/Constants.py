from dataclasses import dataclass

@dataclass(frozen = True)
class Constants:
    GAME_SIZE: tuple[int] = (1920, 1080)
    BLUE_TEAM_ID: int = 0
    RED_TEAM_ID: int = 1