"""CLI entry point for the UI-Pro launcher."""
import argparse

from scripts.launcher.dependencies import check_dependencies, check_prerequisites
from scripts.launcher.services import (
    check_services,
    run_tests,
    start_all,
    start_api,
    start_ui,
)


def main():
    parser = argparse.ArgumentParser(
        description="UI-Pro Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python run.py             Lance tous les services
  python run.py --api         FastAPI uniquement
  python run.py --ui          Next.js UI uniquement
  python run.py --status      Vér status
  python run.py --check        Vérifie dépendances
  python run.py --prereq      Vérifie tous les prérequis
  python run.py --test       Lance les tests
        """,
    )

    parser.add_argument("--api", action="store_true", help="Lance FastAPI")
    parser.add_argument("--ui", action="store_true", help="Lance Next.js UI")
    parser.add_argument("--all", action="store_true", help="Lance tous les services")
    parser.add_argument("--status", action="store_true", help="Vér status")
    parser.add_argument("--check", action="store_true", help="Vérifie dépendances")
    parser.add_argument(
        "--prereq", action="store_true", help="Vérifie tous les prérequis"
    )
    parser.add_argument("--test", action="store_true", help="Lance les tests")
    parser.add_argument(
        "--no-open", action="store_true", help="Pas d'auto-open browser"
    )

    args = parser.parse_args()

    # Default: show status
    if not any(
        [args.api, args.ui, args.all, args.status, args.check, args.prereq, args.test]
    ):
        args.all = True

    if args.status:
        check_services()

    elif args.check:
        check_dependencies()

    elif args.prereq:
        check_prerequisites()

    elif args.test:
        if check_dependencies():
            run_tests()

    elif args.ui:
        start_ui()

    elif args.all:
        start_all(auto_open=not args.no_open)

    elif args.api:
        start_api()
