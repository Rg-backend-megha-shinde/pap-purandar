from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Repair public.auth_user.id primary key and sequence when id values are null/misconfigured."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'auth_user'
                LIMIT 1;
                """
            )
            if not cursor.fetchone():
                self.stdout.write(self.style.ERROR("public.auth_user table does not exist."))
                return

            cursor.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'auth_user' AND column_name = 'id'
                LIMIT 1;
                """
            )
            if not cursor.fetchone():
                self.stdout.write(self.style.WARNING("Adding missing id column to public.auth_user ..."))
                cursor.execute("ALTER TABLE public.auth_user ADD COLUMN id BIGINT;")

            self.stdout.write("Ensuring sequence/default and repairing null ids ...")
            cursor.execute("CREATE SEQUENCE IF NOT EXISTS public.auth_user_id_seq;")
            cursor.execute(
                """
                SELECT setval(
                    'public.auth_user_id_seq',
                    COALESCE((SELECT MAX(id) FROM public.auth_user), 0) + 1,
                    false
                );
                """
            )
            cursor.execute("UPDATE public.auth_user SET id = nextval('public.auth_user_id_seq') WHERE id IS NULL;")
            cursor.execute("ALTER TABLE public.auth_user ALTER COLUMN id SET DEFAULT nextval('public.auth_user_id_seq');")
            cursor.execute("ALTER TABLE public.auth_user ALTER COLUMN id SET NOT NULL;")
            cursor.execute("ALTER SEQUENCE public.auth_user_id_seq OWNED BY public.auth_user.id;")

            cursor.execute(
                """
                SELECT tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.table_schema = 'public'
                  AND tc.table_name = 'auth_user'
                  AND tc.constraint_type = 'PRIMARY KEY'
                  AND kcu.column_name = 'id'
                LIMIT 1;
                """
            )
            pk_exists = cursor.fetchone() is not None
            if not pk_exists:
                self.stdout.write("Adding primary key on public.auth_user(id) ...")
                cursor.execute("ALTER TABLE public.auth_user ADD CONSTRAINT auth_user_pkey PRIMARY KEY (id);")

            cursor.execute("SELECT COUNT(*) FROM public.auth_user WHERE id IS NULL;")
            null_count = cursor.fetchone()[0]

            if null_count == 0:
                self.stdout.write(self.style.SUCCESS("auth_user.id repaired successfully."))
            else:
                self.stdout.write(self.style.ERROR(f"auth_user.id still has {null_count} null values."))
