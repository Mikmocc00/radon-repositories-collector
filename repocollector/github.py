import re
import requests

QUERY_TEMPLATE = """{ 
  search(query: "is:public stars:>=MIN_STARS mirror:false archived:false created:SINCE..UNTIL pushed:>=PUSHED_AFTER LANGUAGE:LANGUAGE", type: REPOSITORY, first: 50 AFTER) { 
    repositoryCount 
    pageInfo { endCursor startCursor hasNextPage } 
    edges { 
      node { 
        ... on Repository { 
          databaseId 
          defaultBranchRef { name } 
          owner { login } 
          name 
          url                
          description 
          primaryLanguage { name } 
          stargazers { totalCount } 
          watchers { totalCount } 
          releases { totalCount } 
          issues { totalCount } 
          createdAt 
          pushedAt 
          updatedAt 
          hasIssuesEnabled 
          isArchived 
          isDisabled 
          isMirror 
          isFork 
          # Estraiamo i file della root per un controllo rapido
          object(expression: "HEAD:") { 
            ... on Tree { 
              entries { 
                name 
                type 
              } 
            } 
          } 
        } 
      } 
    } 
  } 
  rateLimit {
    limit
    cost
    remaining
    resetAt
  }
}
"""


class GithubRepositoriesCollector:

    def __init__(self, access_token):
        self._token = access_token
        self._quota = 0
        self._quota_reset_at = None

    @property
    def quota(self):
        return self._quota

    @property
    def quota_reset_at(self):
        return self._quota_reset_at

    @staticmethod
    def filter_repositories(edges, min_issues: int = 0, min_releases: int = 0, min_watchers: int = 0):
        for edge in edges:
            node = edge.get('node')
            if not node:
                continue

            if node.get('isFork') or node.get('isArchived') or node.get('isDisabled'):
                continue

            issues = node['issues']['totalCount'] if node['issues'] else 0
            releases = node['releases']['totalCount'] if node['releases'] else 0
            stars = node['stargazers']['totalCount'] if node['stargazers'] else 0
            watchers = node['watchers']['totalCount'] if node['watchers'] else 0

            if issues < min_issues or releases < min_releases or watchers < min_watchers:
                continue

            primary_lang_node = node.get('primaryLanguage')
            primary_language = primary_lang_node['name'].lower() if primary_lang_node else ''

            obj = node.get('object')
            entries = obj.get('entries', []) if obj else []
            filenames = [e.get('name').lower() for e in entries]
            dirs = [e.get('name') for e in entries if e.get('type') == 'tree']

            name = node.get('name', '').lower()
            description = (node.get('description') or '').lower()

            is_terraform = (primary_language == 'hcl') or \
                           ('terraform' in name) or \
                           ('terraform' in description) or \
                           any(f.endswith('.tf') for f in filenames)

            k8s_files = ['deployment', 'service', 'ingress', 'kustomization', 'chart']

            is_kubernetes = (
                    ('kubernetes' in name or 'k8s' in name) or
                    ('kubernetes' in description or 'k8s' in description) or
                    (
                            any(f.endswith(('.yaml', '.yml')) for f in filenames) and
                            any(any(k in f for k in k8s_files) for f in filenames)
                    )
            )

            is_docker = (primary_language == 'dockerfile') or \
                        ('docker' in name) or \
                        ('docker' in description) or \
                        any('dockerfile' in f for f in filenames)

            is_ansible = (
                    any(f in filenames for f in ['playbook.yml', 'site.yml', 'main.yml']) or
                    any('roles' == d.lower() for d in dirs) or
                    any('ansible' in f for f in filenames)
            )

            tosca_pattern = re.compile(r'\btosca\b')

            is_tosca = (
                    any(tosca_pattern.search(f) for f in filenames) or
                    any(f.endswith(('.yaml', '.yml')) for f in filenames) and
                    any('topology' in f or 'node_types' in f for f in filenames) or
                    tosca_pattern.search(name) is not None or
                    tosca_pattern.search(description) is not None
            )

            if not (is_terraform or is_kubernetes or is_docker or is_ansible or is_tosca):
                continue

            owner = node.get('owner', {}).get('login', '')

            yield dict(
                id=node.get('databaseId'),
                default_branch=node.get('defaultBranchRef', {}).get('name') if node.get('defaultBranchRef') else None,
                owner=owner,
                name=node.get('name'),
                full_name=f'{owner}/{node.get("name")}',
                url=node.get('url'),
                description=node['description'] if node['description'] else '',
                issues=issues,
                releases=releases,
                stars=stars,
                watchers=watchers,
                primary_language=primary_language,
                created_at=str(node.get('createdAt')),
                pushed_at=str(node.get('pushedAt')),
                dirs=dirs,
                is_terraform=is_terraform,
                is_kubernetes=is_kubernetes,
                is_docker=is_docker,
                is_ansible=is_ansible,
                is_tosca=is_tosca
            )

    def collect_repositories(self, since, until, pushed_after, min_stars=0, min_releases=0,
                             min_watchers=0, min_issues=0, primary_language=None):

        query_base = QUERY_TEMPLATE

        if primary_language and primary_language.lower() == 'terraform':
            lang_filter = "terraform language:hcl"
        elif primary_language and primary_language.lower() == 'kubernetes':
            lang_filter = "kubernetes language:yaml"
        elif primary_language and primary_language.lower() == 'docker':
            lang_filter = "docker language:Dockerfile"
        elif primary_language and primary_language.lower() == 'ansible':
            lang_filter = "ansible"
        elif primary_language and primary_language.lower() == 'tosca':
            lang_filter = "tosca"
        elif primary_language:
            lang_filter = f"language:{primary_language}"
        else:
            lang_filter = ""

        query_base = re.sub('MIN_STARS', str(min_stars), query_base)
        query_base = re.sub('SINCE', since.strftime('%Y-%m-%dT%H:%M:%SZ'), query_base)
        query_base = re.sub('UNTIL', until.strftime('%Y-%m-%dT%H:%M:%SZ'), query_base)
        query_base = re.sub('PUSHED_AFTER', pushed_after.strftime('%Y-%m-%dT%H:%M:%SZ'), query_base)
        query_base = re.sub('LANGUAGE:LANGUAGE', lang_filter, query_base)

        has_next_page = True
        end_cursor = None

        while has_next_page:
            after_val = f', after: "{end_cursor}"' if end_cursor else ""
            tmp_query = re.sub('AFTER', after_val, query_base)

            response = requests.post('https://api.github.com/graphql',
                                     json={'query': tmp_query},
                                     headers={'Authorization': f'Bearer {self._token}'})

            if response.status_code != 200:
                print(f"Errore API: {response.status_code}")
                break

            result = response.json()
            if 'errors' in result:
                print(f"Errore GraphQL: {result['errors']}")
                break

            data = result.get('data', {}).get('search', {})
            if not data:
                break

            self._quota = int(result['data']['rateLimit']['remaining'])
            self._quota_reset_at = result['data']['rateLimit']['resetAt']

            page_info = data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage')
            end_cursor = page_info.get('endCursor')

            yield from self.filter_repositories(data.get('edges', []),
                                                min_issues, min_releases, min_watchers)