# ADR-001 — Granica odgovornosti između korisnika, FlowOS-a i AI agenata

## Odluka

FlowOS nije AI agent niti AI menadžer.

FlowOS je deterministički kontrolni sistem koji upravlja stanjem, izvršenjem, izolacijom, verifikacijom, dokazima i životnim ciklusom rada AI agenata.

Odgovornosti se dijele na tri nivoa:

### Korisnik

Korisnik je autoritet za:

- cilj i scope rada;
- produktne i značajne arhitektonske odluke;
- prioritete;
- prihvatljiv nivo rizika;
- izmjene acceptance kriterijuma;
- konačno prihvatanje ili odbijanje rezultata.

### FlowOS

FlowOS je autoritet za determinističke operativne funkcije:

- stanje projekta i taskova;
- dependency graph i ready frontier;
- worktree i branch lifecycle;
- pokretanje i nadzor agentskih procesa;
- sandbox lifecycle;
- timeout, retry i recovery pravila;
- Git stanje i konflikte;
- determinističku verifikaciju;
- EvidenceBundle;
- audit i timeline;
- primjenu korisnički definisanih policy pravila.

FlowOS ne koristi LLM za odluku koju je moguće pouzdano donijeti kodom.

### AI agent

AI agent dobija ograničen WorkItem i ima slobodu da odlučuje o taktičkoj implementaciji unutar dozvoljenog execution workspacea.

Agent može:

- istraživati relevantan kod;
- implementirati promjenu;
- pisati testove;
- predlagati poboljšanja;
- prijaviti nove rizike, probleme ili potrebne odluke.

Agent ne može samostalno:

- mijenjati cilj ili scope;
- mijenjati acceptance kriterijume;
- uklanjati ili dodavati strateške plan stavke;
- donositi značajne arhitektonske odluke bez odobrenja;
- proglasiti semantički neuspješan rezultat uspješnim;
- integrisati promjene u zaštićeni branch ako policy to eksplicitno ne dozvoljava.

## Osnovni princip

**Čovjek odlučuje šta i zašto.  
FlowOS kontroliše kada, gdje i pod kojim pravilima.  
AI agent odlučuje kako da izvrši konkretno dodijeljen zadatak.**

## Default autonomija

Default režim za FlowOS-pokrenute AFK coding agente je:

**Scoped Write / Managed Execution**

Agent radi u zasebnom branchu i worktreeju. FlowOS prati izvršenje i pokreće determinističku verifikaciju. Završeni rezultat prelazi u `READY_FOR_REVIEW`, a ne automatski u prihvaćen ili integrisan rezultat.

Automatska integracija nije dio početne implementacije.

## Eskalacija

Kada agent tokom izvršenja otkrije problem koji zahtijeva promjenu scopea, arhitekture ili acceptance kriterijuma, on ne donosi odluku samostalno.

Rezultat se evidentira kao finding ili `NEEDS_DECISION`, nakon čega FlowOS vraća kontrolu korisniku.