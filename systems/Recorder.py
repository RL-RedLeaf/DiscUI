from __future__ import annotations
from typing import TYPE_CHECKING
from events import *
from .GameState import GameStateSnap
from entities import PlayerKey, DiscSnap, PlayerSnap, TeamSnap
from config import Constants

import json

if TYPE_CHECKING:
    from .EventBus import EventBus


class Recorder:
    def player_key_to_list(self, player_key: PlayerKey):
        if player_key is None:
            return None
        return [player_key.team_id, player_key.player_id]

    def list_to_player_key(self, player_key: list[int]):
        if player_key is None:
            return None
        return PlayerKey(player_key[0], player_key[1])

    def game_state_to_record(self, state: GameStateSnap):
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

    def record_to_game_state_snap(self, line) -> GameStateSnap:
        return GameStateSnap(
            disc = DiscSnap(pos = tuple(line["d"][0:3]),
                            holder_key = self.list_to_player_key(line["d"][7]),
                            velocity =  tuple(line["d"][3:6]),
                            state = self.decode_disc_state(line["d"][6])
            ),
            team_list = tuple(
                TeamSnap(team_id = t,
                         player_num = len(line["p"][t]),
                         player_list = tuple(
                             PlayerSnap(player_key = PlayerKey(t, p), 
                                        pos = tuple(line["p"][t][p][0:2]),
                                        hold_disc = bool(line["p"][t][p][2])
                            )
                            for p in range(len(line["p"][t]))
                         )
                )
                for t in range(len(line["p"]))
            ),
            delta_time = 0,
            const = Constants(),
            score = tuple(line["s"]),
            tick = line["t"]
        )

    def encode_disc_state(self, state):
        return {
            "waiting": "w",
            "flying": "f",
            "competing": "x",
            "catched": "c",
            "ground": "g",
        }[state]

    def decode_disc_state(self, state):
        return {
            "w": "waiting",
            "f": "flying",
            "x": "competing",
            "c": "catched",
            "g": "ground",
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

    def open_read(self, path):
        with open(path, "r", encoding="utf-8") as f:
            self.lines = f.readlines()

    def read(self, line_number):
        if line_number >= len(self.lines):
            return False
        
        elif self.lines[line_number]:  
            line = json.loads(self.lines[line_number])
            return self.record_to_game_state_snap(line)

        else:
            print(f'{line_number} 行为空')
            return None

