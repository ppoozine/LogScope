from alembic import op


def add_updated_at_trigger(table_name: str) -> None:
    op.execute(f"""
        CREATE TRIGGER trg_{table_name}_updated_at
        BEFORE UPDATE ON {table_name}
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def drop_updated_at_trigger(table_name: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_updated_at ON {table_name};")


def create_set_updated_at_function() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = NOW();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def drop_set_updated_at_function() -> None:
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
