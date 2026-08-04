from __future__ import annotations
from typing import TYPE_CHECKING
from events import *

import json

if TYPE_CHECKING:
    from entities import PlayerKey
    from .GameState import GameStateSnap
    from .EventBus import EventBus


class Recorder:
    def player_key_to_list(self, player_key: PlayerKey):
        if player_key is None:
            return None
        return [player_key.team_id, player_key.player_id]


    def game_state_to_record(self, state):
        return {
            "t": state.tick,
            "s": list(state.score),
            "d": [
                *state.disc.pos,
                *state.disc.velocity,
                self.encode_disc_state(state.disc.state),
                self.player_key_to_list(state.disc.holder_key),
            ],
            "p": [
                [
                    [player.pos[0], player.pos[1], int(player.hold_disc)]
                    for player in team.player_list
                ]
                for team in state.team_list
            ],
        }

    def encode_disc_state(self, state):
        return {
            "waiting": "w",
            "flying": "f",
            "competing": "x",
            "catched": "c",
            "ground": "g",
        }[state]

    def on_game_start(self, event: GameStartEvent):
        try:
            self.record(event.game_state)
        except Exception as e:
            pass
    def on_game_play(self, event: GamePlayEvent):
        try:
            self.record(event.game_state)
        except Exception as e:
            pass

    def on_game_reset(self, event: ResetEvent):
        try:
            self.record(event.gamestate)
            self.file.flush()
        except Exception as e:
            pass

    def setup(self, path, event_bus: EventBus):
        self.file = open(path, "w", encoding="utf-8")
        self.event_bus = event_bus
        print(f"Recorder: record file ready <{path}>")

        self.event_bus.subscribe(GameStartEvent, self.on_game_start)
        self.event_bus.subscribe(GamePlayEvent, self.on_game_play)
        self.event_bus.subscribe(ResetEvent, self.on_game_reset)

    def record(self, game_state: GameStateSnap):
        if self.file is None:
            return

        data = self.game_state_to_record(game_state)
        json.dump(data, self.file, ensure_ascii=False, separators=(",", ":"))
        self.file.write("\n")

    def close(self):
        if self.file is not None:
            self.file.close()
            self.file = None