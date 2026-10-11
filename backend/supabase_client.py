"""The single server-side Supabase client (service-role key; bypasses RLS)."""

from functools import cache

from supabase import Client, create_client

from config import settings


@cache
def get_supabase() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
