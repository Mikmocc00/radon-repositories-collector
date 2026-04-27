import argparse
import copy
import io
import json
import os
from datetime import datetime
from getpass import getpass

from repocollector.github import GithubRepositoriesCollector
from repocollector.report import create_report

VERSION = "0.0.7"


def date(x: str) -> datetime:
    try:
        return datetime.strptime(x, '%Y-%m-%d')
    except Exception:
        raise argparse.ArgumentTypeError('Date format must be: YYYY-MM-DD')


def get_parser():
    parser = argparse.ArgumentParser(prog='repositories-collector', description='Radon Repo Collector')
    parser.add_argument('--since', type=date, default=datetime(2020, 1, 1))
    parser.add_argument('--until', type=date, default=datetime.now())
    parser.add_argument('--dest', type=str, required=True)
    parser.add_argument('--primary-language', type=str, default='terraform')
    parser.add_argument('--min-stars', type=int, default=0)
    parser.add_argument('--verbose', action='store_true', default=True)
    return parser


def main():
    args = get_parser().parse_args()

    if not os.path.exists(args.dest):
        os.makedirs(args.dest)

    token = os.getenv('GITHUB_ACCESS_TOKEN') or getpass('Github token:')
    github = GithubRepositoriesCollector(access_token=token)

    print(f"Inizio ricerca per: {args.primary_language}...")
    repositories = []

    
    date_push = datetime(2010, 1, 1)

    for repo in github.collect_repositories(
            since=args.since, until=args.until, pushed_after=date_push,
            min_stars=args.min_stars, primary_language=args.primary_language):

        repositories.append(repo)
        if args.verbose:
            print(f'Trovato: {repo["full_name"]} ({repo["stars"]} stars)')

    if not repositories:
        print("ATTENZIONE: Nessun repository trovato con questi criteri.")
        return

    json_path = os.path.join(args.dest, 'repositories.json')
    with open(json_path, "w") as f:
        json.dump(repositories, f, indent=4)

    html_path = os.path.join(args.dest, 'repositories.html')
    with io.open(html_path, "w", encoding="utf-8") as f:
        f.write(create_report(repositories))

    print(f"Completato! {len(repositories)} repository salvati in {args.dest}")


if __name__ == "__main__":
    main()
