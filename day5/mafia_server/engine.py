"""Agentic Mafia — the game engine.

Pure game logic: tables, roles, phases, resolution. No networking in this
file — `server.py` wraps it in MCP tools and a dashboard. Keeping the rules
in one place means the rules are enforced in ONE place: agents can be
brilliant or broken, but nobody plays outside the engine.

The game (one table):

- Roles are secret: KILLERS (a team, they know each other), one or more
  HEALERS, everyone else CIVILIAN. Killers win when they equal or outnumber
  everyone else; the town wins when every killer is dead.
- Each round has two phases:
    TALK — every living player submits exactly one public message.
           Messages are revealed simultaneously when everyone has spoken.
    ACT  — everyone votes to lynch someone (plurality; tie → nobody dies).
           Killers also pick a victim (plurality among killers; tie →
           random among tied). Healers also pick someone to protect
           (self-heal allowed). The heal blocks the kill, never the vote.
- At dawn the deaths are announced WITH causes ("lynched" / "killed"), but
  a blocked kill is announced anonymously — the town learns the healer
  succeeded, not who was saved.
- An agent that neither talks nor acts for two consecutive rounds vanishes
  (counts as a death — crashed code shouldn't hold the town hostage).
"""

from __future__ import annotations

import asyncio
import itertools
import random
import secrets
import time
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

MAX_MESSAGE_CHARS = 300


class Role(str, Enum):
    KILLER = "killer"
    HEALER = "healer"
    CIVILIAN = "civilian"


class Phase(str, Enum):
    LOBBY = "lobby"
    TALK = "talk"
    ACT = "act"
    OVER = "over"


@dataclass
class TableConfig:
    size: int = 7
    killers: int = 2
    healers: int = 1
    talk_timeout: float = 75.0
    act_timeout: float = 75.0
    max_rounds: int = 15
    chat_history: str = "round"  # "round" (agents see only the current round) or "full"
    pace: str = "auto"  # "auto": phases flip on their own · "manual": the host
    #                     steps each reveal (chat, dawn) from the dashboard
    reveal_dead_roles: bool = False  # classic-Mafia "flip": dawn announces the
    #                     dead player's role. Default off — deducing alignment
    #                     is the harder, more interesting game


@dataclass
class Player:
    name: str
    token: str
    role: Role | None = None
    alive: bool = True
    death_cause: str | None = None  # "lynched" | "killed" | "vanished"
    death_round: int | None = None
    missed_rounds: int = 0  # consecutive rounds with no message AND no action
    last_seen_version: int = -1
    # per-round submissions
    messages: dict[int, str] = field(default_factory=dict)
    actions: dict[int, dict] = field(default_factory=dict)


