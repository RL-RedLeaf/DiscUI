from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import TYPE_CHECKING

from entities import PlayerKey
from systems import AgentBase, CatchIntent, Intent, MoveIntent, TeamAgentBase, ThrowIntent

if TYPE_CHECKING:
    from entities import PlayerSnap, TeamSnap
    from systems import GameStateSnap


@dataclass
class TgerPlan:
    team_id: int
    tick: int
    mode: str
    attack_dir: int
    holder_key: PlayerKey | None
    catch_point: tuple[float, float]
    attack_style: str = "wide_switch"
    chaser_key: PlayerKey | None = None
    receiver_priority: tuple[PlayerKey, ...] = ()
    target_by_player: dict[PlayerKey, tuple[float, float]] = field(default_factory=dict)
    role_by_player: dict[PlayerKey, str] = field(default_factory=dict)


class TgerCoach(TeamAgentBase[TgerPlan]):
    FIELD_MARGIN: float = 12.0
    SAFE_TOUCH_GAP: float = 60.0
    MARK_DISTANCE: float = 46.0
    CHASE_MARGIN: float = 1.6
    DEFENSE_TRANSITION_TICKS: int = 90
    POSSESSION_MEMORY_TICKS: int = 240
    CONTESTED_RECOVERY_MARGIN: float = 20.0
    ATTACK_STYLES: tuple[str, ...] = ("wide_switch", "diamond", "cross", "backdoor")

    def init(self, team_id, player_list: list[PlayerKey]):
        self.team_id = team_id
        self.player_list = player_list
        self.last_attack_receiver_key: PlayerKey | None = None
        self.last_attack_tick: int = -10_000
        self.previous_holder_key: PlayerKey | None = None
        self.last_own_possession_tick: int = -10_000
        self.last_loss_tick: int = -10_000
        self.last_possession_team: int | None = None
        self.last_own_holder_key: PlayerKey | None = None
        self.attack_sequence: int = 0
        self.attack_pass_count: int = 0
        self.attack_style: str = self.ATTACK_STYLES[self.team_id % len(self.ATTACK_STYLES)]

    def agent(self, gamestate: GameStateSnap) -> TgerPlan | None:
        my_team = gamestate.team_list[self.team_id]
        op_team = gamestate.team_list[1 - self.team_id]
        attack_dir = self._attack_dir()
        disc_holder_key = gamestate.disc.holder_key
        self._update_possession_memory(gamestate, disc_holder_key)
        holder_key = disc_holder_key if disc_holder_key and disc_holder_key.team_id == self.team_id else None
        catch_point = self._predict_landing(gamestate)
        plan = TgerPlan(
            team_id=self.team_id,
            tick=gamestate.tick,
            mode="idle",
            attack_dir=attack_dir,
            holder_key=holder_key,
            catch_point=catch_point,
            attack_style=self.attack_style,
        )

        if holder_key is not None:
            plan.mode = "attack"
            self._build_attack_plan(gamestate, my_team, op_team, plan)
        elif disc_holder_key is not None:
            plan.mode = "transition_defense" if self._in_defensive_transition(gamestate) else "defend"
            self._build_defense_plan(gamestate, my_team, op_team, plan)
        else:
            plan.mode = "free"
            self._build_free_plan(gamestate, my_team, op_team, plan)

        self.previous_holder_key = disc_holder_key
        return plan

    def _update_possession_memory(self, gamestate: GameStateSnap, holder_key: PlayerKey | None) -> None:
        if gamestate.disc.state == "waiting":
            self.last_own_possession_tick = -10_000
            self.last_loss_tick = -10_000
            self.last_possession_team = None
            self.last_own_holder_key = None
            self.attack_pass_count = 0
            return

        if holder_key is not None and holder_key.team_id == self.team_id:
            if self.last_possession_team != self.team_id:
                self.attack_sequence += 1
                self.attack_pass_count = 0
            elif self.last_own_holder_key != holder_key:
                self.attack_pass_count += 1
            style_index = (
                self.attack_sequence
                + self.team_id
                - 1
                + self.attack_pass_count // 2
            ) % len(self.ATTACK_STYLES)
            self.attack_style = self.ATTACK_STYLES[style_index]
            self.last_possession_team = self.team_id
            self.last_own_holder_key = holder_key
            self.last_own_possession_tick = gamestate.tick
            return

        if holder_key is None or holder_key.team_id == self.team_id:
            return

        self.last_possession_team = holder_key.team_id
        changed_holder = holder_key != self.previous_holder_key
        recent_own_possession = gamestate.tick - self.last_own_possession_tick <= self.POSSESSION_MEMORY_TICKS
        if changed_holder and recent_own_possession:
            self.last_loss_tick = gamestate.tick

    def _in_defensive_transition(self, gamestate: GameStateSnap) -> bool:
        return gamestate.tick - self.last_loss_tick <= self.DEFENSE_TRANSITION_TICKS

    def _build_attack_plan(self, gamestate: GameStateSnap, my_team: "TeamSnap", op_team: "TeamSnap", plan: TgerPlan) -> None:
        holder = self._holder(gamestate)
        if holder is None:
            return

        score_x = self._score_x(gamestate)
        available = [p for p in my_team.player_list if p.player_key != holder.player_key]
        ordered = self._attack_role_order(available, holder, score_x, plan.attack_dir)
        phase = (gamestate.tick // 60 + self.attack_sequence) % 4

        for idx, player in enumerate(ordered):
            target, role = self._attack_target_for_style(
                gamestate,
                holder,
                player,
                idx,
                score_x,
                plan.attack_dir,
                plan.attack_style,
                phase,
            )

            target = self._bound(gamestate, target)
            target = self._repel_from_team(gamestate, target, my_team.player_list, holder.player_key)
            plan.target_by_player[player.player_key] = target
            plan.role_by_player[player.player_key] = role

        for player in available:
            if player.player_key not in plan.target_by_player:
                anchor = (holder.pos[0] - plan.attack_dir * 155.0, self._wide_lane_y(gamestate, player, slot=0))
                plan.target_by_player[player.player_key] = self._bound(gamestate, anchor)
                plan.role_by_player[player.player_key] = "reset"

        plan.receiver_priority = tuple(self._rank_receivers(gamestate, holder, my_team, op_team, plan.attack_dir, plan))
        if plan.receiver_priority:
            self.last_attack_receiver_key = plan.receiver_priority[0]
            self.last_attack_tick = gamestate.tick

    def _attack_target_for_style(
        self,
        gamestate: GameStateSnap,
        holder: "PlayerSnap",
        player: "PlayerSnap",
        idx: int,
        score_x: float,
        attack_dir: int,
        style: str,
        phase: int,
    ) -> tuple[tuple[float, float], str]:
        lane = (idx + phase) % 4
        wide_y = self._wide_lane_y(gamestate, player, lane)
        finish = (score_x + attack_dir * 76.0, wide_y)

        if style == "diamond":
            if idx == 0:
                target = (
                    holder.pos[0] + attack_dir * 185.0,
                    self._orbit_y(gamestate, holder.pos[1], phase, 1),
                )
                return target, "pivot"
            if idx == 1:
                deep_x = self._toward_score_x(gamestate, holder.pos[0], score_x, attack_dir, 760.0, inside_bonus=18.0)
                return (deep_x, self._wide_lane_y(gamestate, player, lane + 1)), "deep"
            return finish, "finish"

        if style == "cross":
            if idx == 0:
                under_x = self._toward_score_x(gamestate, holder.pos[0], score_x, attack_dir, 540.0, inside_bonus=0.0)
                return (under_x, self._cross_lane_y(gamestate, phase, 0)), "cross"
            if idx == 1:
                deep_x = self._toward_score_x(gamestate, holder.pos[0], score_x, attack_dir, 720.0, inside_bonus=0.0)
                return (deep_x, self._cross_lane_y(gamestate, phase, 1)), "deep"
            return finish, "backdoor"

        if style == "backdoor":
            if idx == 0:
                return finish, "finish"
            if idx == 1:
                deep_x = self._toward_score_x(gamestate, holder.pos[0], score_x, attack_dir, 820.0, inside_bonus=32.0)
                return (deep_x, self._wide_lane_y(gamestate, player, lane + 2)), "backdoor"
            pivot_x = self._toward_score_x(gamestate, holder.pos[0], score_x, attack_dir, 330.0, inside_bonus=0.0)
            return (pivot_x, self._orbit_y(gamestate, holder.pos[1], phase + idx, 0)), "pivot"

        if idx == 0:
            deep_x = self._toward_score_x(gamestate, holder.pos[0], score_x, attack_dir, 640.0, inside_bonus=0.0)
            return (deep_x, self._wide_lane_y(gamestate, player, lane + 1)), "deep"
        if idx == 1:
            return finish, "finish"
        under_x = self._toward_score_x(gamestate, holder.pos[0], score_x, attack_dir, 470.0, inside_bonus=0.0)
        return (under_x, self._cross_lane_y(gamestate, phase, idx)), "under"

    @staticmethod
    def _orbit_y(gamestate: GameStateSnap, base_y: float, phase: int, direction: int) -> float:
        h = gamestate.const.GAME_SIZE[1]
        offset = (170.0 + 45.0 * (phase % 2)) * direction
        return max(24.0, min(h - 24.0, base_y + offset))

    @staticmethod
    def _cross_lane_y(gamestate: GameStateSnap, phase: int, slot: int) -> float:
        h = gamestate.const.GAME_SIZE[1]
        lanes = (0.18, 0.38, 0.62, 0.82)
        index = (phase + slot * 2) % len(lanes)
        return h * lanes[index]

    def _build_defense_plan(self, gamestate: GameStateSnap, my_team: "TeamSnap", op_team: "TeamSnap", plan: TgerPlan) -> None:
        holder = self._holder(gamestate)
        if holder is None:
            return

        opponent_attack = -plan.attack_dir
        primary_defender = self._closest_player(my_team, holder.pos, exclude=())
        if primary_defender is not None:
            plan.target_by_player[primary_defender.player_key] = self._bound(
                gamestate,
                (holder.pos[0] + opponent_attack * self.MARK_DISTANCE, holder.pos[1]),
            )
            plan.role_by_player[primary_defender.player_key] = "mark_holder"

        receivers = [p for p in op_team.player_list if p.player_key != holder.player_key]
        receivers.sort(key=lambda p: self._receiver_intercept_score(gamestate, p, holder.pos, -plan.attack_dir))

        defenders = [p for p in my_team.player_list if p.player_key != getattr(primary_defender, "player_key", None)]
        if self._in_defensive_transition(gamestate):
            for idx, defender in enumerate(defenders):
                target = self._defensive_home_target(gamestate, holder, defender, opponent_attack, idx)
                plan.target_by_player[defender.player_key] = target
                plan.role_by_player[defender.player_key] = "recover_home"
            return

        for idx, defender in enumerate(defenders):
            if idx == 0 and receivers:
                target_op = receivers[0]
                target = self._lane_intercept_target(gamestate, holder, target_op, opponent_attack)
                role = "deny_lane"
            else:
                target = self._defensive_home_target(gamestate, holder, defender, opponent_attack, idx)
                role = "guard_zone"
            plan.target_by_player[defender.player_key] = self._bound(gamestate, target)
            plan.role_by_player[defender.player_key] = role

    def _build_free_plan(self, gamestate: GameStateSnap, my_team: "TeamSnap", op_team: "TeamSnap", plan: TgerPlan) -> None:
        preferred = None
        if gamestate.tick - self.last_attack_tick <= 140 and self.last_attack_receiver_key is not None:
            preferred = self.last_attack_receiver_key

        my_best = min((self._dist(player.pos, plan.catch_point) for player in my_team.player_list), default=1e9)
        op_best = min((self._dist(player.pos, plan.catch_point) for player in op_team.player_list), default=1e9)
        recovering = (
            gamestate.disc.state != "waiting"
            and op_best <= my_best + self.CONTESTED_RECOVERY_MARGIN
        )
        if recovering:
            plan.mode = "recover"

        chaser = None if recovering else self._pick_chaser(
            gamestate,
            my_team,
            op_team,
            plan.catch_point,
            plan.attack_dir,
            preferred,
        )
        plan.chaser_key = chaser.player_key if chaser is not None else None

        if chaser is not None:
            plan.target_by_player[chaser.player_key] = self._safe_catch_target(gamestate, chaser, plan.catch_point, op_team, plan.attack_dir)
            plan.role_by_player[chaser.player_key] = "chase" if not recovering else "recover_chase"

        for idx, player in enumerate(my_team.player_list):
            if chaser is not None and player.player_key == chaser.player_key:
                continue
            if recovering:
                target = self._recovery_target(gamestate, player, plan.catch_point, plan.attack_dir, idx)
                plan.target_by_player[player.player_key] = target
                plan.role_by_player[player.player_key] = "recover"
            else:
                target = self._transition_target(gamestate, player, plan.catch_point, plan.attack_dir, idx)
                plan.target_by_player[player.player_key] = target
                plan.role_by_player[player.player_key] = "pre_cut"

    def _pick_chaser(
        self,
        gamestate: GameStateSnap,
        my_team: "TeamSnap",
        op_team: "TeamSnap",
        catch_point: tuple[float, float],
        attack_dir: int,
        preferred: PlayerKey | None = None,
    ) -> "PlayerSnap | None":
        if preferred is not None:
            preferred_player = self._player(my_team, preferred)
            if preferred_player is not None:
                preferred_dist = self._dist(preferred_player.pos, catch_point)
            else:
                preferred_dist = 1e9
        else:
            preferred_player = None
            preferred_dist = 1e9

        best: PlayerSnap | None = None
        best_score = 1e9
        my_best = 1e9
        op_best = min((self._dist(op.pos, catch_point) for op in op_team.player_list), default=1e9)

        for player in my_team.player_list:
            d = self._dist(player.pos, catch_point)
            my_best = min(my_best, d)
            score = d
            score += max(0.0, 70.0 - self._nearest_opponent_distance(op_team, player.pos)) * 1.4
            score += max(0.0, 110.0 - self._progress_distance(player.pos, catch_point, attack_dir)) * 0.35
            if self._is_deep_backfield(gamestate, player, attack_dir):
                score += 45.0
            if preferred_player is not None and player.player_key == preferred and preferred_dist <= score + 60.0:
                score -= 110.0
            if score < best_score:
                best_score = score
                best = player

        if best is None:
            return None
        if best_score > 150.0 and op_best + 35.0 < my_best:
            return None
        return best

    def _rank_receivers(
        self,
        gamestate: GameStateSnap,
        holder: "PlayerSnap",
        my_team: "TeamSnap",
        op_team: "TeamSnap",
        attack_dir: int,
        plan: TgerPlan,
    ) -> list[PlayerKey]:
        scored: list[tuple[float, PlayerKey]] = []
        score_x = self._score_x(gamestate)
        for player in my_team.player_list:
            if player.player_key == holder.player_key:
                continue
            target = plan.target_by_player.get(player.player_key, player.pos)
            forward = max(0.0, (target[0] - holder.pos[0]) * attack_dir)
            toward_goal = max(0.0, (target[0] - score_x) * attack_dir)
            openness = self._nearest_opponent_distance(op_team, target)
            lane_clear = self._lane_clearance(op_team, holder.pos, target)
            edge = self._edge_distance(gamestate, target)
            dist = self._dist(holder.pos, target)
            run_dist = self._dist(player.pos, target)
            role = plan.role_by_player.get(player.player_key, "")
            score = (
                forward * 3.8
                + toward_goal * 6.6
                + min(openness, 230.0) * 1.8
                + min(lane_clear, 180.0) * 1.4
                + min(edge, 140.0) * 0.2
                - dist * 0.10
                - run_dist * 0.18
            )
            if role == "finish":
                score += 220.0
            elif role == "deep":
                score += 110.0
            elif role == "under":
                score += 120.0
            elif role == "backdoor":
                score += 205.0
            elif role == "pivot":
                score += 145.0
            elif role == "cross":
                score += 135.0
            if self._inside_enemy_score_area(gamestate, target):
                score += 1400.0
            if openness < 42.0:
                score -= 700.0
            scored.append((score, player.player_key))
        scored.sort(key=lambda item: (-item[0], item[1].player_id))
        return [key for _, key in scored]

    def _receiver_intercept_score(self, gamestate: GameStateSnap, receiver: "PlayerSnap", holder_pos: tuple[float, float], attack_dir: int) -> float:
        openness = self._nearest_opponent_distance(gamestate.team_list[self.team_id], receiver.pos)
        lane_clear = self._lane_clearance(gamestate.team_list[self.team_id], holder_pos, receiver.pos)
        forward = max(0.0, (receiver.pos[0] - holder_pos[0]) * attack_dir)
        return -(forward * 2.0 + min(openness, 180.0) * 1.3 + min(lane_clear, 160.0) * 0.8)

    def _safe_catch_target(self, gamestate: GameStateSnap, chaser: "PlayerSnap", catch_point: tuple[float, float], op_team: "TeamSnap", attack_dir: int) -> tuple[float, float]:
        nearest_op = self._closest_player(op_team, catch_point, exclude=())
        if nearest_op is None:
            return self._bound(gamestate, catch_point)
        op_dist = self._dist(nearest_op.pos, catch_point)
        my_dist = self._dist(chaser.pos, catch_point)
        if op_dist <= 64.0 and op_dist <= my_dist + 32.0:
            offset = (95.0 if attack_dir > 0 else -95.0)
            side = -90.0 if chaser.player_key.player_id % 2 == 0 else 90.0
            return self._bound(gamestate, (catch_point[0] + offset, catch_point[1] + side))
        return self._bound(gamestate, catch_point)

    def _support_target(self, gamestate: GameStateSnap, player: "PlayerSnap", catch_point: tuple[float, float], attack_dir: int, slot: int) -> tuple[float, float]:
        spacing = [120.0, 190.0, 260.0, 330.0]
        offset = spacing[slot % len(spacing)]
        side = -1.0 if (player.player_key.player_id + slot) % 2 == 0 else 1.0
        target = (catch_point[0] + attack_dir * offset, catch_point[1] + side * (70.0 + 18.0 * (slot % 3)))
        return self._bound(gamestate, target)

    def _recovery_target(
        self,
        gamestate: GameStateSnap,
        player: "PlayerSnap",
        catch_point: tuple[float, float],
        attack_dir: int,
        slot: int,
    ) -> tuple[float, float]:
        home_x = catch_point[0] - attack_dir * (180.0 + 130.0 * slot)
        lane_slot = (player.player_key.player_id + slot) % 4
        lane_y = self._wide_lane_y(gamestate, player, lane_slot)
        return self._bound(gamestate, (home_x, lane_y))

    def _defensive_home_target(
        self,
        gamestate: GameStateSnap,
        holder: "PlayerSnap",
        defender: "PlayerSnap",
        opponent_attack: int,
        slot: int,
    ) -> tuple[float, float]:
        defensive_edge = self._score_x_for_team(gamestate, 1 - self.team_id)
        depth = 110.0 + 150.0 * slot
        home_x = defensive_edge - opponent_attack * depth
        if (home_x - holder.pos[0]) * opponent_attack < 70.0:
            home_x = holder.pos[0] + opponent_attack * 70.0
        lane_y = self._wide_lane_y(gamestate, defender, slot + 1)
        return self._bound(gamestate, (home_x, lane_y))

    def _lane_intercept_target(
        self,
        gamestate: GameStateSnap,
        holder: "PlayerSnap",
        receiver: "PlayerSnap",
        opponent_attack: int,
    ) -> tuple[float, float]:
        target_x = holder.pos[0] + (receiver.pos[0] - holder.pos[0]) * 0.45
        if (target_x - holder.pos[0]) * opponent_attack < 70.0:
            target_x = holder.pos[0] + opponent_attack * 70.0
        return self._bound(gamestate, (target_x, receiver.pos[1]))

    def _transition_target(
        self,
        gamestate: GameStateSnap,
        player: "PlayerSnap",
        catch_point: tuple[float, float],
        attack_dir: int,
        slot: int,
    ) -> tuple[float, float]:
        score_x = self._score_x(gamestate)
        pid = player.player_key.player_id
        if pid >= 2:
            target_x = score_x + attack_dir * (120.0 if pid == 3 else -70.0)
            lane_slot = 3 if pid == 3 else 1
        elif pid == 1:
            target_x = self._toward_score_x(gamestate, catch_point[0], score_x, attack_dir, 740.0, inside_bonus=0.0)
            lane_slot = 2
        else:
            target_x = catch_point[0] - attack_dir * 140.0
            lane_slot = 0
        return self._bound(gamestate, (target_x, self._wide_lane_y(gamestate, player, lane_slot)))

    @staticmethod
    def _attack_role_order(
        players: list["PlayerSnap"],
        holder: "PlayerSnap",
        score_x: float,
        attack_dir: int,
    ) -> list["PlayerSnap"]:
        forward = (holder.pos[0] - score_x) * attack_dir
        if forward < 360.0:
            priority = {2: 0, 3: 1, 1: 2, 0: 3}
        else:
            priority = {3: 0, 2: 1, 1: 2, 0: 3}
        return sorted(
            players,
            key=lambda p: (
                priority.get(p.player_key.player_id, 9),
                -p.player_key.player_id,
            ),
        )

    def _toward_score_x(
        self,
        gamestate: GameStateSnap,
        base_x: float,
        score_x: float,
        attack_dir: int,
        advance: float,
        inside_bonus: float,
    ) -> float:
        desired = base_x + attack_dir * advance
        inside = score_x + attack_dir * inside_bonus
        if (desired - inside) * attack_dir > 0.0:
            desired = inside
        return self._bound(gamestate, (desired, gamestate.const.GAME_SIZE[1] / 2.0))[0]

    @staticmethod
    def _wide_lane_y(gamestate: GameStateSnap, player: "PlayerSnap", slot: int) -> float:
        h = gamestate.const.GAME_SIZE[1]
        lanes = (0.17, 0.36, 0.64, 0.83)
        y = h * lanes[slot % len(lanes)]
        drift = ((gamestate.tick // 80 + player.player_key.player_id + slot) % 3 - 1) * 18.0
        return max(18.0, min(h - 18.0, y + drift))

    def _repel_from_team(
        self,
        gamestate: GameStateSnap,
        target: tuple[float, float],
        players: tuple["PlayerSnap", ...],
        exclude: PlayerKey,
    ) -> tuple[float, float]:
        tx, ty = target
        for player in players:
            if player.player_key == exclude:
                continue
            d = self._dist((tx, ty), player.pos)
            if 0.01 < d < self.SAFE_TOUCH_GAP:
                tx += (tx - player.pos[0]) / d * (self.SAFE_TOUCH_GAP - d)
                ty += (ty - player.pos[1]) / d * (self.SAFE_TOUCH_GAP - d)
        return self._bound(gamestate, (tx, ty))

    def _attack_dir(self) -> int:
        return 1 if self.team_id == 0 else -1

    @staticmethod
    def _progress_distance(from_pos: tuple[float, float], to_pos: tuple[float, float], attack_dir: int) -> float:
        return (to_pos[0] - from_pos[0]) * attack_dir

    @staticmethod
    def _predict_landing(gamestate: GameStateSnap) -> tuple[float, float]:
        disc = gamestate.disc
        c = gamestate.const
        x, y, z = disc.pos
        vx, vy, vz = disc.velocity
        if disc.state == "waiting":
            return (x, y)
        target_z = c.CATCH_HIGHT
        a = 0.5 * c.GRAVITY
        b = vz
        cc = z - target_z
        t = 0.0
        if abs(a) > 0.0001:
            root = b * b - 4.0 * a * cc
            if root >= 0.0:
                s = sqrt(root)
                candidates = [(-b + s) / (2.0 * a), (-b - s) / (2.0 * a)]
                future = [v for v in candidates if v > 0.0]
                if future:
                    t = max(future)
        if t <= 0.0:
            t = 0.45 if vz >= 0.0 else max(0.0, -z / min(vz, -0.01))
        return (x + vx * t, y + vy * t)

    @staticmethod
    def _bound(gamestate: GameStateSnap, pos: tuple[float, float]) -> tuple[float, float]:
        w, h = gamestate.const.GAME_SIZE
        return (
            max(12.0, min(w - 12.0, pos[0])),
            max(12.0, min(h - 12.0, pos[1])),
        )

    @staticmethod
    def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
        return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    @staticmethod
    def _edge_distance(gamestate: GameStateSnap, pos: tuple[float, float]) -> float:
        w, h = gamestate.const.GAME_SIZE
        return min(pos[0], w - pos[0], pos[1], h - pos[1])

    @staticmethod
    def _nearest_opponent_distance(op_team: "TeamSnap", pos: tuple[float, float]) -> float:
        return min((sqrt((player.pos[0] - pos[0]) ** 2 + (player.pos[1] - pos[1]) ** 2) for player in op_team.player_list), default=1e9)

    @staticmethod
    def _lane_clearance(op_team: "TeamSnap", a: tuple[float, float], b: tuple[float, float]) -> float:
        best = 1e9
        for player in op_team.player_list:
            best = min(best, TgerCoach._point_segment_distance(player.pos, a, b))
        return best

    @staticmethod
    def _point_segment_distance(point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        ax, ay = a
        bx, by = b
        px, py = point
        abx = bx - ax
        aby = by - ay
        den = abx * abx + aby * aby
        if den <= 0.001:
            return sqrt((px - ax) ** 2 + (py - ay) ** 2)
        t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / den))
        cx = ax + abx * t
        cy = ay + aby * t
        return sqrt((px - cx) ** 2 + (py - cy) ** 2)

    @staticmethod
    def _player(team: "TeamSnap", key: PlayerKey) -> "PlayerSnap | None":
        for player in team.player_list:
            if player.player_key == key:
                return player
        return None

    @staticmethod
    def _holder(gamestate: GameStateSnap) -> "PlayerSnap | None":
        key = gamestate.disc.holder_key
        if key is None:
            return None
        return gamestate.team_list[key.team_id].player_list[key.player_id]

    @staticmethod
    def _closest_player(team: "TeamSnap", pos: tuple[float, float], exclude: tuple[PlayerKey, ...]) -> "PlayerSnap | None":
        best: PlayerSnap | None = None
        best_d = 1e9
        for player in team.player_list:
            if player.player_key in exclude:
                continue
            d = sqrt((player.pos[0] - pos[0]) ** 2 + (player.pos[1] - pos[1]) ** 2)
            if d < best_d:
                best_d = d
                best = player
        return best

    @staticmethod
    def _score_x_for_team(gamestate: GameStateSnap, team_id: int) -> float:
        if team_id == gamestate.const.BLUE_TEAM_ID:
            return gamestate.const.BLUE_SCORE_AREA[0]
        return gamestate.const.RED_SCORE_AREA[0] + gamestate.const.RED_SCORE_AREA[2]

    def _score_x(self, gamestate: GameStateSnap) -> float:
        return self._score_x_for_team(gamestate, self.team_id)

    def _inside_enemy_score_area(self, gamestate: GameStateSnap, pos: tuple[float, float]) -> bool:
        if self.team_id == gamestate.const.BLUE_TEAM_ID and pos[0] >= gamestate.const.BLUE_SCORE_AREA[0]:
            return True
        if self.team_id == gamestate.const.RED_TEAM_ID and pos[0] <= gamestate.const.RED_SCORE_AREA[0] + gamestate.const.RED_SCORE_AREA[2]:
            return True
        return False

    @staticmethod
    def _lane_y(gamestate: GameStateSnap, player: "PlayerSnap", slot: int) -> float:
        h = gamestate.const.GAME_SIZE[1]
        count = max(1, len(gamestate.team_list[player.player_key.team_id].player_list))
        base = h * (player.player_key.player_id + 1) / (count + 1)
        wobble = ((gamestate.tick // 90 + slot + player.player_key.player_id) % 3 - 1) * 28.0
        return max(12.0, min(h - 12.0, base + wobble))

    @staticmethod
    def _is_deep_backfield(gamestate: GameStateSnap, player: "PlayerSnap", attack_dir: int) -> bool:
        holder = TgerCoach._holder(gamestate)
        if holder is None:
            return False
        return (player.pos[0] - holder.pos[0]) * attack_dir < -80.0


class TgerAgent(AgentBase[TgerPlan]):
    HOLD_BEFORE_THROW_SECONDS: float = 0.0
    THROW_RECOVERY_SECONDS: float = 0.42
    CATCH_COOLDOWN_SECONDS: float = 0.14
    THROW_Z_SPEED: float = 5.5
    MIN_THROW_DISTANCE: float = 24.0
    MAX_THROW_DISTANCE: float = 1400.0
    CATCH_CLEARANCE: float = 42.0
    CATCH_DANGER_DISTANCE: float = 42.0
    NO_TOUCH_DISTANCE: float = 42.0
    OPENING_MAX_DISTANCE: float = 340.0
    OPENING_MIN_OPENNESS: float = 70.0
    OPENING_MIN_LANE_CLEAR: float = 58.0
    AGGRESSIVE_RUN_FACTOR: float = 0.95
    TRANSITION_RUN_FACTOR: float = 0.74

    def init(self, player_key: PlayerKey) -> None:
        self.player_key = player_key
        self.hold_seconds = 0.0
        self.throw_recovery = 0.0
        self.catch_cooldown = 0.0
        self.last_team_possession: int | None = None
        self.opening_pass_pending = False
        self.last_disc_state: str = "waiting"

    def agent(self, gamestate: GameStateSnap, plan: TgerPlan | None = None) -> list[Intent]:
        me = self._me(gamestate)
        disc = gamestate.disc
        dt = gamestate.delta_time

        self._update_possession_state(gamestate)
        self.throw_recovery = max(0.0, self.throw_recovery - dt)
        self.catch_cooldown = max(0.0, self.catch_cooldown - dt)
        if me.hold_disc and disc.holder_key == self.player_key:
            self.hold_seconds += dt
        else:
            self.hold_seconds = 0.0

        if me.hold_disc and disc.holder_key == self.player_key and disc.state == "catched":
            if self.hold_seconds < self.HOLD_BEFORE_THROW_SECONDS:
                return []
            return self._throw_action(gamestate, me, plan)

        if self._can_catch_now(gamestate, me) and self._should_catch(gamestate, me, plan):
            self.catch_cooldown = self.CATCH_COOLDOWN_SECONDS
            return [CatchIntent(disc_id=0)]

        if disc.holder_key is not None and disc.holder_key.team_id == self.player_key.team_id:
            return self._attack_move(gamestate, me, plan)

        if disc.holder_key is not None and disc.holder_key.team_id != self.player_key.team_id:
            return self._defense_move(gamestate, me, plan)

        return self._free_move(gamestate, me, plan)

    def _update_possession_state(self, gamestate: GameStateSnap) -> None:
        disc = gamestate.disc
        previous_state = self.last_disc_state
        if disc.state == "waiting":
            self.last_team_possession = None
            self.opening_pass_pending = False
            self.last_disc_state = disc.state
            return
        if disc.holder_key is None:
            self.last_disc_state = disc.state
            return

        team_id = disc.holder_key.team_id
        if team_id != self.last_team_possession:
            self.opening_pass_pending = team_id == self.player_key.team_id
            self.last_team_possession = team_id
        elif (
            team_id == self.player_key.team_id
            and previous_state in ("flying", "competing")
        ):
            self.opening_pass_pending = False
        self.last_disc_state = disc.state

    def _throw_action(self, gamestate: GameStateSnap, me: "PlayerSnap", plan: TgerPlan | None) -> list[Intent]:
        safe_transition = self.opening_pass_pending
        attack_plan = (
            plan
            if plan is not None and plan.mode == "attack" and plan.holder_key == self.player_key
            else None
        )
        receiver = self._opening_receiver(gamestate, me) if safe_transition else self._best_receiver(gamestate, me, attack_plan)
        if receiver is None:
            return []
        throw_point = (
            self._opening_throw_point(gamestate, me, receiver)
            if safe_transition
            else self._receiver_lead_point(gamestate, me, receiver, attack_plan)
        )
        motion = self._throw_motion(gamestate, me.pos, throw_point)
        if motion is None:
            return []
        self.hold_seconds = 0.0
        self.throw_recovery = self.THROW_RECOVERY_SECONDS
        self.opening_pass_pending = False
        return [ThrowIntent(disc_id=0, motion=motion)]

    def _opening_receiver(self, gamestate: GameStateSnap, me: "PlayerSnap") -> "PlayerSnap | None":
        my_team = self._my_team(gamestate)
        op_team = self._op_team(gamestate)
        attack_dir = self._attack_dir()
        best: PlayerSnap | None = None
        best_score = -1e9

        for teammate in my_team.player_list:
            if teammate.player_key == self.player_key:
                continue
            target = self._opening_throw_target(gamestate, teammate)
            throw_dist = self._dist(me.pos, target)
            if throw_dist < 90.0 or throw_dist > self.OPENING_MAX_DISTANCE:
                continue

            openness = min((self._dist(target, op.pos) for op in op_team.player_list), default=999.0)
            lane_clear = min(
                (self._point_segment_distance(op.pos, me.pos, target) for op in op_team.player_list),
                default=999.0,
            )
            run_dist = self._dist(teammate.pos, target)
            if openness < self.OPENING_MIN_OPENNESS or lane_clear < self.OPENING_MIN_LANE_CLEAR:
                continue

            forward = max(0.0, (target[0] - me.pos[0]) * attack_dir)
            side_step = abs(target[1] - me.pos[1])
            score = (
                min(openness, 260.0) * 2.4
                + min(lane_clear, 220.0) * 2.0
                + min(forward, 180.0) * 0.7
                + min(side_step, 260.0) * 0.45
                - throw_dist * 0.20
                - run_dist * 0.95
            )
            if score > best_score:
                best_score = score
                best = teammate
        return best

    def _opening_throw_target(self, gamestate: GameStateSnap, receiver: "PlayerSnap") -> tuple[float, float]:
        attack_dir = self._attack_dir()
        return self._bound(
            gamestate,
            (receiver.pos[0] + attack_dir * 70.0, receiver.pos[1]),
        )

    def _opening_throw_point(
        self,
        gamestate: GameStateSnap,
        holder: "PlayerSnap",
        receiver: "PlayerSnap",
    ) -> tuple[float, float]:
        target = self._opening_throw_target(gamestate, receiver)
        distance = self._dist(holder.pos, target)
        vz = self._planned_throw_z(distance, "under")
        flight_time = 2.0 * vz / abs(gamestate.const.GRAVITY)
        max_run = gamestate.const.PLAYER_SPEED * flight_time * 0.66
        run_dist = self._dist(receiver.pos, target)
        if run_dist > max_run and run_dist > 0.001:
            ratio = max_run / run_dist
            target = (
                receiver.pos[0] + (target[0] - receiver.pos[0]) * ratio,
                receiver.pos[1] + (target[1] - receiver.pos[1]) * ratio,
            )
        return self._bound(gamestate, target)

    def _best_receiver(self, gamestate: GameStateSnap, me: "PlayerSnap", plan: TgerPlan | None) -> "PlayerSnap | None":
        my_team = self._my_team(gamestate)
        op_team = self._op_team(gamestate)
        attack_dir = self._attack_dir()
        score_x = gamestate.const.BLUE_SCORE_AREA[0] if attack_dir > 0 else gamestate.const.RED_SCORE_AREA[0] + gamestate.const.RED_SCORE_AREA[2]

        priority = {}
        if plan is not None and plan.receiver_priority:
            priority = {key: len(plan.receiver_priority) - idx for idx, key in enumerate(plan.receiver_priority)}

        best: PlayerSnap | None = None
        best_score = -1e9
        for teammate in my_team.player_list:
            if teammate.player_key == self.player_key:
                continue
            target_pos = self._receiver_lead_point(gamestate, me, teammate, plan)
            dist = self._dist(me.pos, target_pos)
            if dist < self.MIN_THROW_DISTANCE or dist > self.MAX_THROW_DISTANCE:
                continue
            run_dist = self._dist(teammate.pos, target_pos)
            forward = max(0.0, (target_pos[0] - me.pos[0]) * attack_dir)
            toward_goal = max(0.0, (target_pos[0] - score_x) * attack_dir)
            openness = min((self._dist(target_pos, op.pos) for op in op_team.player_list), default=999.0)
            lane_clear = min((self._point_segment_distance(op.pos, me.pos, target_pos) for op in op_team.player_list), default=999.0)
            if openness < 58.0 or lane_clear < 30.0:
                continue

            score = (
                forward * 2.8
                + toward_goal * 5.0
                + min(openness, 180.0) * 1.7
                + min(lane_clear, 150.0) * 1.1
                - dist * 0.10
                - run_dist * 0.14
                - max(0.0, 70.0 - openness) * 5.0
                - max(0.0, 42.0 - lane_clear) * 9.0
            )
            if plan is not None:
                score += priority.get(teammate.player_key, 0) * 40.0
                role = plan.role_by_player.get(teammate.player_key)
                if role == "primary":
                    score += 150.0
                elif role == "secondary":
                    score += 70.0
                elif role == "finish":
                    score += 120.0
                elif role == "backdoor":
                    score += 115.0
                elif role == "pivot":
                    score += 95.0
                elif role == "cross":
                    score += 85.0
            if target_pos[0] >= gamestate.const.BLUE_SCORE_AREA[0] or target_pos[0] <= gamestate.const.RED_SCORE_AREA[0] + gamestate.const.RED_SCORE_AREA[2]:
                score += 700.0
            if score > best_score:
                best_score = score
                best = teammate
        return best

    @staticmethod
    def _closest_teammate(me: "PlayerSnap", team: "TeamSnap") -> "PlayerSnap | None":
        best: PlayerSnap | None = None
        best_d = 1e9
        for player in team.player_list:
            if player.player_key == me.player_key:
                continue
            d = sqrt((player.pos[0] - me.pos[0]) ** 2 + (player.pos[1] - me.pos[1]) ** 2)
            if d < best_d:
                best_d = d
                best = player
        return best

    def _receiver_lead_point(
        self,
        gamestate: GameStateSnap,
        holder: "PlayerSnap",
        receiver: "PlayerSnap",
        plan: TgerPlan | None,
    ) -> tuple[float, float]:
        target = receiver.pos
        if plan is not None:
            target = plan.target_by_player.get(receiver.player_key, receiver.pos)
        target = self._bound(gamestate, target)

        role = plan.role_by_player.get(receiver.player_key, "") if plan is not None else ""
        vz = self._planned_throw_z(self._dist(holder.pos, target), role)
        flight_time = 2.0 * vz / abs(gamestate.const.GRAVITY)
        run_factor = self.AGGRESSIVE_RUN_FACTOR if plan is not None else self.TRANSITION_RUN_FACTOR
        max_run = gamestate.const.PLAYER_SPEED * flight_time * run_factor
        rx, ry = receiver.pos
        dx = target[0] - rx
        dy = target[1] - ry
        run_dist = sqrt(dx * dx + dy * dy)
        if run_dist > max_run and run_dist > 0.001:
            ratio = max_run / run_dist
            target = (rx + dx * ratio, ry + dy * ratio)

        throw_dist = self._dist(holder.pos, target)
        if throw_dist < self.MIN_THROW_DISTANCE:
            attack_dir = self._attack_dir()
            target = (target[0] + attack_dir * (self.MIN_THROW_DISTANCE - throw_dist + 8.0), target[1])
        return self._bound(gamestate, target)

    def _attack_move(self, gamestate: GameStateSnap, me: "PlayerSnap", plan: TgerPlan | None) -> list[Intent]:
        if plan is None:
            return []
        target = plan.target_by_player.get(self.player_key)
        if target is None:
            return []
        target = self._keep_away(gamestate, target, self._holder(gamestate))
        return self._move_toward(gamestate, me, target)

    def _defense_move(self, gamestate: GameStateSnap, me: "PlayerSnap", plan: TgerPlan | None) -> list[Intent]:
        if plan is None:
            return []
        target = plan.target_by_player.get(self.player_key)
        if target is None:
            return []
        holder = self._holder(gamestate)
        if holder is not None:
            target = self._keep_away(gamestate, target, holder)
        return self._move_toward(gamestate, me, target)

    def _free_move(self, gamestate: GameStateSnap, me: "PlayerSnap", plan: TgerPlan | None) -> list[Intent]:
        if plan is None:
            catch_point = self._predict_landing(gamestate)
            return self._move_toward(gamestate, me, catch_point)
        if self.opening_pass_pending and gamestate.disc.state in ("flying", "competing"):
            catch_point = self._predict_landing(gamestate)
            my_dist = self._dist(me.pos, catch_point)
            teammate_dist = min(
                (
                    self._dist(player.pos, catch_point)
                    for player in self._my_team(gamestate).player_list
                    if player.player_key != self.player_key
                ),
                default=1e9,
            )
            if my_dist <= teammate_dist + 12.0:
                return self._move_toward(gamestate, me, catch_point)
        target = plan.target_by_player.get(self.player_key)
        if target is None:
            target = plan.catch_point
        return self._move_toward(gamestate, me, target)

    def _should_catch(self, gamestate: GameStateSnap, me: "PlayerSnap", plan: TgerPlan | None) -> bool:
        if self.catch_cooldown > 0.0:
            return False
        disc = gamestate.disc
        if self._inside_own_score_area(gamestate, me.pos):
            return True

        catch_xy = (disc.pos[0], disc.pos[1])
        my_d = self._dist(me.pos, catch_xy)
        nearest_op = min((self._dist(op.pos, catch_xy) for op in self._op_team(gamestate).player_list), default=999.0)
        if plan is not None and plan.mode == "recover":
            return plan.chaser_key == self.player_key
        if disc.state == "waiting":
            if plan is None or plan.chaser_key == self.player_key:
                return True
            return my_d <= nearest_op + 10.0
        if plan is not None and plan.chaser_key is not None and plan.chaser_key != self.player_key:
            if my_d > nearest_op + 14.0 and my_d > gamestate.const.CATCH_DISTANCE * 0.75:
                return False
        if nearest_op <= self.CATCH_CLEARANCE and my_d > gamestate.const.CATCH_DISTANCE * 0.45:
            return False
        return True

    def _can_catch_now(self, gamestate: GameStateSnap, me: "PlayerSnap") -> bool:
        disc = gamestate.disc
        if disc.holder_key is not None or me.hold_disc:
            return False
        if disc.state not in ("flying", "competing", "waiting"):
            return False
        if disc.pos[2] > gamestate.const.CATCH_HIGHT:
            return False
        return self._dist(me.pos, (disc.pos[0], disc.pos[1])) <= gamestate.const.CATCH_DISTANCE

    def _throw_motion(self, gamestate: GameStateSnap, from_pos: tuple[float, float], to_pos: tuple[float, float]) -> tuple[int, int, int] | None:
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        dist = sqrt(dx * dx + dy * dy)
        if dist < 1.0:
            return None
        vz = self._planned_throw_z(dist, "finish" if dist > 450.0 else "deep" if dist > 220.0 else "under")
        flight_time = max(0.28, 2.0 * vz / abs(gamestate.const.GRAVITY))
        vx = dx / flight_time
        vy = dy / flight_time
        speed = sqrt(vx * vx + vy * vy)
        if speed < gamestate.const.MIN_VELOCITY:
            scale = gamestate.const.MIN_VELOCITY / max(speed, 0.01)
            vx *= scale
            vy *= scale
        return (int(round(vx)), int(round(vy)), int(round(vz)))

    @staticmethod
    def _planned_throw_z(distance: float, role: str = "") -> float:
        if role == "finish":
            return max(5.2, min(8.5, 5.7 + distance / 290.0))
        if role == "deep":
            return max(5.7, min(9.5, 6.1 + distance / 245.0))
        return max(6.0, min(10.4, 6.5 + distance / 195.0))

    def _move_toward(self, gamestate: GameStateSnap, me: "PlayerSnap", target: tuple[float, float]) -> list[Intent]:
        target = self._bound(gamestate, target)
        step = self._step(me.pos, target, gamestate.const.PLAYER_SPEED, gamestate.delta_time)
        return [MoveIntent(target_pos=(float(step[0]), float(step[1])))]

    def _keep_away(self, gamestate: GameStateSnap, target: tuple[float, float], holder: "PlayerSnap | None") -> tuple[float, float]:
        if holder is None:
            return self._bound(gamestate, target)
        tx, ty = target
        d = self._dist((tx, ty), holder.pos)
        if d < self.NO_TOUCH_DISTANCE:
            if d < 0.01:
                attack_dir = self._attack_dir()
                return self._bound(gamestate, (holder.pos[0] - attack_dir * self.NO_TOUCH_DISTANCE, holder.pos[1]))
            ratio = self.NO_TOUCH_DISTANCE / d
            tx = holder.pos[0] + (tx - holder.pos[0]) * ratio
            ty = holder.pos[1] + (ty - holder.pos[1]) * ratio
        return self._bound(gamestate, (tx, ty))

    def _holder(self, gamestate: GameStateSnap) -> "PlayerSnap | None":
        key = gamestate.disc.holder_key
        if key is None:
            return None
        return gamestate.team_list[key.team_id].player_list[key.player_id]

    def _my_team(self, gamestate: GameStateSnap) -> "TeamSnap":
        return gamestate.team_list[self.player_key.team_id]

    def _op_team(self, gamestate: GameStateSnap) -> "TeamSnap":
        return gamestate.team_list[1 - self.player_key.team_id]

    def _me(self, gamestate: GameStateSnap) -> "PlayerSnap":
        return gamestate.team_list[self.player_key.team_id].player_list[self.player_key.player_id]

    def _attack_dir(self) -> int:
        return 1 if self.player_key.team_id == 0 else -1

    @staticmethod
    def _predict_landing(gamestate: GameStateSnap) -> tuple[float, float]:
        disc = gamestate.disc
        c = gamestate.const
        x, y, z = disc.pos
        vx, vy, vz = disc.velocity
        if disc.state == "waiting":
            return (x, y)
        a = 0.5 * c.GRAVITY
        b = vz
        cc = z - c.CATCH_HIGHT
        t = 0.0
        if abs(a) > 0.0001:
            root = b * b - 4.0 * a * cc
            if root >= 0.0:
                s = sqrt(root)
                candidates = [(-b + s) / (2.0 * a), (-b - s) / (2.0 * a)]
                future = [v for v in candidates if v > 0.0]
                if future:
                    t = max(future)
        if t <= 0.0:
            t = 0.45 if vz >= 0.0 else max(0.0, -z / min(vz, -0.01))
        return (x + vx * t, y + vy * t)

    @staticmethod
    def _step(from_pos: tuple[float, float], to_pos: tuple[float, float], speed: float, dt: float) -> tuple[float, float]:
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        dist = sqrt(dx * dx + dy * dy)
        max_step = speed * dt * 0.98
        if dist <= max_step or dist <= 0.001:
            return (float(to_pos[0]), float(to_pos[1]))
        ratio = max_step / dist
        return (from_pos[0] + dx * ratio, from_pos[1] + dy * ratio)

    @staticmethod
    def _bound(gamestate: GameStateSnap, pos: tuple[float, float]) -> tuple[float, float]:
        w, h = gamestate.const.GAME_SIZE
        return (max(12.0, min(w - 12.0, pos[0])), max(12.0, min(h - 12.0, pos[1])))

    @staticmethod
    def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
        return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    @staticmethod
    def _point_segment_distance(point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        ax, ay = a
        bx, by = b
        px, py = point
        abx = bx - ax
        aby = by - ay
        den = abx * abx + aby * aby
        if den <= 0.001:
            return sqrt((px - ax) ** 2 + (py - ay) ** 2)
        t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / den))
        cx = ax + abx * t
        cy = ay + aby * t
        return sqrt((px - cx) ** 2 + (py - cy) ** 2)

    def _inside_own_score_area(self, gamestate: GameStateSnap, pos: tuple[float, float]) -> bool:
        if self.player_key.team_id == gamestate.const.BLUE_TEAM_ID:
            area = gamestate.const.BLUE_SCORE_AREA
        else:
            area = gamestate.const.RED_SCORE_AREA
        return area[0] <= pos[0] <= area[0] + area[2] and area[1] <= pos[1] <= area[1] + area[3]

    @staticmethod
    def _is_deep_backfield(gamestate: GameStateSnap, player: "PlayerSnap", attack_dir: int) -> bool:
        holder = TgerAgent._holder_static(gamestate)
        if holder is None:
            return False
        return (player.pos[0] - holder.pos[0]) * attack_dir < -90.0

    @staticmethod
    def _holder_static(gamestate: GameStateSnap) -> "PlayerSnap | None":
        key = gamestate.disc.holder_key
        if key is None:
            return None
        return gamestate.team_list[key.team_id].player_list[key.player_id]


TgerTeamAgent = TgerCoach

__all__ = ["TgerPlan", "TgerAgent", "TgerCoach", "TgerTeamAgent"]
