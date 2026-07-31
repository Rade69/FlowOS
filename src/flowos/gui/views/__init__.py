"""FlowOS GUI Views — PySide6 widgeti za prikaz i unos.

View je isključivo prikaz i prikupljanje korisničkih akcija.
View sme: prikazati DTO/ViewModel podatke, emitovati Qt signal
sa korisničkom namerom, upravljati lokalnim vizuelnim stanjem.
View ne sme: pozivati FastAPI direktno, pristupati bazi,
izvršavati Git komande, pokretati procese, donositi odluku
da li je neka akcija dozvoljena.
"""