class Table:
    def __init__(self, table_id: int, config: TableConfig):
        self.id = table_id
        self.config = config
        self.players: list[Player] = []
        self.phase = Phase.LOBBY
        self.round = 0
        self.winner: str | None = None  # "town" | "killers" | "nobody"
        self.deadline: float | None = None  # unix time the phase force-advances
        self.pace = config.pace
        # in manual pace, a finished phase parks here until the host advances:
        self.pending: str | None = None  # None | "act" | "dawn"
        # events[r] = list of public narrator lines announced at dawn of round r
        self.events: dict[int, list[str]] = {}
        # chat[r] = [(player_name, message)] in submission order, revealed in ACT
        self.chat: dict[int, list[tuple[str, str]]] = {}
        # bumped every time the public state changes; `next` long-polls on it
        self.version = 0
        self._changed = asyncio.Event()

    # ---- state change notification -------------------------------------

    def bump(self) -> None:
        self.version += 1
        self._changed.set()
        self._changed = asyncio.Event()

    async def wait_for_change(self, timeout: float) -> None:
        event = self._changed
        try:
            await asyncio.wait_for(event.wait(), timeout)
        except asyncio.TimeoutError:
            pass

    # ---- lookups --------------------------------------------------------

    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    def find_alive(self, name: str) -> Player | None:
        for p in self.alive_players():
            if p.name == name:
                return p
        return None

    @property
    def seats_left(self) -> int:
        return self.config.size - len(self.players)

    # ---- lobby ----------------------------------------------------------

    def add_player(self, name: str) -> Player:
        player = Player(name=name, token=secrets.token_hex(8))
        self.players.append(player)
        self.bump()
        return player

    def min_players(self) -> int:
        # enough that the killers don't win at dawn of round 1
        return self.config.killers + self.config.healers + 2

    def start(self, rng: random.Random | None = None) -> None:
        rng = rng or random.Random()
        if self.phase is not Phase.LOBBY:
            raise ValueError(f"table {self.id} already started")
        if len(self.players) < self.min_players():
            raise ValueError(
                f"table {self.id} needs at least {self.min_players()} players "
                f"({len(self.players)} joined)"
            )
        roles = (
            [Role.KILLER] * self.config.killers
            + [Role.HEALER] * self.config.healers
        )
        roles += [Role.CIVILIAN] * (len(self.players) - len(roles))
        rng.shuffle(roles)
        for player, role in zip(self.players, roles):
            player.role = role
        self.round = 1
        self.phase = Phase.TALK
        self.deadline = time.time() + self.config.talk_timeout
        self.events[0] = [
            f"The game begins with {len(self.players)} townsfolk. Among them: "
            f"{self.config.killers} killer(s) and {self.config.healers} healer(s).",
        ]
        self.bump()

    # ---- TALK phase ------------------------------------------------------

    def submit_message(self, player: Player, message: str) -> None:
        if self.phase is not Phase.TALK:
            raise ValueError("messages are only accepted during the TALK phase")
        if self.round in player.messages:
            raise ValueError("you already sent your message this round")
        message = message.strip()
        if len(message) > MAX_MESSAGE_CHARS:
            message = message[: MAX_MESSAGE_CHARS - 1] + "…"
        player.messages[self.round] = message
        self.chat.setdefault(self.round, []).append((player.name, message))
        if all(self.round in p.messages for p in self.alive_players()):
            self._phase_done("act")

    # ---- pacing ----------------------------------------------------------

    def _phase_done(self, transition: str) -> None:
        """A phase is complete. Auto pace: transition now. Manual pace: park
        it (agents keep long-polling; late submissions still count) until the
        host presses the dashboard button."""
        if self.pace == "manual":
            self.pending = transition
            self.deadline = None
        else:
            self._transition(transition)

    def _transition(self, transition: str) -> None:
        self.pending = None
        if transition == "act":
            self._begin_act()
        else:
            self._resolve_round()

    def advance(self) -> None:
        """Host pressed the dashboard button: run the parked transition."""
        if self.pending:
            self._transition(self.pending)

    def set_pace(self, pace: str) -> None:
        if pace not in ("auto", "manual"):
            raise ValueError("pace must be 'auto' or 'manual'")
        self.pace = pace
        if pace == "auto" and self.pending:
            self._transition(self.pending)

    def _begin_act(self) -> None:
        self.phase = Phase.ACT
        self.chat.setdefault(self.round, [])
        self.deadline = time.time() + self.config.act_timeout
        self.bump()

    # ---- ACT phase -------------------------------------------------------

    def submit_action(
        self,
        player: Player,
        vote: str,
        kill_target: str,
        heal_target: str,
        reasoning: str = "",
    ) -> None:
        if self.phase is not Phase.ACT:
            raise ValueError(
                "actions are only accepted during the ACT phase "
                "(wait for everyone's message first)"
            )
        if self.round in player.actions:
            raise ValueError("you already submitted your action this round")

        def check_target(kind: str, name: str) -> str:
            name = name.strip()
            if not name:
                return ""
            if self.find_alive(name) is None:
                living = ", ".join(p.name for p in self.alive_players())
                raise ValueError(
                    f"invalid {kind} target {name!r} — living players are: {living}"
                )
            return name

        vote = check_target("vote", vote)
        kill_target = check_target("kill", kill_target)
        heal_target = check_target("heal", heal_target)
        if vote and self.round == 1:
            raise ValueError(
                "there is no lynch vote on the first night — the town has "
                "nothing to go on yet; leave vote empty"
            )
        if kill_target and player.role is not Role.KILLER:
            raise ValueError("only killers can kill — leave kill_target empty")
        if heal_target and player.role is not Role.HEALER:
            raise ValueError("only healers can heal — leave heal_target empty")

        player.actions[self.round] = {
            "vote": vote,
            "kill": kill_target,
            "heal": heal_target,
            # private: shown only on the host's dashboard, never in any
            # player view — see view_for, which never surfaces actions
            "reasoning": reasoning.strip()[:MAX_MESSAGE_CHARS],
        }
        if all(self.round in p.actions for p in self.alive_players()):
            self._phase_done("dawn")

    # ---- deadline (called by the server's phase timer) -------------------

    def force_advance(self) -> None:
        """The phase deadline passed: move on without the stragglers."""
        if self.phase is Phase.TALK:
            self._phase_done("act")
        elif self.phase is Phase.ACT:
            self._phase_done("dawn")

    # ---- dawn ------------------------------------------------------------

    def _resolve_round(self, rng: random.Random | None = None) -> None:
        rng = rng or random.Random()
        alive = self.alive_players()
        acts = {p.name: p.actions.get(self.round) for p in alive}
        lines: list[str] = []

        # the lynch: plurality of all votes; any tie → nobody dies
        votes = Counter(a["vote"] for a in acts.values() if a and a["vote"])
        lynched = _plurality(votes, on_tie=None)

        # the kill: plurality among the killers' choices; tie → random among tied
        kills = Counter(
            a["kill"]
            for p in alive
            if p.role is Role.KILLER and (a := acts.get(p.name)) and a["kill"]
        )
        kill_target = _plurality(kills, on_tie=rng.choice)

        heals = {
            a["heal"]
            for p in alive
            if p.role is Role.HEALER and (a := acts.get(p.name)) and a["heal"]
        }

        deaths: list[tuple[str, str]] = []
        if lynched:
            deaths.append((lynched, "lynched"))
        saved = False
        if kill_target and kill_target != lynched:
            if kill_target in heals:
                saved = True
            else:
                deaths.append((kill_target, "killed"))

        # inactivity: no message AND no action this round
        for p in alive:
            if self.round in p.messages or self.round in p.actions:
                p.missed_rounds = 0
            else:
                p.missed_rounds += 1
                if p.missed_rounds >= 2 and p.name not in (d[0] for d in deaths):
                    deaths.append((p.name, "vanished"))

        for name, cause in deaths:
            player = self.find_alive(name)
            if player is None:
                continue
            player.alive = False
            player.death_cause = cause
            player.death_round = self.round
            flip = (
                f" — they were a {player.role.value}"
                if self.config.reveal_dead_roles
                else ""
            )
            if cause == "lynched":
                lines.append(f"{name} was lynched by the town's vote{flip}.")
            elif cause == "killed":
                lines.append(f"{name} was killed in the night{flip}.")
            else:
                lines.append(
                    f"{name} vanished without a trace{flip}. (Agent inactive.)"
                )
        if saved:
            lines.append(
                "The killers struck, but the healer got there first — "
                "the attack failed."
            )
        if not lines:
            lines.append("Dawn breaks. Miraculously, nobody died.")

        self.events[self.round] = lines
        self._check_game_over(lines)
        if self.phase is not Phase.OVER:
            self.round += 1
            self.phase = Phase.TALK
            self.deadline = time.time() + self.config.talk_timeout
        self.bump()

    def _check_game_over(self, lines: list[str]) -> None:
        alive = self.alive_players()
        killers = sum(1 for p in alive if p.role is Role.KILLER)
        others = len(alive) - killers
        if killers == 0:
            self.winner = "town"
            lines.append("Every killer is dead. THE TOWN WINS! 🎉")
        elif killers >= others:
            self.winner = "killers"
            lines.append("The killers now rule the town. THE KILLERS WIN! 🔪")
        elif self.round >= self.config.max_rounds:
            self.winner = "nobody"
            lines.append(
                f"{self.config.max_rounds} rounds and no resolution — the town "
                "collapses from paranoia. NOBODY WINS."
            )
        if self.winner:
            self.phase = Phase.OVER
            self.deadline = None
            reveal = ", ".join(
                f"{p.name} was a {p.role.value}" for p in self.players
            )
            lines.append(f"The roles are revealed: {reveal}.")

    # ---- player views (what `next` returns) ------------------------------

    def view_for(self, player: Player, waiting: bool = False) -> dict:
        view: dict = {
            "table": self.id,
            "status": "waiting" if waiting else self._status_of(player),
            "phase": self.phase.value,
            "round": self.round,
            "rules": {
                "players": len(self.players),
                "killers": self.config.killers,
                "healers": self.config.healers,
            },
            "you": {"name": player.name, "alive": player.alive},
            "players_alive": [p.name for p in self.alive_players()],
        }
        if player.role is not None:
            view["you"]["role"] = player.role.value
            if player.role is Role.KILLER:
                view["you"]["your_fellow_killers"] = [
                    p.name
                    for p in self.players
                    if p.role is Role.KILLER and p.name != player.name
                ]
        if not player.alive:
            view["you"]["died"] = f"{player.death_cause} in round {player.death_round}"

        if self.phase is not Phase.LOBBY:
            last_round = self.round if self.phase is Phase.OVER else self.round - 1
            view["news"] = list(
                itertools.chain.from_iterable(
                    self.events.get(r, []) for r in self._news_rounds(last_round)
                )
            )
            view["chat"] = self._chat_view()
        if self.phase is Phase.OVER:
            view["winner"] = self.winner
            view["roles_revealed"] = {p.name: p.role.value for p in self.players}
        view["to_do"] = self._to_do(player)
        return view

    def _news_rounds(self, last_round: int) -> list[int]:
        if self.config.chat_history == "full":
            return list(range(0, last_round + 1))
        return [last_round]  # round 1 → last_round 0 → the game-start line

    def _chat_view(self) -> list[dict]:
        # Current round's chat is public only once everyone has spoken (ACT
        # phase). Default mode "round": that's ALL agents ever see — remembering
        # previous rounds is the agents' job. Mode "full": entire history.
        rounds: list[int] = []
        if self.config.chat_history == "full":
            rounds = [r for r in self.chat if r < self.round]
        if self.phase in (Phase.ACT, Phase.OVER):
            rounds.append(self.round)
        return [
            {"round": r, "from": name, "message": msg}
            for r in sorted(set(rounds))
            for name, msg in self.chat.get(r, [])
        ]

    def _status_of(self, player: Player) -> str:
        if self.phase is Phase.LOBBY:
            return "lobby"
        if self.phase is Phase.OVER:
            return "game_over"
        return "playing" if player.alive else "dead"

    def _to_do(self, player: Player) -> str:
        if self.phase is Phase.LOBBY:
            return (
                f"Waiting for the game to start ({len(self.players)}"
                f"/{self.config.size} seats taken). Call next again."
            )
        if self.phase is Phase.OVER:
            return "The game is over. Thanks for playing!"
        if not player.alive:
            return (
                "You are dead. You may keep calling next to watch the town, "
                "but you can no longer speak or act."
            )
        if self.phase is Phase.TALK:
            if self.round in player.messages:
                return (
                    "Message received. Call next to wait for the town chat "
                    "(everyone's messages are revealed together)."
                )
            return (
                "TALK phase: submit exactly ONE public message with "
                "send_message. Everyone will read it. Then call next."
            )
        # ACT
        if self.round in player.actions:
            return "Action received. Call next to wait for dawn."
        if self.round == 1:
            base = (
                "ACT phase, first night: there is NO lynch vote yet — call "
                "submit_action with vote empty to pass the night."
            )
        else:
            base = (
                "ACT phase: read the chat above, then call submit_action with "
                "your vote — the player you want lynched (plurality wins, tie "
                "→ nobody; empty string abstains)."
            )
        if player.role is Role.KILLER:
            base += " As a KILLER, also set kill_target — your team's victim."
        elif player.role is Role.HEALER:
            base += (
                " As the HEALER, also set heal_target — who to protect tonight "
                "(yourself is allowed)."
            )
        return base


