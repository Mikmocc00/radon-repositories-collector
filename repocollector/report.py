import statistics
import datetime


def create_report(repositories: list) -> str:
    if not repositories:
        return "<html><body><h1>No repositories found</h1></body></html>"

    now = datetime.datetime.now()
    gen_date = now.strftime('%Y-%m-%d')

    # Calcolo medie in sicurezza
    def get_avg(key):
        return int(statistics.mean([r[key] for r in repositories])) if repositories else 0

    avg_issues = get_avg('issues')
    avg_releases = get_avg('releases')
    avg_stars = get_avg('stars')
    avg_watchers = get_avg('watchers')

    accordion = ''.join([__generate_card(r) for r in repositories])

    return f"""
    <!doctype html>
    <html lang="en">
        <head>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.1.3/css/bootstrap.min.css">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
            <title>Radon Report</title>
        </head>
        <body class="container">
            <div class="py-5 text-center">
                <h2>Radon Repositories Collector Report</h2>
                <p>Generated on: {gen_date}</p>
            </div>
            <div class="row mb-4">
                <div class="col-md-3"><div class="card p-3 text-center"><h5>Repos</h5><h3>{len(repositories)}</h3></div></div>
                <div class="col-md-3"><div class="card p-3 text-center"><h5>Avg Stars</h5><h3>{avg_stars}</h3></div></div>
                <div class="col-md-3"><div class="card p-3 text-center"><h5>Avg Issues</h5><h3>{avg_issues}</h3></div></div>
                <div class="col-md-3"><div class="card p-3 text-center"><h5>Avg Releases</h5><h3>{avg_releases}</h3></div></div>
            </div>
            <div class="accordion" id="repoAcc">
                {accordion}
            </div>
        </body>
    </html>
    """


def __generate_card(m: dict) -> str:
    return f"""
    <div class="card">
        <div class="card-header">
            <button class="btn btn-link" data-toggle="collapse" data-target="#c{m['id']}">
                {m['full_name']}
            </button>
            <a href="{m['url']}" target="_blank"><i class="fa fa-github"></i></a>
        </div>
        <div id="c{m['id']}" class="collapse" data-parent="#repoAcc">
            <div class="card-body">
                <p>{m['description']}</p>
                <span class="badge badge-secondary">Language: {m['primary_language']}</span>
                <span class="badge badge-info">Stars: {m['stars']}</span>
                <span class="badge badge-warning">Issues: {m['issues']}</span>
            </div>
        </div>
    </div>
    """