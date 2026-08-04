"""
tger_agent — 飞盘游戏智能体

策略:
  持盘: 评估队友站位（偏前方、防守空、边界安全），直接传盘
  自由盘(flying): 全队追盘接盘
  自由盘(waiting/competing): P0/P1 追盘, P2/P3 前插跑位
  队友持盘: 向得分区方向分散跑位
  对手持盘: 最近者压迫持盘手，其余退防
"""

from __future__ import annotations

from math import sqrt
from typing import TYPE_CHECKING

from entities import PlayerKey
from systems import AgentBase, CatchIntent, MoveIntent, ThrowIntent, Intent

if TYPE_CHECKING:
    from systems import GameStateSnap



class TgerAgent(AgentBase):
    player_key: PlayerKey

    THROW_SPEED: float = 380.0
    MIN_THROW_TIME: float = 0.8
    MAX_THROW_DISTANCE: float = 520.0
    SPREAD: float = 80.0
    DEFEND_GAP: float = 50.0
    HOLD_BEFORE_THROW_SECONDS: float = 0.18
    THROW_RECOVERY_SECONDS: float = 0.8
    CATCH_COOLDOWN_SECONDS: float = 0.15
    SUPPORT_GAP: float = 320.0
    POSITION_EPSILON: float = 1.0
    FOUL_RADIUS: float = 36.0
    SAFE_MARK_RADIUS: float = 68.0
    CATCH_DANGER_RADIUS: float = 44.0
    ORBIT_RADIUS: float = 72.0
    ACTIVE_CHASERS_PER_TEAM: int = 2

    def init(self, player_key: PlayerKey) -> None:
        self.player_key = player_key
        self.hold_elapsed = 0.0
        self.throw_recovery_elapsed = 0.0
        self.catch_cooldown_elapsed = 0.0

    def _me(self, state: GameStateSnap):
        return state.team_list[self.player_key.team_id].player_list[self.player_key.player_id]

    def _my_team(self, state: GameStateSnap):
        return state.team_list[self.player_key.team_id]

    def _op_team(self, state: GameStateSnap):
        return state.team_list[1 - self.player_key.team_id]

    def _distance2d(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _dir_to(self, from_pos: tuple[float, float], to_pos: tuple[float, float]) -> tuple[float, float]:
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        dist = sqrt(dx * dx + dy * dy)
        if dist <= self.POSITION_EPSILON:
            return (0.0, 0.0)
        return (dx / dist, dy / dist)

    def _attack_direction(self) -> int:
        return 1 if self.player_key.team_id == 0 else -1

    def _predict_catch_point(self, state: GameStateSnap) -> tuple[float, float]:
        disc = state.disc
        c = state.const
        x, y, z = disc.pos
        vx, vy, vz = disc.velocity
        g = c.GRAVITY

        if z <= c.CATCH_HIGHT:
            return (x, y)

        a = 0.5 * g
        b = vz
        c0 = z - c.CATCH_HIGHT
        disc_val = b * b - 4 * a * c0
        if disc_val < 0:
            return (x + vx * 0.4, y + vy * 0.4)

        sqrt_val = sqrt(disc_val)
        t1 = (-b - sqrt_val) / (2 * a) if a != 0 else 0.0
        t2 = (-b + sqrt_val) / (2 * a) if a != 0 else 0.0
        candidates = [t for t in (t1, t2) if t > 0]
        if not candidates:
            return (x, y)

        t = min(candidates)
        return (x + vx * t, y + vy * t)

    def agent(self, gamestate: GameStateSnap) -> list[Intent]:
        me = self._me(gamestate)
        disc = gamestate.disc
        c = gamestate.const
        dt = gamestate.delta_time

        if disc.state == "waiting":
            self.hold_elapsed = 0.0
            self.throw_recovery_elapsed = 0.0
            self.catch_cooldown_elapsed = 0.0

        if self.throw_recovery_elapsed > 0:
            self.throw_recovery_elapsed = max(0.0, self.throw_recovery_elapsed - dt)
        if self.catch_cooldown_elapsed > 0:
            self.catch_cooldown_elapsed = max(0.0, self.catch_cooldown_elapsed - dt)
        if me.hold_disc and disc.holder_key == self.player_key:
            self.hold_elapsed += dt
        else:
            self.hold_elapsed = 0.0

        my_tid = self.player_key.team_id
        op_tid = 1 - my_tid
        my_team = gamestate.team_list[my_tid]
        op_team = gamestate.team_list[op_tid]

        atk = 1 if my_tid == c.BLUE_TEAM_ID else -1

        if me.hold_disc and disc.holder_key == self.player_key:
            if self.hold_elapsed < self.HOLD_BEFORE_THROW_SECONDS:
                return []
            return self._throw(gamestate, me, my_team, op_team, atk)

        if disc.state == "flying":
            catch_point = self._predict_catch_point(gamestate)
            if self.throw_recovery_elapsed > 0:
                return self._free_support(gamestate, me, disc, my_team, atk, catch_point)
            if self._is_active_chaser(me, gamestate, catch_point):
                return self._free_chase(gamestate, me, disc, catch_point, atk)
            return self._free_support(gamestate, me, disc, my_team, atk, catch_point)

        if disc.state in ("waiting", "competing") and disc.holder_key is None:
            catch_point = self._predict_catch_point(gamestate)
            if self._is_active_chaser(me, gamestate, catch_point):
                return self._free_chase(gamestate, me, disc, catch_point, atk)
            return self._free_support(gamestate, me, disc, my_team, atk, catch_point)

        if disc.holder_key is not None and disc.holder_key.team_id == my_tid:
            return self._off_pos(gamestate, me, my_team, op_team, atk)

        if disc.holder_key is not None and disc.holder_key.team_id == op_tid:
            return self._def_pos(gamestate, me, disc, op_team, atk)

        return []

    def _throw(self, gamestate, me, my_team, op_team, atk: int) -> list[Intent]:
        c = gamestate.const
        best = self._best_receiver(c, me, my_team, op_team, atk)
        if best is None:
            best = self._closest_teammate(me, my_team)
            if best is None:
                return []

        motion = self._calc_throw(me.pos, best.pos, c)
        if motion is None:
            return []

        self.throw_recovery_elapsed = self.THROW_RECOVERY_SECONDS
        self.hold_elapsed = 0.0
        return [ThrowIntent(disc_id=0, motion=motion)]

    def _best_receiver(self, c, me, my_team, op_team, atk: int):
        best_score = -1e9
        best_tgt = None
        fw, fh = c.GAME_SIZE
        mx, my_pos = me.pos

        frontier = 0.0
        for teammate in my_team.player_list:
            if teammate.player_key == self.player_key:
                continue
            frontier = max(frontier, max(0.0, (teammate.pos[0] - mx) * atk))

        for teammate in my_team.player_list:
            if teammate.player_key == self.player_key:
                continue

            tx, ty = teammate.pos
            d = self._d2(me.pos, teammate.pos)
            if d < 40 or d > self.MAX_THROW_DISTANCE:
                continue

            fwd = (tx - mx) * atk
            if fwd < -80:
                continue

            safe = min((self._d2(teammate.pos, op.pos) for op in op_team.player_list), default=300.0)
            safe = min(safe, 260.0)

            score_zone_x = c.BLUE_SCORE_AREA[0] if atk == 1 else c.RED_SCORE_AREA[0]
            in_zone = (tx - score_zone_x) * atk
            zone = max(0.0, in_zone) * 6.0
            near_zone = max(0.0, 450.0 - abs(tx - score_zone_x)) * 0.008

            edge = min(tx, fw - tx, ty, fh - ty)
            edge_s = min(edge, 150.0)

            crowd_penalty = 0.0
            lane_penalty = 0.0
            for op in op_team.player_list:
                op_dist = self._d2(teammate.pos, op.pos)
                if op_dist < 140:
                    crowd_penalty += max(0.0, 140 - op_dist) * 0.9
                lane_dist = self._distance_point_to_segment(op.pos, me.pos, teammate.pos)
                if lane_dist < 48:
                    lane_penalty += max(0.0, 48 - lane_dist) * 2.0

            support_gap = self._d2(me.pos, teammate.pos)
            support_bonus = max(0.0, 420.0 - support_gap) * 0.05
            depth_bonus = max(0.0, (tx - mx) * atk) * 2.3
            lane_bonus = max(0.0, 3.0 - lane_penalty / 24.0) * 130.0
            frontier_bonus = 0.0
            if frontier > 0:
                frontier_bonus = max(0.0, (fwd - max(0.0, frontier - 20.0)) * 6.0) + 180.0

            score = (
                3.0 * max(fwd, 0)
                + depth_bonus
                + frontier_bonus
                + 0.35 * safe
                + 0.2 * edge_s
                + zone
                + near_zone
                + support_bonus
                + lane_bonus
                - 0.22 * d
                - crowd_penalty
                - lane_penalty
            )

            if score > best_score:
                best_score = score
                best_tgt = teammate

        return best_tgt

    def _closest_teammate(self, me, my_team):
        best, best_d = None, float("inf")
        for teammate in my_team.player_list:
            if teammate.player_key == self.player_key:
                continue
            d = self._d2(me.pos, teammate.pos)
            if 40 < d < best_d and d <= self.MAX_THROW_DISTANCE:
                best_d, best = d, teammate
        return best

    def _lane_band(self, my_team) -> int:
        support_cutoff = max(1, len(my_team.player_list) // 2)
        return 0 if self.player_key.player_id < support_cutoff else 1

    @staticmethod
    def _distance_point_to_segment(point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        ax, ay = a
        bx, by = b
        px, py = point
        abx = bx - ax
        aby = by - ay
        apx = px - ax
        apy = py - ay
        ab_len2 = abx * abx + aby * aby
        if ab_len2 < 0.01:
            return sqrt(apx * apx + apy * apy)
        t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab_len2))
        cx = ax + abx * t
        cy = ay + aby * t
        dx = px - cx
        dy = py - cy
        return sqrt(dx * dx + dy * dy)

    def _calc_throw(self, from_pos: tuple[float, float], to_pos: tuple[float, float], c):
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        dist = sqrt(dx * dx + dy * dy)
        if dist < 1:
            return None

        planned_time = max(dist / 220.0, 1.0)
        vz = max(5, round(4.9 * planned_time))
        actual_time = 2 * vz / 9.8
        vx = dx / actual_time
        vy = dy / actual_time
        min_speed = c.MIN_VELOCITY
        speed = sqrt(vx * vx + vy * vy)
        if speed < min_speed:
            scale = min_speed / max(speed, 0.01)
            vx *= scale
            vy *= scale
        return (round(vx), round(vy), vz)

    def _free_chase(self, gamestate, me, disc, catch_point, atk: int):
        c = gamestate.const
        dt = gamestate.delta_time
        dxy = catch_point

        if self._d2(me.pos, dxy) <= c.CATCH_DISTANCE and disc.pos[2] <= c.CATCH_HIGHT:
            if not self._is_safe_catcher(gamestate, me, catch_point):
                return [MoveIntent(target_pos=self._step(me.pos, self._orbit_target(gamestate, catch_point, atk), c.PLAYER_SPEED, dt))]
            if self.catch_cooldown_elapsed > 0:
                return [MoveIntent(target_pos=self._step(me.pos, self._orbit_target(gamestate, catch_point, atk), c.PLAYER_SPEED, dt))]
            self.catch_cooldown_elapsed = self.CATCH_COOLDOWN_SECONDS
            return [CatchIntent(disc_id=0)]
        return [MoveIntent(target_pos=self._step(me.pos, dxy, c.PLAYER_SPEED, dt))]

    def _free_support(self, gamestate, me, disc, my_team, atk: int, catch_point):
        c = gamestate.const
        dt = gamestate.delta_time
        fw, fh = c.GAME_SIZE

        if self._d2(me.pos, catch_point) <= c.CATCH_DISTANCE and disc.pos[2] <= c.CATCH_HIGHT:
            if self._is_safe_catcher(gamestate, me, catch_point):
                self.catch_cooldown_elapsed = self.CATCH_COOLDOWN_SECONDS
                return [CatchIntent(disc_id=0)]

        tx = catch_point[0] + atk * self.SUPPORT_GAP
        ty = self._spread_y(me, my_team, fh)
        if self._d2(me.pos, catch_point) > 600:
            tx = catch_point[0] + atk * (self.SUPPORT_GAP * 0.6)

        tx = max(10.0, min(float(fw) - 10, tx))
        ty = max(10.0, min(float(fh) - 10, ty))
        return [MoveIntent(target_pos=self._step(me.pos, (tx, ty), c.PLAYER_SPEED, dt))]

    def _off_pos(self, gamestate, me, my_team, op_team, atk: int):
        c = gamestate.const
        dt = gamestate.delta_time
        mx, my_pos = me.pos
        fw, fh = c.GAME_SIZE
        band = self._lane_band(my_team)

        hx = mx
        for teammate in my_team.player_list:
            if teammate.hold_disc:
                hx = teammate.pos[0]
                break

        tx = hx + atk * (220.0 if band == 0 else 420.0)
        ty = self._spread_y(me, my_team, fh)
        if band == 0:
            ty += 24.0 if self.player_key.player_id % 2 == 0 else -24.0
        else:
            ty += 70.0 if self.player_key.player_id % 2 == 0 else -70.0

        for op in op_team.player_list:
            if self._d2((tx, ty), op.pos) < 60:
                tx += (tx - op.pos[0]) * 0.5
                ty += (ty - op.pos[1]) * 0.5

        my_d = self._d2(me.pos, (hx, 0))
        closest = float("inf")
        for teammate in my_team.player_list:
            if teammate.player_key == self.player_key or teammate.hold_disc:
                continue
            d = self._d2(teammate.pos, (hx, 0))
            if d < closest:
                closest = d
        if band == 0 and my_d < closest * 0.8 and my_d < 150:
            tx = hx + atk * 80.0
        elif band == 1 and my_d < 220:
            tx = hx + atk * 300.0

        tx = max(10.0, min(float(fw) - 10, tx))
        ty = max(10.0, min(float(fh) - 10, ty))
        return [MoveIntent(target_pos=self._step(me.pos, (tx, ty), c.PLAYER_SPEED, dt))]

    def _def_pos(self, gamestate, me, disc, op_team, atk: int):
        c = gamestate.const
        dt = gamestate.delta_time
        mx, my_pos = me.pos
        fw, fh = c.GAME_SIZE

        holder = None
        for op in op_team.player_list:
            if op.player_key == disc.holder_key:
                holder = op
                break

        if holder is None:
            tx = mx - atk * 100.0
            ty = my_pos
            return [MoveIntent(target_pos=self._step(me.pos, (max(10, min(fw - 10, tx)), max(10, min(fh - 10, ty))), c.PLAYER_SPEED, dt))]

        my_d = self._d2(me.pos, holder.pos)
        others = any(
            self._d2(a.pos, holder.pos) < my_d
            for a in gamestate.team_list[self.player_key.team_id].player_list
            if a.player_key != self.player_key
        )

        if not others:
            dx = mx - holder.pos[0]
            dy = my_pos - holder.pos[1]
            if abs(dx) < 0.01 and abs(dy) < 0.01:
                dx = atk
                dy = 0.0
            d = max((dx * dx + dy * dy) ** 0.5, 0.01)
            tx = holder.pos[0] + dx / d * self.SAFE_MARK_RADIUS
            ty = holder.pos[1] + dy / d * self.SAFE_MARK_RADIUS
        else:
            receivers = [op for op in op_team.player_list if op.player_key != holder.player_key]
            if receivers:
                receiver = receivers[(self.player_key.player_id - 1) % len(receivers)]
                tx = receiver.pos[0] + atk * 110.0
                ty = receiver.pos[1] + (self.player_key.player_id % 2 * 2 - 1) * 55.0
            else:
                tx = holder.pos[0] + atk * 170.0
                ty = my_pos

            away_x = tx - holder.pos[0]
            away_y = ty - holder.pos[1]
            if abs(away_x) < 0.01 and abs(away_y) < 0.01:
                away_x = atk
                away_y = 0.0
            away_d = max((away_x * away_x + away_y * away_y) ** 0.5, 0.01)
            if away_d < self.SAFE_MARK_RADIUS:
                tx = holder.pos[0] + away_x / away_d * self.SAFE_MARK_RADIUS
                ty = holder.pos[1] + away_y / away_d * self.SAFE_MARK_RADIUS

        tx = max(10.0, min(float(fw) - 10, tx))
        ty = max(10.0, min(float(fh) - 10, ty))
        return [MoveIntent(target_pos=self._step(me.pos, (tx, ty), c.PLAYER_SPEED, dt))]

    def _spread_y(self, me, my_team, fh: float) -> float:
        pid = self.player_key.player_id
        n = max(len(my_team.player_list), 1)
        ty = fh / (n + 1) * (pid + 1)
        band = self._lane_band(my_team)
        nearest_d = float("inf")
        nearest_y = None
        for teammate in my_team.player_list:
            if teammate.player_key == self.player_key:
                continue
            d = abs(me.pos[1] - teammate.pos[1])
            if d < nearest_d:
                nearest_d = d
                nearest_y = teammate.pos[1]
        if nearest_y is not None and nearest_d < self.SPREAD:
            dy = me.pos[1] - nearest_y
            if abs(dy) < 1:
                dy = 30.0 if me.pos[1] < fh / 2 else -30.0
            spread = self.SPREAD if band == 0 else self.SPREAD * 1.15
            ty = me.pos[1] + (spread if dy > 0 else -spread)
        elif band == 1:
            ty += 36.0 if pid % 2 == 0 else -36.0
        return max(10.0, min(fh - 10, ty))

    def _is_closest_to_disc(self, me, disc, my_team) -> bool:
        my_dist = self._distance2d(me.pos, (disc.pos[0], disc.pos[1]))
        for teammate in my_team.player_list:
            if teammate.player_key == self.player_key:
                continue
            if self._distance2d(teammate.pos, (disc.pos[0], disc.pos[1])) + 0.5 < my_dist:
                return False
        return True

    def _is_active_chaser(self, me, gamestate, catch_point) -> bool:
        my_dist = self._distance2d(me.pos, catch_point)
        my_id = self.player_key.player_id
        my_tid = self.player_key.team_id

        better_teammates = 0
        my_team = gamestate.team_list[my_tid]
        for player in my_team.player_list:
            if player.player_key == self.player_key:
                continue
            if self._recent_thrower_ahead(player, catch_point):
                continue

            player_dist = self._distance2d(player.pos, catch_point)
            if player_dist + 0.5 < my_dist:
                better_teammates += 1
            elif abs(player_dist - my_dist) <= 0.5 and player.player_key.player_id < my_id:
                better_teammates += 1
        return better_teammates < self.ACTIVE_CHASERS_PER_TEAM

    def _is_safe_catcher(self, gamestate, me, catch_point) -> bool:
        my_dist = self._distance2d(me.pos, catch_point)
        my_tid = self.player_key.team_id
        my_id = self.player_key.player_id

        for team in gamestate.team_list:
            for player in team.player_list:
                if player.player_key == self.player_key:
                    continue
                player_dist = self._distance2d(player.pos, catch_point)
                if player_dist > self.CATCH_DANGER_RADIUS:
                    continue
                if team.team_id != my_tid and player_dist <= self.FOUL_RADIUS:
                    return False
                if team.team_id != my_tid and player_dist + 0.5 < my_dist:
                    return False
                if team.team_id != my_tid and abs(player_dist - my_dist) <= 0.5:
                    if player.player_key.team_id < my_tid:
                        return False
        return True

    def _has_crowded_catch_window(self, gamestate, catch_point) -> bool:
        for team in gamestate.team_list:
            if team.team_id == self.player_key.team_id:
                continue
            for player in team.player_list:
                if self._distance2d(player.pos, catch_point) <= self.CATCH_DANGER_RADIUS:
                    return True
        return False

    def _orbit_target(self, gamestate, catch_point, atk: int) -> tuple[float, float]:
        c = gamestate.const
        fw, fh = c.GAME_SIZE
        lanes = ((-atk, -0.7), (-atk, 0.7), (atk, -0.7), (atk, 0.7))
        ox, oy = lanes[self.player_key.player_id % len(lanes)]
        tx = catch_point[0] + ox * self.ORBIT_RADIUS
        ty = catch_point[1] + oy * self.ORBIT_RADIUS
        return (max(10.0, min(float(fw) - 10, tx)), max(10.0, min(float(fh) - 10, ty)))

    def _recent_thrower_ahead(self, teammate, catch_point) -> bool:
        direction = self._attack_direction()
        return (teammate.pos[0] - catch_point[0]) * direction < 0 and self._distance2d(teammate.pos, catch_point) < 160

    @staticmethod
    def _d2(a: tuple[float, float], b: tuple[float, float]) -> float:
        return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    @staticmethod
    def _step(from_pos: tuple[float, float], to_pos: tuple[float, float], speed: float, dt: float) -> tuple[float, float]:
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        dist = sqrt(dx * dx + dy * dy)
        mx = speed * dt * 0.8
        if dist <= mx:
            return (float(to_pos[0]), float(to_pos[1]))
        r = mx / dist
        return (from_pos[0] + dx * r, from_pos[1] + dy * r)
