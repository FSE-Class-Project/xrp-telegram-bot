# Database Migrations

This project uses Alembic for database schema migrations.

## Migration Commands

### Using the migrate.py script (Recommended)

```bash
# Check current migration status
python migrate.py current

# Create a new migration
python migrate.py create "Add new column to users table"

# Upgrade to latest migration
python migrate.py upgrade

# Upgrade to specific revision
python migrate.py upgrade abc123

# Downgrade to specific revision
python migrate.py downgrade abc123

# Show migration history
python migrate.py history

# Stamp database with revision (without running migrations)
python migrate.py stamp head
```

### Using Alembic directly

```bash
# Check current revision
alembic current

# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Upgrade database
alembic upgrade head

# Downgrade database
alembic downgrade -1

# Show migration history
alembic history --verbose
```

## Migration Workflow

1. **Make model changes** in `backend/database/models.py`
2. **Create migration**: `python migrate.py create "Description of changes"`
3. **Review migration** in `alembic/versions/`
4. **Apply migration**: `python migrate.py upgrade`

## Important Notes

- Always review generated migrations before applying them
- Test migrations on development data before production
- Create backups before running migrations in production
- The database is automatically initialized with migrations on startup
- If migrations fail, the system falls back to direct table creation

## Migration Files

- `alembic.ini` - Alembic configuration
- `alembic/env.py` - Migration environment setup
- `alembic/versions/` - Migration files
- `migrate.py` - CLI tool for migration management
