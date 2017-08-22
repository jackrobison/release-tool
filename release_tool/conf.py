import os
import yaml


def get_conf_file(conf_path=None):
    conf_path = conf_path or os.path.expanduser("~/.release-tool.yml")
    if not os.path.isfile(conf_path):
        raise Exception("Config file (%s) is missing" % conf_path)
    with open(conf_path, "r") as conf_file:
        data = conf_file.read()
    return yaml.safe_load(data)


def get_settings():
    conf_file = get_conf_file()
    settings = {}
    for repo_name, repo_settings in conf_file.iteritems():
        settings[repo_name] = repo_settings
        if 'module' not in repo_settings:
            settings[repo_name]['module'] = repo_name
        if 'branch' not in repo_settings:
            settings[repo_name]['branch'] = 'master'
        settings[repo_name]['path'] = os.path.expandvars(settings[repo_name]['path'])
    return settings
