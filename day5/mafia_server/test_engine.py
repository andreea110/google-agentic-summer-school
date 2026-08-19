"""Plain-assert tests for the game engine (no pytest needed).

Run from day5/:  python -m mafia_server.test_engine
"""

import asyncio
import random

from .engine import Game, Phase, Role, Table, TableConfig


def make_table(size=5, killers=1, healers=1, **kw) -> Table:
    table = Table(1, TableConfig(size=size, killers=killers, healers=healers, **kw))
    for i in range(size):
        table.add_player(f"p{i}")
    table.start(rng=random.Random(42))
    return table


def by_role(table, role):
    return [p for p in table.alive_players() if p.role is role]


def talk(table, skip=()):
    for p in table.alive_players():
        if p.name not in skip:
            table.submit_message(p, f"hello from {p.name}")


def pass_night(table):
    """Play round 1 uneventfully (no votes allowed, no kills submitted)."""
    talk(table)
    for p in table.alive_players():
        table.submit_action(p, vote="", kill_target="", heal_target="")
    assert table.round == 2, "first night should end with nobody dead"


def test_full_round_and_kill():
    table = make_table()
    assert table.phase is Phase.TALK and table.round == 1
    talk(table)
    assert table.phase is Phase.ACT, "all messages in -> ACT"
    killer = by_role(table, Role.KILLER)[0]
    victim = next(p for p in table.alive_players() if p.role is Role.CIVILIAN)
    for p in table.alive_players():
        kill = victim.name if p is killer else ""
        table.submit_action(p, vote="", kill_target=kill, heal_target="")
    assert not victim.alive and victim.death_cause == "killed"
    assert table.round == 2 and table.phase is Phase.TALK
    assert any("killed in the night" in line for line in table.events[1])


def test_heal_blocks_kill():
    table = make_table()
    talk(table)
    killer = by_role(table, Role.KILLER)[0]
    healer = by_role(table, Role.HEALER)[0]
    victim = next(p for p in table.alive_players() if p.role is Role.CIVILIAN)
    for p in table.alive_players():
        table.submit_action(
            p,
            vote="",
            kill_target=victim.name if p is killer else "",
            heal_target=victim.name if p is healer else "",
        )
    assert victim.alive, "healed victim survives"
    assert any("healer got there first" in line for line in table.events[1])


def test_no_first_night_lynch():
    table = make_table()
    talk(table)
    voter = table.alive_players()[0]
    target = table.alive_players()[1]
    try:
        table.submit_action(voter, vote=target.name, kill_target="", heal_target="")
        raise AssertionError("first-night vote accepted")
    except ValueError:
        pass
    assert 1 not in voter.actions, "rejected action must not be recorded"


def test_lynch_plurality_and_tie():
    table = make_table()
    pass_night(table)
    talk(table)
    alive = table.alive_players()
    target = alive[0]
    for p in alive:  # everyone votes target except target (votes elsewhere)
        table.submit_action(p, vote=target.name if p is not target else alive[1].name,
                            kill_target="", heal_target="")
    assert not target.alive and target.death_cause == "lynched"

    # tie -> nobody dies
    table3 = make_table(size=6, killers=1, healers=1)
    pass_night(table3)
    talk(table3)
    alive3 = table3.alive_players()
    for i, p in enumerate(alive3):  # 3 vs 3 -> tie -> nobody lynched
        table3.submit_action(p, vote=alive3[0].name if i % 2 else alive3[1].name,
                             kill_target="", heal_target="")
    assert all(p.alive for p in table3.players), "tie means nobody dies"
    assert any("nobody died" in line for line in table3.events[2])


