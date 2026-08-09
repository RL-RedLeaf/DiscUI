from dataclasses import dataclass

@dataclass(frozen = True)
class Constants:
    SCORE_LENTH: int = 540
    GAME_SIZE: tuple[float, float] = (1920 + SCORE_LENTH * 2, 1110)
    BLUE_TEAM_PULL: tuple[float, float, float] = (SCORE_LENTH * 2, GAME_SIZE[1] / 2, 0)                #发盘点
    RED_TEAM_PULL: tuple[float, float, float] = (GAME_SIZE[0] - SCORE_LENTH * 2, GAME_SIZE[1] / 2, 0)  #发盘点
    BLUE_TEAM_ID: int = 0
    RED_TEAM_ID: int = 1

    DISC_SIZE: int = 12         #这三个是用于绘制
    PLAYER_SIZE: int = 18
    SPOT_SIZE: int = 15

    GRAVITY: float = -9.8

    PLAYER_SPEED: float = 150
    CATCH_DISTANCE: float = 20
    CATCH_HIGHT: float = 2

    MIN_VELOCITY: float = 50
    MAX_HOLD_TIME: float = 2

    BLUE_SCORE_AREA: tuple[float, float, float, float] = (GAME_SIZE[0] - SCORE_LENTH, 0, SCORE_LENTH, GAME_SIZE[1])
    RED_SCORE_AREA: tuple[float, float, float, float] = (0, 0, SCORE_LENTH, GAME_SIZE[1])

    SUCCESS_SCORE: int = 15

    MAX_TIME: float = 10 * 60