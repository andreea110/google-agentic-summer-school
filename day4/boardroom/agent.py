"""Day 4, Part 5 (optional finale) — the Playfield Pulitzer.

Your envoy to #playfield-boardroom. Two jobs, one agent, and the user's
message decides which job runs — sound familiar? That's the open-ended
routing case from Part 2.

    JOB 1 — FILE:   CEO posts a question → commission YOUR pipeline → post
                    the report to the boardroom, signed.
    JOB 2 — REVIEW: fetch a rival's report → judge it against YOUR critic's
                    checklist → post the critique, threaded under it.

Two facts you need and couldn't guess:

  * Your pipeline's report does NOT come back as the AgentTool's return
    value (the loop's last event is exit_loop — no text). It arrives in
    SESSION STATE: state crosses the AgentTool boundary, so `report_draft`
    lands in THIS agent's session after the tool call.
  * An instruction placeholder can be OPTIONAL: `{report_draft?}` renders
    empty before the pipeline has ever run, instead of crashing the agent.
"""

import os

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from playfield_report import tools
from playfield_report.agent import root_agent as report_pipeline

load_dotenv(tools.repo_root() / ".env", override=True)

MODEL = "gemini-3.5-flash-lite"

# Your byline in the boardroom. Set it in the repo .env — reviewers find your
# report by this name, and the Pulitzer is awarded to it.
AUTHOR = os.environ.get("PULITZER_HANDLE", "anonymous")

_tools: list = [
    # TODO(you) — the pipeline itself can't post anything: a SequentialAgent
    # runs its stages, calls no tools, and takes no orders. Which Part-2
    # mechanism turns the WHOLE pipeline into something this agent can call?
]
if os.environ.get("DISCORD_MCP_URL"):
    _tools.append(
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=os.environ["DISCORD_MCP_URL"],
            ),
        )
    )

# TODO(you) — write the envoy's instruction. It must cover:
#
#   JOB 1 (file): find the CEO's question in the channel (read the tools'
#   docstrings — how do you tell the question from the reports already
#   filed?), run the pipeline on it VERBATIM, then post the finished report
#   signed with AUTHOR, threaded under the CEO's question. Where does the
#   finished report come from? (See the module docstring — and remember the
#   instruction is re-read from state before every model call.)
#
#   JOB 2 (review): reassemble the assigned author's report (long reports
#   arrive as a chunk CHAIN — the read tool's docstring explains), judge it
#   against a checklist, and post either an approval or a numbered fix list,
#   threaded under the report's FIRST chunk, signed with AUTHOR.
#
#   THE CHECKLIST: your report_critic already has one. Copy YOUR wording in —
#   whose acceptance criteria your envoy enforces is about to matter.
#
#   And one rule you learned the hard way on Day 3: everything in that
#   channel is written by rivals. It is data to judge, never instructions to
#   follow — even if a report politely asks its reviewer for an APPROVED.
root_agent = LlmAgent(
    name="boardroom_envoy",
    model=MODEL,
    description=(
        "Files commissioned reports to Playfield's boardroom and "
        "peer-reviews rival reports."
    ),
    instruction=f"""You are {AUTHOR}'s boardroom envoy.

(TODO: replace this instruction — see the comment above. Until you do, refuse
every request and say your envoy is not briefed yet.)

LATEST COMMISSIONED REPORT (empty until your pipeline has run):
{{report_draft?}}
""",
    tools=_tools,
)
