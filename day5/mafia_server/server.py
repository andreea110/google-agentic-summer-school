"""Agentic Mafia — the MCP game server.

One process serves everything:

- the MCP endpoint (streamable HTTP) at  /mcp   — where agents connect
- the instructor dashboard at            /dashboard?key=…  — for the projector
- its JSON feed at                       /api/state

The four tools (join_game, next, send_message, submit_action) are the ONLY
way agents touch the game, and every rule is enforced server-side. Errors
come back as {"error": ...} dicts — the Day-3 lesson: structured errors let
an agent recover; exceptions just kill the run.

`next` is a LONG-POLL: if nothing new has happened it holds the request for
up to ~20s waiting for the state to change, so agents don't burn an LLM turn
per "still waiting". Design note for students: the model never polls — the
tool does.

Run (instructor machine):

    cd day5
    python -m mafia_server --tables 2 --table-size 7 --killers 2 --healers 1

Then give students the printed MCP URL and put the dashboard on the projector.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import secrets
import socket
import time
from pathlib import Path

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route

from .engine import Game, Phase, Role, TableConfig

LONGPOLL_SECONDS = 20.0
DASHBOARD_HTML = Path(__file__).with_name("dashboard.html")

game: Game  # set in main()
admin_key: str = ""

mcp = FastMCP(
    "agentic-mafia",
    instructions=(
        "The game server for 'Agentic Mafia' — a social deduction game "
        "played by AI agents. Join once with join_game, then loop: "
        "next → send_message → next → submit_action → next … "
        "and always follow the to_do field of the latest game state."
    ),
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
async def join_game(player_name: str) -> dict:
    """Join a table. Call this ONCE, first, with a unique player name.

    Returns your secret token — every other tool needs it. Keep it safe and
    never mention it in chat messages.
    """
    try:
        table, player = game.join(player_name)
    except ValueError as exc:
        return {"error": str(exc)}
    return {
        "token": player.token,
        "table": table.id,
        "seats_left": table.seats_left,
        "message": (
            f"Welcome to table {table.id}, {player.name}. The instructor "
            "starts the game; call next (in a loop) to wait for your role."
        ),
    }


@mcp.tool(name="next")
async def next_state(token: str) -> dict:
    """Get the current game state, waiting until something new happens.

    Long-polls: blocks up to ~20s for the game to advance, so call it in a
    loop until its to_do tells you to do something else. The state includes
    your role, who is alive, the news since your last call, the town chat
    (once everyone has spoken), and a to_do field saying what to do now.
    """
    try:
        table, player = game.resolve_token(token)
    except ValueError as exc:
        return {"error": str(exc)}
    if player.last_seen_version >= table.version:
        await table.wait_for_change(LONGPOLL_SECONDS)
    if player.last_seen_version >= table.version:
        return table.view_for(player, waiting=True)
    player.last_seen_version = table.version
    return table.view_for(player)


@mcp.tool()
async def send_message(token: str, message: str) -> dict:
    """Say one thing to the whole table (TALK phase only, once per round).

    Everyone's messages are revealed simultaneously when the phase ends —
    nobody can read yours early, and you can't read theirs. Max 300 chars
    (longer messages are truncated).
    """
    try:
        table, player = game.resolve_token(token)
        if not player.alive:
            return {"error": "the dead don't talk — you can only call next"}
        table.submit_message(player, message)
    except ValueError as exc:
        return {"error": str(exc)}
    return {"ok": True, "message": "Message registered. Call next."}


@mcp.tool()
async def submit_action(
    token: str,
    vote: str = "",
    kill_target: str = "",
    heal_target: str = "",
    reasoning: str = "",
) -> dict:
    """Submit your secret action for this round (ACT phase only, once).

    vote: the player you want lynched — plurality wins, any tie means nobody
    dies, empty string abstains. Killers may also set kill_target (the team's
    plurality picks the victim). Healers may also set heal_target (self-heal
    allowed; a heal blocks the killers, never the vote). Civilians: vote only.

    reasoning (optional): one short sentence on WHY you chose this action.
    It is completely private — shown only on the human host's dashboard,
    never to any player, and it has no effect on the game.
    """
    try:
        table, player = game.resolve_token(token)
        if not player.alive:
            return {"error": "the dead don't act — you can only call next"}
        table.submit_action(player, vote, kill_target, heal_target, reasoning)
    except ValueError as exc:
        return {"error": str(exc)}
    return {"ok": True, "message": "Action registered. Call next to await dawn."}


# ---- dashboard -----------------------------------------------------------


def _player_state(table, p, reveal: bool) -> dict:
    show_role = reveal or not p.alive or table.phase is Phase.OVER
    state = {
        "name": p.name,
        "alive": p.alive,
        "death_cause": p.death_cause,
        "death_round": p.death_round,
        "role": p.role.value if (p.role and show_role) else None,
        "spoke": table.round in p.messages,
        "acted": table.round in p.actions,
        # hover tooltip: full message history (public once revealed; the
        # current round is included only for the key-holder)
        "messages": [
            {"round": r, "message": m}
            for r, m in sorted(p.messages.items())
            if r < table.round or table.phase in (Phase.ACT, Phase.OVER) or reveal
        ],
        "actions": (
            [{"round": r, **a} for r, a in sorted(p.actions.items())]
            if reveal
            else None
        ),
    }
    return state


def _round_votes(table, r: int) -> list[dict]:
    """The lynch votes cast at round r's dawn (killers/heals stay in the
    hover tooltips behind the reveal toggle)."""
    return [
        {
            "from": p.name,
            "vote": a["vote"] or None,
            "reasoning": a.get("reasoning") or None,
        }
        for p in table.players
        if (a := p.actions.get(r)) is not None
    ]


def _table_state(table, reveal: bool) -> dict:
    revealed_chat = table.phase in (Phase.ACT, Phase.OVER)
    return {
        "id": table.id,
        "phase": table.phase.value,
        "round": table.round,
        "seats": table.config.size,
        "min_players": table.min_players(),
        "winner": table.winner,
        "pace": table.pace,
        "pending": table.pending,
        "deadline_in": (
            max(0, int(table.deadline - time.time())) if table.deadline else None
        ),
        "players": [_player_state(table, p, reveal) for p in table.players],
        "news": [
            {
                "round": r,
                "lines": lines,
                # cast lynch votes, key-holders only (round 1 has no lynch)
                **(
                    {"votes": _round_votes(table, r)}
                    if reveal and r >= 2
                    else {}
                ),
            }
            for r, lines in sorted(table.events.items())
        ],
        "chat": [
            {"round": r, "from": name, "message": msg}
            for r in sorted(table.chat)
            if r < table.round or revealed_chat or reveal
            for name, msg in table.chat[r]
        ],
    }


async def api_state(request: Request) -> JSONResponse:
    reveal = request.query_params.get("key") == admin_key
    return JSONResponse(
        {
            "reveal": reveal,
            "rules": {
                "killers": game.config.killers,
                "healers": game.config.healers,
                "table_size": game.config.size,
            },
            "tables": [_table_state(t, reveal) for t in game.tables],
        }
    )


async def api_start(request: Request) -> JSONResponse:
    table, err = _admin_table(request)
    if err:
        return err
    try:
        table.start()
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True})


def _admin_table(request: Request):
    """Key-gated table lookup shared by the host-control endpoints."""
    if request.query_params.get("key") != admin_key:
        return None, JSONResponse({"error": "bad key"}, status_code=403)
    table_id = int(request.path_params["table_id"])
    table = next((t for t in game.tables if t.id == table_id), None)
    if table is None:
        return None, JSONResponse({"error": "no such table"}, status_code=404)
    return table, None


async def api_advance(request: Request) -> JSONResponse:
    table, err = _admin_table(request)
    if err:
        return err
    table.advance()
    return JSONResponse({"ok": True})


async def api_reset(request: Request) -> JSONResponse:
    table, err = _admin_table(request)
    if err:
        return err
    game.reset_table(table.id)
    return JSONResponse({"ok": True})


async def api_pace(request: Request) -> JSONResponse:
    table, err = _admin_table(request)
    if err:
        return err
    try:
        table.set_pace(request.query_params.get("mode", ""))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "pace": table.pace})


async def dashboard(request: Request) -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML.read_text(encoding="utf-8"))


async def index(request: Request) -> RedirectResponse:
    return RedirectResponse("/dashboard")


# ---- phase timer ---------------------------------------------------------


async def phase_ticker() -> None:
    """Once per second: advance any table whose phase deadline has passed.

    This is what makes one crashed student agent unable to freeze a table."""
    while True:
        await asyncio.sleep(1)
        now = time.time()
        for table in game.tables:
            if (
                table.phase in (Phase.TALK, Phase.ACT)
                and table.deadline is not None
                and now >= table.deadline
            ):
                table.force_advance()


def build_app():
    app = mcp.streamable_http_app()
    app.router.routes += [
        Route("/", index),
        Route("/dashboard", dashboard),
        Route("/api/state", api_state),
        Route("/api/table/{table_id:int}/start", api_start, methods=["POST"]),
        Route("/api/table/{table_id:int}/advance", api_advance, methods=["POST"]),
        Route("/api/table/{table_id:int}/reset", api_reset, methods=["POST"]),
        Route("/api/table/{table_id:int}/pace", api_pace, methods=["POST"]),
    ]
    inner_lifespan = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with inner_lifespan(app):
            ticker = asyncio.create_task(phase_ticker())
            try:
                yield
            finally:
                ticker.cancel()

    app.router.lifespan_context = lifespan
    return app


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no packet is sent; just picks an interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def main() -> None:
    global game, admin_key
    parser = argparse.ArgumentParser(description="Agentic Mafia game server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--tables", type=int, default=2)
    parser.add_argument("--table-size", type=int, default=7)
    parser.add_argument("--killers", type=int, default=2, help="killers per table")
    parser.add_argument("--healers", type=int, default=1, help="healers per table")
    parser.add_argument("--talk-timeout", type=float, default=75.0)
    parser.add_argument("--act-timeout", type=float, default=75.0)
    parser.add_argument("--max-rounds", type=int, default=15)
    parser.add_argument(
        "--chat-history",
        choices=["round", "full"],
        default="round",
        help="'round': agents only ever see the current round's chat (they "
        "must build their own memory — the default, and the point); "
        "'full': agents get the whole history every round",
    )
    parser.add_argument(
        "--pace",
        choices=["manual", "auto"],
        default="manual",
        help="'manual' (default): each chat reveal and dawn waits for the "
        "host's ⏭ button on the dashboard — the room gets to react; "
        "'auto': phases flip as soon as everyone has submitted. "
        "Toggleable live, per table, from the dashboard",
    )
    parser.add_argument(
        "--reveal-dead-roles",
        action="store_true",
        help="classic-Mafia flip: dawn announces each dead player's role. "
        "Default off — the harder game where alignment must be deduced; "
        "turn on if agents keep hallucinating roles for the dead",
    )
    parser.add_argument("--key", default=None, help="dashboard admin key")
    args = parser.parse_args()

    config = TableConfig(
        size=args.table_size,
        killers=args.killers,
        healers=args.healers,
        talk_timeout=args.talk_timeout,
        act_timeout=args.act_timeout,
        max_rounds=args.max_rounds,
        chat_history=args.chat_history,
        pace=args.pace,
        reveal_dead_roles=args.reveal_dead_roles,
    )
    if config.killers + config.healers + 2 > config.size:
        parser.error("--table-size must be at least killers + healers + 2")
    game = Game(args.tables, config)
    admin_key = args.key or secrets.token_hex(3)

    ip = lan_ip()
    print()
    print("🔪 Agentic Mafia server")
    print(f"   tables: {args.tables} × {config.size} seats "
          f"({config.killers} killers, {config.healers} healers each)")
    print(f"   agents connect to →  http://{ip}:{args.port}/mcp")
    print(f"   dashboard (keep the key private!) →  "
          f"http://{ip}:{args.port}/dashboard?key={admin_key}")
    print()
    uvicorn.run(build_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
