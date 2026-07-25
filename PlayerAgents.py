from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Final, TYPE_CHECKING
from typing_extensions import override

from entities import PlayerKey, PlayerSnap
from systems import AgentBase, CatchIntent, MoveIntent, ThrowIntent

if TYPE_CHECKING:
    from systems import GameStateSnap


IntentAction = MoveIntent | ThrowIntent | CatchIntent

FIELD_MARGIN: Final[float] = 40.0
FORCE_THROW_TICKS: Final[int] = 90


@dataclass(frozen=True, slots=True)
class RoleProfile:
    lane_ratio: float
    advance: float
    catch_priority: int


HANDLER_PROFILE: Final = RoleProfile(0.50, -130.0, 1)
LEFT_CUTTER_PROFILE: Final = RoleProfile(0.30, 190.0, 2)
RIGHT_CUTTER_PROFILE: Final = RoleProfile(0.70, 190.0, 3)
DEEP_RECEIVER_PROFILE: Final = RoleProfile(0.50, 470.0, 0)


def move_intent(target_pos: tuple[int, int]) -> MoveIntent:
    intent = MoveIntent.__new__(MoveIntent)
    setattr(intent, "target_pos", target_pos)
    return intent


def throw_intent(disc_id: int, motion: tuple[float, float, float]) -> ThrowIntent:
    intent = ThrowIntent.__new__(ThrowIntent)
    setattr(intent, "disc_id", disc_id)
    setattr(intent, "motion", motion)
    return intent


class emptyPlayerAgent(AgentBase):
    player_key: PlayerKey

    @override
    def init(self, player_key: PlayerKey) -> None:
        self.player_key = player_key

    @override
    def agent(self, gamestate: GameStateSnap) -> list[IntentAction]:
        return []


