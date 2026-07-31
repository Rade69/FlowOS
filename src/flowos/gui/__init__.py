# FlowOS GUI — PySide6 + Qt Widgets prikazni sloj
#
# View → Controller → Services troslojna arhitektura.
# View ne sme direktno pozivati Services niti pristupati mreži/disku/bazi.
# Controller ne sme sadržati SQL, Git, subprocess ni poslovna pravila.
# Services komunicira sa backendom preko HTTP/WebSocket-a.
