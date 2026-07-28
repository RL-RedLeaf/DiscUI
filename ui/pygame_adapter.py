from .port import *

from events import *
from systems import EventBus


from systems import GameStateSnap


class PygameRenderPort(RenderPort):
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.screen = None
        self.px_portion = 1.0  # 每个单位长度对应的像素比例, 用于缩放
        
    
    def init(self, game_size: tuple[int], event_bus: EventBus):
        self.px_portion = min(self.width / game_size[0], self.height / game_size[1])
        self.event_bus = event_bus
        self.event_bus.subscribe(GameStartEvent, self.on_game_start)
        self.event_bus.subscribe(GamePlayEvent, self.on_game_play)
        self.event_bus.subscribe(ResetEvent, self.on_game_reset)
        if self.screen:
            return  # 防呆操作
        

        import pygame
        pygame.init()

        self.screen = pygame.display.set_mode((int(game_size[0] * self.px_portion), int(game_size[1] * self.px_portion)))
        pygame.display.set_caption("DiscUI")

    def on_game_start(self, event: GameStartEvent):
        self.draw(event.game_state)

    def on_game_play(self, event: GamePlayEvent):
        self.draw(event.game_state)

    def on_game_reset(self, event: ResetEvent):
        self.draw(event.gamestate)

    def draw(self, state: GameStateSnap):
        import pygame
        # 清屏
        self.screen.fill((0, 255, 0))
        CONST = state.const
        # 绘制游戏场地
        self.left_score_area = pygame.Rect(0, 0, CONST.SCORE_LENTH * self.px_portion, CONST.GAME_SIZE[1] * self.px_portion)
        self.right_score_area = pygame.Rect(CONST.GAME_SIZE[0] * self.px_portion - CONST.SCORE_LENTH * self.px_portion, 0, CONST.SCORE_LENTH * self.px_portion, CONST.GAME_SIZE[1] * self.px_portion)
        self.score_font = pygame.font.SysFont('SimHei', 30)
        blue_text = self.score_font.render(f'{state.score[0]}', True, (0, 0, 255))
        red_text = self.score_font.render(f'{state.score[1]}', True, (255, 0, 0))


        pygame.draw.rect(self.screen, (0, 153, 0), self.left_score_area)
        pygame.draw.rect(self.screen, (0, 153, 0), self.right_score_area)
        pygame.draw.circle(self.screen, (255, 255, 255), (CONST.BLUE_TEAM_PULL[0] * self.px_portion, CONST.BLUE_TEAM_PULL[1] * self.px_portion), CONST.SPOT_SIZE * self.px_portion)
        pygame.draw.circle(self.screen, (255, 255, 255), (CONST.RED_TEAM_PULL[0] * self.px_portion, CONST.RED_TEAM_PULL[1] * self.px_portion), CONST.SPOT_SIZE * self.px_portion)

        for team in state.team_list:
            for player in team.player_list:
                pygame.draw.circle(self.screen, (100, 100, 255) if team.team_id == 0 else (255, 100, 100), (player.pos[0] * self.px_portion, player.pos[1] * self.px_portion), CONST.PLAYER_SIZE * self.px_portion)

        pygame.draw.circle(self.screen, (0, 0, 0), (state.disc.pos[0] * self.px_portion, state.disc.pos[1] * self.px_portion), CONST.DISC_SIZE * self.px_portion)
        

        self.screen.blit(blue_text, (CONST.GAME_SIZE[0] / 2  * self.px_portion - 10, 5))
        self.screen.blit(red_text, (CONST.GAME_SIZE[0] / 2  * self.px_portion + 10, 5))

        # 更新显示
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
