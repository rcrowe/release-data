import re
from pathlib import Path
from common import endoflife
from common.git import Git

"""
Fetch Red Hat OpenShift versions from the documentation git repository
"""

PRODUCT = "red-hat-openshift"
REPO_URL = "https://github.com/openshift/openshift-docs.git"


def get_versions_from_file(release_notes_file: Path) -> dict:
    if not release_notes_file.exists():
        return {}

    with open(release_notes_file, "rb") as f:
        plain = f.read().decode("utf-8")

    return {
        version: date
        for (version, date) in re.findall(
            r"{product-title}\s(?P<version>\d+\.\d+\.\d+).*$\n+Issued:\s(?P<date>\d{4}-\d\d-\d\d)$",
            plain,
            re.MULTILINE,
        )
    }

git = Git(REPO_URL)
git.setup()
versions = {}

# only fetch v4+ branches, because the format was different in openshift v3
for branch in git.list_branches("refs/heads/enterprise-[4-9]*"):
    version = branch.split("-")[1].replace(".", "-")
    release_notes_file = f"release_notes/ocp-{version}-release-notes.adoc"
    git.checkout(branch, file_list=[release_notes_file])
    versions = {**versions, **get_versions_from_file(git.repo_dir / release_notes_file)}

# Typo in https://github.com/openshift/openshift-docs/blob/enterprise-4.12/release_notes/ocp-4-12-release-notes.adoc.
versions['4.12.1'] = '2023-01-30'

print(f"::group::{PRODUCT}")
for version, date in versions.items():
    print(f"{version}: {date}")
print("::endgroup::")

endoflife.write_releases(
    PRODUCT,
    dict(
        # sort by date then version (desc)
        sorted(versions.items(), key=lambda x: (x[1], x[0]), reverse=True)
    ),
)
