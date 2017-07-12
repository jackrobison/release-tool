import os
import yaml

LBRYSCHEMA = "lbryschema"
LBRY = "lbrynet"
LBRYUM = "lbryum"
LBRYUM_SERVER = "lbryumserver"
REPO_ROOT = "lbryio"

DIRECTORIES = {
    LBRYSCHEMA: os.path.expanduser("~/lbry-metadata"),
    LBRY: os.path.expanduser("~/lbry"),
    LBRYUM: os.path.expanduser("~/lbryum"),
    LBRYUM_SERVER: os.path.expanduser("~/lbryum-server")
}

REPOS = {
    LBRYSCHEMA: "%s/lbryschema" % REPO_ROOT,
    LBRY: "%s/lbry" % REPO_ROOT,
    LBRYUM: "%s/lbryum" % REPO_ROOT,
    LBRYUM_SERVER: "%s/lbryum-server" % REPO_ROOT,
}

# a reverse version of the dict above
MODULES = {k: v for k, v in zip(REPOS.itervalues(), REPOS.iterkeys())}

DEPENDENCIES = {
    LBRYUM: [LBRYSCHEMA],
    LBRYUM_SERVER: [LBRYSCHEMA],
    LBRY: [LBRYSCHEMA, LBRYUM]
}


BUMP_SEQUENCE = {
    LBRYSCHEMA: [LBRYUM_SERVER, LBRYUM, LBRY],
    LBRYUM: [LBRY]
}


def get_conf_file():
    with open(os.path.expanduser("~/release-tool/release-tool.yml"), "r") as conf_file:
        data = conf_file.read()
    return yaml.safe_load(data)
