"""FlowOS API Controllers — tanke FastAPI rute.

Svaka ruta:
1. Validira transportni oblik (Pydantic).
2. Poziva jedan Service metod.
3. Vraća DTO ili ApiErrorResponse.

Nema poslovne logike u ruti. Nema direktnog pristupa bazi, Git-u,
filesystemu ili subprocess-u.
"""