class FourPlayerStrategyAgent(AgentBase):
    player_key: PlayerKey
    profile: RoleProfile
    release_pos: tuple[float, float] | None
    hold_start_tick: int | None

    def __init__(self, profile: RoleProfile) -> None:
        super().__init__()
        self.profile = profile
        self.release_pos = None
        self.hold_start_tick = None

    @override
    def init(self, player_key: PlayerKey) -> None:
        self.player_key = player_key

    @override
    def agent(self, gamestate: GameStateSnap) -> list[IntentAction]:
        player = self._self_player(gamestate)
        disc = gamestate.disc

        match disc.state:
            case "catched":
                self.release_pos = (disc.pos[0], disc.pos[1])
                if disc.holder_key == self.player_key and player.hold_disc:
                    if self.hold_start_tick is None:
                        self.hold_start_tick = gamestate.tick
                    if not self._has_ready_receiver(gamestate) and gamestate.tick - self.hold_start_tick < FORCE_THROW_TICKS:
                        return []
                    return [self._throw_to_best_receiver(gamestate)]
                self.hold_start_tick = None
                return self._move_for_catched_disc(gamestate, player)
            case "flying" | "waiting" | "competing":
                self.hold_start_tick = None
                return self._play_loose_disc(gamestate, player)
            case "ground":
                self.hold_start_tick = None
                return self._move_to_formation(gamestate, player)
            case _:
                return []

    def _self_player(self, gamestate: GameStateSnap) -> PlayerSnap:
        return gamestate.team_list[self.player_key.team_id].player_list[self.player_key.player_id]

    def _team_players(self, gamestate: GameStateSnap) -> tuple[PlayerSnap, ...]:
        return gamestate.team_list[self.player_key.team_id].player_list

    def _opponents(self, gamestate: GameStateSnap) -> tuple[PlayerSnap, ...]:
        opponent_team_id = 1 - self.player_key.team_id
        return gamestate.team_list[opponent_team_id].player_list

    def _direction(self, gamestate: GameStateSnap) -> int:
        if self.player_key.team_id == gamestate.const.BLUE_TEAM_ID:
            return 1
        return -1

    def _move_for_catched_disc(
        self,
        gamestate: GameStateSnap,
        player: PlayerSnap,
    ) -> list[IntentAction]:
        holder_key = gamestate.disc.holder_key
        if holder_key.team_id == self.player_key.team_id:
            return self._move_to_formation(gamestate, player)
        return self._move_to_defense(gamestate, player)

    def _play_loose_disc(
        self,
        gamestate: GameStateSnap,
        player: PlayerSnap,
    ) -> list[IntentAction]:
        if gamestate.disc.state == "competing":
            return self._move_to_formation(gamestate, player)
        if self._is_assigned_catcher(gamestate):
            disc_pos = gamestate.disc.pos
            distance = self._distance(player.pos, (disc_pos[0], disc_pos[1]))
            if self._disc_has_left_release_area(gamestate) and distance <= gamestate.const.CATCH_DISTANCE and disc_pos[2] <= gamestate.const.CATCH_HIGHT and self._nearest_opponent_distance(gamestate, (disc_pos[0], disc_pos[1])) >= gamestate.const.PLAYER_SIZE * 2:
                return [CatchIntent(disc_id=0)]
            return [self._move_toward(gamestate, player.pos, (disc_pos[0], disc_pos[1]))]
        return self._move_to_formation(gamestate, player)

    def _disc_has_left_release_area(self, gamestate: GameStateSnap) -> bool:
        if gamestate.disc.state == "waiting" or self.release_pos is None:
            return True
        disc_xy = (gamestate.disc.pos[0], gamestate.disc.pos[1])
        return self._distance(self.release_pos, disc_xy) >= gamestate.const.CATCH_DISTANCE * 2

    def _move_to_formation(
        self,
        gamestate: GameStateSnap,
        player: PlayerSnap,
    ) -> list[IntentAction]:
        target = self._formation_target(gamestate)
        return [self._move_toward(gamestate, player.pos, target)]

    def _move_to_defense(
        self,
        gamestate: GameStateSnap,
        player: PlayerSnap,
    ) -> list[IntentAction]:
        direction = self._direction(gamestate)
        disc_x = gamestate.disc.pos[0]
        game_width, game_height = gamestate.const.GAME_SIZE
        target_x = min(max(disc_x - direction * (140.0 + self.profile.catch_priority * 35.0), FIELD_MARGIN), game_width - FIELD_MARGIN)
        target_y = game_height * self.profile.lane_ratio
        return [self._move_toward(gamestate, player.pos, (target_x, target_y))]

    def _formation_target(self, gamestate: GameStateSnap) -> tuple[float, float]:
        direction = self._direction(gamestate)
        game_width, game_height = gamestate.const.GAME_SIZE
        base_x = gamestate.disc.pos[0]
        target_x = min(max(base_x + direction * self.profile.advance, FIELD_MARGIN), game_width - FIELD_MARGIN)
        target_y = game_height * self.profile.lane_ratio
        return target_x, target_y

    def _throw_to_best_receiver(self, gamestate: GameStateSnap) -> ThrowIntent:
        disc_pos = gamestate.disc.pos
        receivers = [player for player in self._team_players(gamestate) if player.player_key != self.player_key]
        best_score = None
        best_motion = (0.0, 0.0, 0.0)
        catch_speed = list(gamestate.const.CATCH_SPEED)
        max_frames = int(gamestate.const.MAX_HOLD_TIME / gamestate.delta_time)
        for target in receivers:
            for frame_count in range(1, max_frames + 1):
                time = frame_count * gamestate.delta_time
                velocity_x = (target.pos[0] - disc_pos[0]) / time
                velocity_y = (target.pos[1] - disc_pos[1]) / time
                gravity = gamestate.const.GRAVITY * gamestate.delta_time**2 * frame_count * (frame_count + 1) / 2
                velocity_z = (gamestate.const.CATCH_HIGHT - (disc_pos[2] + 2) - gravity) / time
                catch_velocity_z = velocity_z + gamestate.const.GRAVITY * gamestate.delta_time * frame_count
                if abs(velocity_x) > catch_speed[0] or abs(velocity_y) > catch_speed[1] or abs(catch_velocity_z) > catch_speed[2]:
                    continue
                speed = hypot(velocity_x, velocity_y)
                score = self._receiver_score(gamestate, target) - speed * 0.4 - abs(velocity_z) * 20 - gamestate.const.PLAYER_SPEED * time * 8
                if best_score is None or score > best_score:
                    best_score = score
                    best_motion = (velocity_x, velocity_y, velocity_z)
        return throw_intent(disc_id=0, motion=best_motion)

    def _has_ready_receiver(self, gamestate: GameStateSnap) -> bool:
        disc_xy = (gamestate.disc.pos[0], gamestate.disc.pos[1])
        ready_distance = gamestate.const.CATCH_DISTANCE + gamestate.const.PLAYER_SPEED * FORCE_THROW_TICKS * gamestate.delta_time
        return any(self._distance(disc_xy, player.pos) <= ready_distance for player in self._team_players(gamestate) if player.player_key != self.player_key)

    def _receiver_score(self, gamestate: GameStateSnap, receiver: PlayerSnap) -> float:
        direction = self._direction(gamestate)
        disc_x = gamestate.disc.pos[0]
        disc_xy = (gamestate.disc.pos[0], gamestate.disc.pos[1])
        progress = (receiver.pos[0] - disc_x) * direction
        safety = self._nearest_opponent_distance(gamestate, receiver.pos)
        x_pos = receiver.pos[0]
        game_width = gamestate.const.GAME_SIZE[0]
        score_length = gamestate.const.SCORE_LENTH
        score_bonus = 0.0
        if (self.player_key.team_id == gamestate.const.BLUE_TEAM_ID and x_pos >= game_width - score_length) or (self.player_key.team_id == gamestate.const.RED_TEAM_ID and x_pos <= score_length):
            score_bonus = 900.0
        return progress + safety * 0.45 + score_bonus - self._distance(disc_xy, receiver.pos) * 1.2

    def _is_assigned_catcher(self, gamestate: GameStateSnap) -> bool:
        disc_xy = (gamestate.disc.pos[0], gamestate.disc.pos[1])
        teammates = self._team_players(gamestate)
        nearest = min(
            teammates,
            key=lambda player: (
                self._distance(player.pos, disc_xy),
                self._role_priority(player.player_key),
            ),
        )
        return nearest.player_key == self.player_key

    def _role_priority(self, player_key: PlayerKey) -> int:
        if player_key == self.player_key:
            return self.profile.catch_priority
        return player_key.player_id + 10

    def _nearest_opponent_distance(
        self,
        gamestate: GameStateSnap,
        pos: tuple[float, float],
    ) -> float:
        distances = [self._distance(opponent.pos, pos) for opponent in self._opponents(gamestate)]
        return min(distances)

    def _move_toward(
        self,
        gamestate: GameStateSnap,
        current: tuple[float, float],
        target: tuple[float, float],
    ) -> MoveIntent:
        max_step = gamestate.const.PLAYER_SPEED * gamestate.delta_time * 0.95
        dx = target[0] - current[0]
        dy = target[1] - current[1]
        distance = hypot(dx, dy)
        if distance <= max_step or distance == 0:
            return move_intent(self._nearest_legal_step(current, target, max_step))
        ratio = max_step / distance
        next_x = current[0] + dx * ratio
        next_y = current[1] + dy * ratio
        return move_intent(self._nearest_legal_step(current, (next_x, next_y), max_step))

    def _nearest_legal_step(
        self,
        current: tuple[float, float],
        target: tuple[float, float],
        max_step: float,
    ) -> tuple[int, int]:
        base_x = int(round(current[0]))
        base_y = int(round(current[1]))
        radius = int(max_step) + 1
        candidates = [
            (base_x + offset_x, base_y + offset_y)
            for offset_x in range(-radius, radius + 1)
            for offset_y in range(-radius, radius + 1)
            if self._distance(current, (base_x + offset_x, base_y + offset_y)) <= max_step
        ]
        if not candidates:
            return base_x, base_y
        return min(candidates, key=lambda pos: self._distance(pos, target))

    def _distance(self, first: tuple[float, float], second: tuple[float, float]) -> float:
        return hypot(first[0] - second[0], first[1] - second[1])


class FourPlayerHandlerAgent(FourPlayerStrategyAgent):
    def __init__(self) -> None:
        super().__init__(HANDLER_PROFILE)


class FourPlayerLeftCutterAgent(FourPlayerStrategyAgent):
    def __init__(self) -> None:
        super().__init__(LEFT_CUTTER_PROFILE)


class FourPlayerRightCutterAgent(FourPlayerStrategyAgent):
    def __init__(self) -> None:
        super().__init__(RIGHT_CUTTER_PROFILE)


class FourPlayerDeepReceiverAgent(FourPlayerStrategyAgent):
    def __init__(self) -> None:
        super().__init__(DEEP_RECEIVER_PROFILE)
