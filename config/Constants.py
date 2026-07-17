from dataclasses import dataclass

@dataclass(frozen = True)
class Constants:
    SCORE_LENTH: int = 540
    GAME_SIZE: tuple[int] = (1920 + SCORE_LENTH * 2, 1110)
    BLUE_TEAM_PULL: tuple[int] = (SCORE_LENTH * 2, GAME_SIZE[1] / 2)                #发盘点
    RED_TEAM_PULL: tuple[int] = (GAME_SIZE[0] - SCORE_LENTH * 2, GAME_SIZE[1] / 2)  #发盘点
    BLUE_TEAM_ID: int = 0
    RED_TEAM_ID: int = 1
    