def test_rules_enforced():
    table = make_table()
    civilian = next(p for p in table.alive_players() if p.role is Role.CIVILIAN)
    # can't act during TALK
    try:
        table.submit_action(civilian, vote="", kill_target="", heal_target="")
        raise AssertionError("acted during TALK")
    except ValueError:
        pass
    table.submit_message(civilian, "hi")
    # one message per round
    try:
        table.submit_message(civilian, "hi again")
        raise AssertionError("double message accepted")
    except ValueError:
        pass
    talk(table, skip=[civilian.name])
    # civilians can't kill
    victim = table.alive_players()[0]
    try:
        table.submit_action(civilian, vote="", kill_target=victim.name, heal_target="")
        raise AssertionError("civilian killed someone")
    except ValueError:
        pass
    # dead / unknown targets rejected
    try:
        table.submit_action(civilian, vote="ghost", kill_target="", heal_target="")
        raise AssertionError("vote for unknown player accepted")
    except ValueError:
        pass
    # long messages truncated
    chatty = make_table()
    speaker = chatty.alive_players()[0]
    chatty.submit_message(speaker, "x" * 1000)
    assert len(speaker.messages[1]) <= 300


def test_timeout_and_vanish():
    table = make_table()
    lazy = next(p for p in table.alive_players() if p.role is Role.CIVILIAN)
    for _ in range(2):  # two full rounds of total silence from lazy
        talk(table, skip=[lazy.name])
        table.force_advance()  # TALK deadline passes
        assert table.phase is Phase.ACT
        for p in table.alive_players():
            if p is not lazy:
                table.submit_action(p, vote="", kill_target="", heal_target="")
        table.force_advance()  # ACT deadline passes
    assert not lazy.alive and lazy.death_cause == "vanished"


def test_win_conditions():
    # town win: lynch the only killer (from round 2 — no first-night lynch)
    table = make_table()
    pass_night(table)
    talk(table)
    killer = by_role(table, Role.KILLER)[0]
    for p in table.alive_players():
        table.submit_action(p, vote=killer.name, kill_target="", heal_target="")
    assert table.winner == "town" and table.phase is Phase.OVER
    assert any("roles are revealed" in line for line in table.events[2])

    # killer win by attrition: killer kills a civilian each night, no lynch
    table = make_table(size=5, killers=2, healers=0)
    while table.winner is None:
        talk(table)
        killers = by_role(table, Role.KILLER)
        victim = next(p for p in table.alive_players() if p.role is not Role.KILLER)
        for p in table.alive_players():
            table.submit_action(
                p, vote="", kill_target=victim.name if p in killers else "",
                heal_target="")
    assert table.winner == "killers"

    # stalemate -> nobody
    table = make_table(max_rounds=3)
    while table.winner is None:
        talk(table)
        for p in table.alive_players():
            table.submit_action(p, vote="", kill_target="", heal_target="")
    assert table.winner == "nobody"


def test_views_and_secrecy():
    table = make_table(size=6, killers=2, healers=1)
    killers = by_role(table, Role.KILLER)
    civ = next(p for p in table.alive_players() if p.role is Role.CIVILIAN)
    kview = table.view_for(killers[0])
    assert kview["you"]["role"] == "killer"
    assert kview["you"]["your_fellow_killers"] == [killers[1].name]
    cview = table.view_for(civ)
    assert "your_fellow_killers" not in cview["you"]
    # chat hidden during TALK, visible in ACT
    table.submit_message(civ, "secret-ish")
    assert table.view_for(killers[0]).get("chat", []) == []
    talk(table, skip=[civ.name])
    assert table.phase is Phase.ACT
    chat = table.view_for(killers[0])["chat"]
    assert len(chat) == 6 and {c["from"] for c in chat} == {
        p.name for p in table.alive_players()}
    # default 'round' history: round-1 chat is gone by round 2
    for p in table.alive_players():
        table.submit_action(p, vote="", kill_target="", heal_target="")
    assert table.round == 2
    talk(table)
    chat2 = table.view_for(killers[0])["chat"]
    assert all(c["round"] == 2 for c in chat2), "old chat must be forgotten"


