"""FlowOS GUI Controllers — koordinatori toka ekrana.

Controller povezuje View signale sa GUI Services pozivima,
validira UI format, mapira DTO u ViewState, i orkestrira
potvrdu korisnika pre rizične akcije.

Controller ne sme: sadržati SQL, formirati Git komande,
koristiti subprocess, implementirati poslovna pravila.
"""
