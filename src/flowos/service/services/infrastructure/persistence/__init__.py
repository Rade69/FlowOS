"""Persistence — SQLAlchemy modeli, session factory, Alembic migracije.

Backend je jedini SQLite writer. Svi ORM modeli su privatni za ovaj modul.
API Controlleri i drugi servisi dobijaju samo DTO objekte.
"""
