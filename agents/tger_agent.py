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

import math
from typing import TYPE_CHECKING

from entities import PlayerKey
from systems import AgentBase, CatchIntent, MoveIntent, ThrowIntent, Intent

if TYPE_CHECKING:
    from systems import GameStateSnap


class TgerAgent(AgentBase):

    player_key: PlayerKey

    THROW_SPEED: float = 380.0
    MIN_THROW_TIME: float = 0.8
    SPREAD: float = 80.0
    DEFEND_GAP: float = 50.0

    def init(self, player_key: PlayerKey) -> None:
        self.player_key = player_key

    # ── 主入口 ──────────────────────────────────────────────

    def agent(self, gamestate: GameStateSnap) -> list[Intent]:
        me = self._me(gamestate)
        disc = gamestate.disc
        c = gamestate.const
        dt = gamestate.delta_time

        my_tid = self.player_key.team_id
        op_tid = 1 - my_tid
        my_team = gamestate.team_list[my_tid]
        op_team = gamestate.team_list[op_tid]

        atk = 1 if my_tid == c.BLUE_TEAM_ID else -1

        # 1. 持盘 → 传盘
        if me.hold_disc and disc.holder_key == self.player_key:
            return self._throw(gamestate, me, my_team, op_team, atk)

        # 2. 自由盘
        if disc.state in ("flying", "competing", "waiting") and disc.holder_key is None:
            return self._free_disc(gamestate, me, disc, my_team, atk)

        # 3. 队友持盘 → 进攻跑位
        if disc.holder_key is not None and disc.holder_key.team_id == my_tid:
            tgt = self._off_pos(gamestate, me, my_team, op_team, atk)
            return [MoveIntent(target_pos=tgt)]

        # 4. 对手持盘 → 防守
        if disc.holder_key is not None and disc.holder_key.team_id == op_tid:
            tgt = self._def_pos(gamestate, me, disc, op_team, atk)
            return [MoveIntent(target_pos=tgt)]

        return []

    # ── 传盘 ──────────────────────────────────────────────────

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
        return [ThrowIntent(disc_id=0, motion=motion)]

    def _best_receiver(self, c, me, my_team, op_team, atk: int):
        best_score = -1e9
        best_tgt = None
        fw, fh = c.GAME_SIZE
        mx, my_pos = me.pos

        for t in my_team.player_list:
            if t.player_key == self.player_key:
                continue
            tx, ty = t.pos
            d = self._d2(me.pos, t.pos)
            if d < 40 or d > 1000:
                continue

            fwd = (tx - mx) * atk
            if fwd < -80:
                continue

            safe = min((self._d2(t.pos, op.pos) for op in op_team.player_list), default=300)
            safe = min(safe, 200.0)

            score_zone_x = c.BLUE_SCORE_AREA[0] if atk == 1 else c.RED_SCORE_AREA[0]
            # 得分区巨大加分 — 鼓励传向得分区内的队友
            in_zone = (tx - score_zone_x) * atk
            zone = max(0, in_zone) * 5.0
            near_zone = max(0, 500 - abs(tx - score_zone_x)) * 0.01

            edge = min(tx, fw - tx, ty, fh - ty)
            edge_s = min(edge, 150.0)

            # 前方权重从 1.0 → 1.8, 更偏好深远传盘
            score = 1.8 * max(fwd, 0) + 0.5 * safe + 0.2 * edge_s + zone + near_zone - 0.12 * d

            if score > best_score:
                best_score = score
                best_tgt = t

        return best_tgt

    def _calc_throw(self, from_pos: tuple, to_pos: tuple, c):
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        dist = math.hypot(dx, dy)
        if dist < 1:
            return None

        t = max(dist / self.THROW_SPEED, self.MIN_THROW_TIME)
        vz_raw = (4.9 * t * t - 2.0) / t
        vz = max(vz_raw, 4.0)
        vz_i = math.ceil(vz)

        disc_val = vz_i * vz_i + 4 * 4.9 * 2.0
        t_act = (vz_i + math.sqrt(max(disc_val, 0))) / (2 * 4.9)

        return (round(dx / t_act), round(dy / t_act), vz_i)

    def _closest_teammate(self, me, my_team):
        best, best_d = None, float("inf")
        for t in my_team.player_list:
            if t.player_key == self.player_key:
                continue
            d = self._d2(me.pos, t.pos)
            if 40 < d < best_d:
                best_d, best = d, t
        return best

    # ── 自由盘 ────────────────────────────────────────────────

    def _free_disc(self, gamestate, me, disc, my_team, atk: int) -> list[Intent]:
        c = gamestate.const
        dt = gamestate.delta_time
        dxy = (disc.pos[0], disc.pos[1])
        dist = self._d2(me.pos, dxy)

        # flying → 全队追盘
        # waiting/competing → P0/P1 追盘, P2/P3 前插
        chase = disc.state == "flying" or self.player_key.player_id < 2

        if chase:
            intents = [MoveIntent(target_pos=self._step(me.pos, dxy, c.PLAYER_SPEED, dt))]
            if dist <= c.CATCH_DISTANCE and disc.pos[2] <= c.CATCH_HIGHT:
                intents.append(CatchIntent(disc_id=0))
            return intents
        else:
            fw, fh = c.GAME_SIZE
            tx = disc.pos[0] + atk * 600.0
            ty = self._spread_y(me, my_team, fh)
            if dist > 600:
                tx = disc.pos[0] + atk * 150.0
            tx = max(10.0, min(float(fw) - 10, tx))
            ty = max(10.0, min(float(fh) - 10, ty))
            return [MoveIntent(target_pos=self._step(me.pos, (tx, ty), c.PLAYER_SPEED, dt))]

    # ── 跑位 ──────────────────────────────────────────────────

    def _off_pos(self, gamestate, me, my_team, op_team, atk: int):
        c = gamestate.const
        dt = gamestate.delta_time
        mx, my_pos = me.pos
        fw, fh = c.GAME_SIZE

        hx = mx
        for a in my_team.player_list:
            if a.hold_disc:
                hx = a.pos[0]
                break

        tx = hx + atk * 350.0
        ty = self._spread_y(me, my_team, fh)

        for op in op_team.player_list:
            if self._d2((tx, ty), op.pos) < 60:
                tx += (tx - op.pos[0]) * 0.5
                ty += (ty - op.pos[1]) * 0.5

        # 安全阀: 最近的队友略微后退接应
        my_d = self._d2(me.pos, (hx, 0))
        closest = float("inf")
        for a in my_team.player_list:
            if a.player_key == self.player_key or a.hold_disc:
                continue
            d = self._d2(a.pos, (hx, 0))
            if d < closest:
                closest = d
        if my_d < closest * 0.8 and my_d < 150:
            tx = hx + atk * 80.0

        tx = max(10.0, min(float(fw) - 10, tx))
        ty = max(10.0, min(float(fh) - 10, ty))
        return self._step(me.pos, (tx, ty), c.PLAYER_SPEED, dt)

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
            return self._step(me.pos,
                (max(10, min(fw - 10, tx)), max(10, min(fh - 10, ty))),
                c.PLAYER_SPEED, dt)

        my_d = self._d2(me.pos, holder.pos)
        others = any(
            self._d2(a.pos, holder.pos) < my_d
            for a in gamestate.team_list[self.player_key.team_id].player_list
            if a.player_key != self.player_key
        )

        if not others:
            dx = mx - holder.pos[0]
            dy = my_pos - holder.pos[1]
            d = max(my_d, 0.01)
            tx = holder.pos[0] + (dx / d) * self.DEFEND_GAP
            ty = holder.pos[1] + (dy / d) * self.DEFEND_GAP
        else:
            tx = holder.pos[0] - atk * 150.0
            ty = my_pos

        tx = max(10.0, min(float(fw) - 10, tx))
        ty = max(10.0, min(float(fh) - 10, ty))
        return self._step(me.pos, (tx, ty), c.PLAYER_SPEED, dt)

    # ── 工具 ──────────────────────────────────────────────────

    def _me(self, gs):
        return gs.team_list[self.player_key.team_id].player_list[self.player_key.player_id]

    def _spread_y(self, me, my_team, fh: float) -> float:
        pid = self.player_key.player_id
        n = max(len(my_team.player_list), 1)
        ty = fh / (n + 1) * (pid + 1)
        nearest_d = float("inf")
        nearest_y = None
        for a in my_team.player_list:
            if a.player_key == self.player_key:
                continue
            d = abs(me.pos[1] - a.pos[1])
            if d < nearest_d:
                nearest_d = d
                nearest_y = a.pos[1]
        if nearest_y is not None and nearest_d < self.SPREAD:
            dy = me.pos[1] - nearest_y
            if abs(dy) < 1:
                dy = 30.0 if me.pos[1] < fh / 2 else -30.0
            ty = me.pos[1] + math.copysign(self.SPREAD, dy)
        return max(10.0, min(fh - 10, ty))

    @staticmethod
    def _d2(a: tuple, b: tuple) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    @staticmethod
    def _step(from_pos: tuple, to_pos: tuple, speed: float, dt: float) -> tuple[int, int]:
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        dist = math.hypot(dx, dy)
        mx = speed * dt
        if dist <= mx:
            return (int(to_pos[0]), int(to_pos[1]))
        r = mx / dist
        return (int(from_pos[0] + dx * r), int(from_pos[1] + dy * r))
