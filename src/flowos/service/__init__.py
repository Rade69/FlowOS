# FlowOS Service — FastAPI backend sa troslojnom arhitekturom
#
# API Controllers su tanki — validiraju transportni oblik, pozivaju Service, vraćaju DTO.
# Backend Services sadrže svu poslovnu logiku, Git operacije, watcher, worktree.
# Infrastructure su interne implementacije Services sloja (persistence, filesystem, process).
# Backend sluša samo na 127.0.0.1. Jedini je SQLite writer.
