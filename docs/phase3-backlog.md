# Faza 3 — Neblokirajući backlog

Stavke koje ne blokiraju završetak Faze 3, ali treba da budu rešene pre
produkcionog izdanja ili u narednim fazama.

## 1. Production watcher E2E test — runtime pokrivenost

**Trenutno stanje:**
- `TestProductionWatcherWiring` koristi `_create_watcher_callback` iz
  composition_root-a — istu funkciju koju lifespan poziva pri startup-u
- Test dokazuje da produkcioni callback ispravno zapisuje FileActivity
  i detektuje WRITE_WRITE

**Ograničenje:**
- Lifespan pokreće watcher-e samo za projekte koji postoje u bazi pri
  startup-u, ne za dinamički dodate
- Test ne prolazi kroz ceo `create_app()` → lifespan → watcher startup
  lanac, već direktno poziva `_create_watcher_callback`

**Preporuka:**
Ojačati test u kasnijoj fazi (4+) tako što će lifespan podržavati
dinamičko dodavanje watcher-a ili će test koristiti bazu sa unapred
pripremljenim projektom pre kreiranja aplikacije.

## 2. Migraciona politika — formalizacija pre prvog izdanja

**Trenutno stanje:**
- `docs/phase3-migration-history.md` dokumentuje pre-release odluku o
  brisanju dve privremene migracije
- Migracioni lanac je konzistentan i prolazi round-trip test

**Ograničenje:**
- Ne postoji formalna politika o tome kada je dozvoljeno prepisivati
  migracionu istoriju, a kada je potrebno praviti kompatibilne nastavke

**Preporuka:**
Pre prvog stvarnog izdanja FlowOS-a, kreirati `docs/migration-policy.md`
koji definiše:
- Pravila za pre-release vs post-release migracije
- Proceduru za rebase/squash migracione istorije
- Testove za upgrade sa svih podržanih revision ID-jeva
- Odgovornost za migracioni integritet
