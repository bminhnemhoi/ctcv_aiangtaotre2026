"""ctcv-agent: the coach agent of CTCV (planner, quarantine, tool router, guardrails).

Module boundaries enforce the CaMeL split (idea §5, ADR-004):

* ``ctcv_agent.quarantine`` reads untrusted text and returns a closed schema; it never
  imports the router or the tools.
* ``ctcv_agent.tools`` holds the eight whitelisted tools; no tool module may import a
  network or process library (``tests/invariants/test_tool_whitelist.py``).
* ``ctcv_agent.coach`` is the only module that talks to the planner and dispatches tools.

Submodules are imported explicitly (``from ctcv_agent import coach``) to keep import
side effects small.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
