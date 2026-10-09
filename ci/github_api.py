"""Small GitHub client; callers keep API responses in private diagnostics."""

import json
import urllib.error
import urllib.parse
import urllib.request


class PrivateRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        redirected = super().redirect_request(request, fp, code, message, headers, new_url)
        if redirected is not None and urllib.parse.urlparse(new_url).hostname != 'api.github.com':
            redirected.remove_header('Authorization')
        return redirected


class GitHub:
    def __init__(self, repository, token):
        if not token:
            raise ValueError("A repository-scoped token is required")
        self.repository = repository
        self.token = token

    def request(self, path, method="GET", data=None, raw=None, content_type=None):
        url = "https://api.github.com/repos/" + self.repository + path
        if path.startswith("https://uploads.github.com/"):
            parsed = urllib.parse.urlparse(path)
            if parsed.path != "/repos/" + self.repository + "/releases/" + parsed.path.split("/")[-2] + "/assets":
                raise ValueError("Unexpected upload endpoint")
            url = path
        headers = {
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "public-client-build",
        }
        body = raw
        if data is not None:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        elif raw is not None:
            headers["Content-Type"] = content_type or "application/octet-stream"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.build_opener(PrivateRedirect()).open(request, timeout=180) as response:
            result = response.read()
        return json.loads(result) if result else None

    def require_private(self):
        metadata = self.request("")
        if metadata.get("private") is not True:
            raise ValueError("The source and destination repository must remain private")
        return metadata

    def release(self, tag):
        try:
            return self.request("/releases/tags/" + urllib.parse.quote(tag, safe=""))
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
        # The by-tag endpoint only returns published releases. Drafts are
        # visible to authorized maintainers in the paginated release list.
        # Without this lookup every platform would create another draft.
        page = 1
        matches = []
        while True:
            batch = self.request(f"/releases?per_page=100&page={page}")
            matches.extend(release for release in batch if release["tag_name"] == tag)
            if len(batch) < 100:
                break
            page += 1
        if len(matches) > 1:
            raise ValueError("More than one release has the selected tag; inspect the private drafts")
        return matches[0] if matches else None

    def assets(self, release):
        results = []
        page = 1
        while True:
            batch = self.request(f"/releases/{release['id']}/assets?per_page=100&page={page}")
            results.extend(batch)
            if len(batch) < 100:
                return results
            page += 1

    def asset_json(self, asset):
        # The browser URL requires authentication even for a draft release.
        url = "https://api.github.com/repos/" + self.repository + f"/releases/assets/{asset['id']}"
        request = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/octet-stream",
            "User-Agent": "public-client-build",
        })
        with urllib.request.build_opener(PrivateRedirect()).open(request, timeout=180) as response:
            return json.load(response)

    def upload(self, release, filename, data, replace=False):
        matches = [asset for asset in self.assets(release) if asset["name"] == filename]
        if matches and not replace:
            raise ValueError("Asset already exists")
        for asset in matches:
            self.request(f"/releases/assets/{asset['id']}", method="DELETE")
        endpoint = release["upload_url"].split("{")[0]
        endpoint += "?name=" + urllib.parse.quote(filename, safe="")
        return self.request(endpoint, method="POST", raw=data)

    def upload_json(self, release, filename, data, replace=False):
        return self.upload(release, filename, (json.dumps(data, indent=2) + "\n").encode(), replace)
