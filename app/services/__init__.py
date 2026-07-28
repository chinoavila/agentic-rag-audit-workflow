"""Lógica de dominio compartida entre routers y el pipeline de RAG.

A diferencia de `app/models/` (ORM) y `app/routers/` (HTTP), este paquete es para reglas de
negocio consumidas por más de un caller (p. ej. un endpoint FastAPI *y* el índice de
retrieval) que no deben reimplementarse en paralelo -- ver `tool_eligibility.py`.
"""
