"""
MCP_QA_Automation
-----------------
An MCP server exposing two defect-triage tools to any MCP-compatible client
(Claude Desktop, other MCP clients, etc.):

  1. triage_defect     - fast keyword-based severity + defect-vs-change-request
  2. triage_defect_ai  - LLM-backed structured triage for one or many defects

Both accept raw text and/or Jira keys (Jira needs .env).

Run with:
    mcp dev server.py          # opens MCP Inspector for manual testing
    python server.py           # runs the server directly (stdio transport)
"""

from mcp.server.fastmcp import FastMCP

from tools.defect_triage import triage_defect, triage_defect_ai

mcp = FastMCP("MCP-QA-Automation")

mcp.tool()(triage_defect)
mcp.tool()(triage_defect_ai)


if __name__ == "__main__":
    mcp.run()
