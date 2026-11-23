"""Provision or inspect PETRO-TWIN users without embedding bootstrap credentials in the app."""
import argparse
import getpass
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_service.auth import AuthenticationService
from ml_service.config import config
from ml_service.persistence import AnalysisRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="PETRO-TWIN local user administration")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="Create a user (use this to create the first administrator)")
    create.add_argument("--username", required=True)
    create.add_argument("--role", choices=("admin", "engineer", "operator", "viewer"), default="admin")
    sub.add_parser("list", help="List user accounts without password data")
    args = parser.parse_args()

    repository = AnalysisRepository(config.database_url)
    repository.initialize()
    service = AuthenticationService(repository, config.jwt_secret or secrets.token_urlsafe(48),
                                    config.token_ttl_minutes)
    if args.command == "list":
        for user in repository.list_auth_users():
            print(f"{user['username']}  role={user['role']}  active={user['is_active']}")
        return 0

    password = getpass.getpass("New password (minimum 12 characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        return 2
    if repository.get_auth_user_by_username(args.username.casefold()):
        print("Username already exists.", file=sys.stderr)
        return 2
    try:
        user = service.create_user(args.username, password, args.role)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Created {user['username']} with role={user['role']}. Password was not written to disk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
