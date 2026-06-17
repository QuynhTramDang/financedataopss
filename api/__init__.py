"""HTTP API layer (FastAPI) exposing the LangGraph control plane to the web UI.

This is a thin read-mostly boundary over the existing Python modules
(graph workflow, observability, registry, monitoring, governance). It does not
re-implement domain logic — it normalizes state for the React frontend and
seeds demo investigations so the UI is fully populated offline (no LLM tokens
burned just to render screens).
"""