def test_reveal_dead_roles():
    # default: dawn lines never mention a role
    table = make_table()
    talk(table)
    killer = by_role(table, Role.KILLER)[0]
    victim = next(p for p in table.alive_players() if p.role is Role.CIVILIAN)
    for p in table.alive_players():
        table.submit_action(p, vote="",
                            kill_target=victim.name if p is killer else "",
                            heal_target="")
    assert not any("they were a" in line for line in table.events[1])

    # flip mode: the role is announced with the death
    table = make_table(reveal_dead_roles=True)
    talk(table)
    killer = by_role(table, Role.KILLER)[0]
    victim = next(p for p in table.alive_players() if p.role is Role.CIVILIAN)
    for p in table.alive_players():
        table.submit_action(p, vote="",
                            kill_target=victim.name if p is killer else "",
                            heal_target="")
    assert any(
        f"{victim.name} was killed in the night — they were a civilian" in line
        for line in table.events[1]
    )


def test_manual_pacing():
    table = make_table(pace="manual")
    talk(table)
    assert table.phase is Phase.TALK and table.pending == "act", \
        "manual pace parks the chat reveal for the host"
    table.advance()
    assert table.phase is Phase.ACT and table.pending is None
    for p in table.alive_players():
        table.submit_action(p, vote="", kill_target="", heal_target="")
    assert table.phase is Phase.ACT and table.pending == "dawn"
    table.set_pace("auto")  # flipping to auto releases the parked dawn
    assert table.round == 2 and table.phase is Phase.TALK and table.pending is None
    # ...and stays auto from here on
    talk(table)
    assert table.phase is Phase.ACT and table.pending is None


def test_reasoning_is_private():
    import json

    table = make_table()
    talk(table)
    secret = "I am secretly the killer and I choose my victim by wit"
    for p in table.alive_players():
        table.submit_action(p, vote="", kill_target="", heal_target="",
                            reasoning=secret)
        assert table.round not in p.actions or True  # stored below
    # stored server-side…
    assert all(p.actions[1]["reasoning"] == secret for p in table.players)
    # …but absent from every player view, playing or waiting
    for p in table.players:
        for waiting in (False, True):
            view = json.dumps(table.view_for(p, waiting=waiting))
            assert "reasoning" not in view and secret not in view


def test_reset_table():
    game = Game(1, TableConfig(size=4, killers=1, healers=0))
    tokens = [game.join(f"s{i}")[1].token for i in range(4)]
    game.tables[0].start()
    game.reset_table(1)
    fresh = game.tables[0]
    assert fresh.phase is Phase.LOBBY and not fresh.players
    # old tokens get the rejoin hint, not a generic error
    try:
        game.resolve_token(tokens[0])
        raise AssertionError("stale token accepted")
    except ValueError as exc:
        assert "reset" in str(exc) and "join_game" in str(exc)
    # names are free again, rejoining works
    table, player = game.join("s0")
    assert table is fresh and player.name == "s0"
    try:
        game.reset_table(99)
        raise AssertionError("reset of unknown table accepted")
    except ValueError:
        pass


def test_game_registry():
    game = Game(2, TableConfig(size=4, killers=1, healers=0))
    tokens = [game.join(f"s{i}")[1].token for i in range(6)]
    assert len({t for t in tokens}) == 6
    assert [len(t.players) for t in game.tables] == [4, 2]
    try:
        game.join("s0")
        raise AssertionError("duplicate name accepted")
    except ValueError:
        pass
    table, player = game.resolve_token(tokens[0])
    assert table.id == 1 and player.name == "s0"
    try:
        game.resolve_token("bogus")
        raise AssertionError("bogus token accepted")
    except ValueError:
        pass


def main() -> None:
    async def run() -> None:  # tables create asyncio.Events -> need a loop
        tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
        for test in tests:
            test()
            print(f"  ✓ {test.__name__}")
        print(f"{len(tests)} engine tests passed.")

    asyncio.run(run())


if __name__ == "__main__":
    main()