def _plurality(counts: Counter, on_tie) -> str | None:
    """Most-voted name; ties resolved by on_tie (a callable over the tied
    names, or None meaning 'nobody')."""
    if not counts:
        return None
    top = max(counts.values())
    tied = sorted(name for name, n in counts.items() if n == top)
    if len(tied) == 1:
        return tied[0]
    return on_tie(tied) if callable(on_tie) else on_tie


class Game:
    """All tables + name/token registries. One instance per server."""

    def __init__(self, n_tables: int, config: TableConfig):
        self.config = config
        self.tables = [Table(i + 1, config) for i in range(n_tables)]
        self.by_token: dict[str, tuple[Table, Player]] = {}
        self.names: set[str] = set()
        self.stale_tokens: set[str] = set()  # tokens orphaned by a table reset

    def join(self, name: str) -> tuple[Table, Player]:
        name = name.strip()
        if not name or len(name) > 30:
            raise ValueError("pick a player_name between 1 and 30 characters")
        if name.lower() in self.names:
            raise ValueError(
                f"the name {name!r} is taken — pick a unique one (add a suffix?)"
            )
        for table in self.tables:
            if table.phase is Phase.LOBBY and table.seats_left > 0:
                player = table.add_player(name)
                self.names.add(name.lower())
                self.by_token[player.token] = (table, player)
                return table, player
        raise ValueError(
            "all tables are full or already playing — ask the instructor "
            "to open another table"
        )

    def reset_table(self, table_id: int) -> None:
        """Fresh table in place: seats and names free up, old tokens go
        stale (with a rejoin hint), parked long-polls wake up."""
        idx = next(
            (i for i, t in enumerate(self.tables) if t.id == table_id), None
        )
        if idx is None:
            raise ValueError(f"no table {table_id}")
        old = self.tables[idx]
        for player in old.players:
            self.names.discard(player.name.lower())
            self.by_token.pop(player.token, None)
            self.stale_tokens.add(player.token)
        self.tables[idx] = Table(old.id, self.config)
        old.bump()  # wake anyone still long-polling on the dead table

    def resolve_token(self, token: str) -> tuple[Table, Player]:
        token = token.strip()
        entry = self.by_token.get(token)
        if entry is None:
            if token in self.stale_tokens:
                raise ValueError(
                    "this game was reset by the host — your token is no "
                    "longer valid. Call join_game again with your "
                    "player_name to sit at a fresh table"
                )
            raise ValueError(
                "unknown token — pass the exact token join_game gave you"
            )
        return entry
