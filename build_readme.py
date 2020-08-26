from python_graphql_client import GraphqlClient
import feedparser
import httpx
import json
import pathlib
import re
import os

root = pathlib.Path(__file__).parent.resolve()
client = GraphqlClient(endpoint="https://api.github.com/graphql")


TOKEN = os.environ.get("HFAN22_TOKEN", "")


def replace_chunk(content, marker, chunk, inline=False):
    r = re.compile(
        r"<!\-\- {} starts \-\->.*<!\-\- {} ends \-\->".format(marker, marker),
        re.DOTALL,
    )
    if not inline:
        chunk = "\n{}\n".format(chunk)
    chunk = "<!-- {} starts -->{}<!-- {} ends -->".format(marker, chunk, marker)
    return r.sub(chunk, content)

def make_query(after_cursor=None, include_organization=False):
    return """
    query {
        viewer {
            pullRequests(first: 10, baseRefName: "master", orderBy:{field: CREATED_AT, direction: DESC}) {
            totalCount,
            pageInfo {
                hasNextPage
                endCursor
            },
            nodes {
                url,
                repository {
                name,
                url
                },
                headRefName,
                commits {
                totalCount
                },
                comments {
                totalCount
                },
                reviews {
                totalCount,
                }
                createdAt,
                mergedAt
            }
            }
        }
        }
    """.replace(
        "AFTER", '"{}"'.format(after_cursor) if after_cursor else "null"
    )


def fetch_pull_requests(oauth_token):
    pull_requests = []
    pull_request_nodes = []
    repos = set()
    has_next_page = True
    after_cursor = None

    first = True

    while has_next_page:
        data = client.execute(
            query=make_query(after_cursor, include_organization=first),
            headers={"Authorization": "Bearer {}".format(oauth_token)},
        )
        first = False
        print()
        print(json.dumps(data, indent=4))
        print()
        pull_request_nodes = data["data"]["viewer"]["pullRequests"]["nodes"]
        for pr in pull_request_nodes:
            if pr["repository"]["name"] not in repos:
                repos.add(pr["repository"]["name"])
            pull_requests.append(pr)
            pull_request_nodes.append(
                {
                    "pull_request_url": pr["url"],
                    "repository": pr["repository"]["name"],
                    "head_branch": pr["headRefName"],
                    "total_commits": pr["commits"]["totalCount"],
                    "total_comments": pr["comments"]["totalCount"],
                    "created_at": pr["createdAt"],
                    "merged_at": pr["mergedAt"],
                    "repo_url": pr["repository"]["url"]
                }
            )
        has_next_page = data["data"]["viewer"]["pullRequests"]["pageInfo"]["hasNextPage"]
        after_cursor = data["data"]["viewer"]["pullRequests"]["pageInfo"]["endCursor"]
    return pull_request_nodes


if __name__ == "__main__":
    readme = root / "README.md"
    pull_request_nodes = fetch_pull_requests(TOKEN)
    pull_request_nodes.sort(key=lambda r: r["created_at"], reverse=True)
    md = "\n\n".join(
        [
            "[{repository} {head_branch}]({pull_request_url}) - {created_at}".format(**pull_request_nodes)
            for pr in pull_request_nodes[:8]
        ]
    )
    readme_contents = readme.open().read()
    rewritten = replace_chunk(readme_contents, "recent_pull_requests", md)
    readme.open("w").write(rewritten)
