# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import argparse
from termcolor import colored
from bump_module import GITHUB_REPOS, MODULES, get_update_ops, pushd


def release_tool(name, part="candidate", bump_deps=False):
    stack = get_update_ops(name, part, bump_deps)
    touched = stack.files_touched
    repos = stack.repos_touched
    print "%i operations, %i files touched, %i repos touched" % (len(stack), len(touched),
                                                                 len(repos))
    for f in touched:
        print "    %s" % f

    print ""
    released = False

    bump_sequence = stack.repo_sequence

    for repo_name in bump_sequence:
        repo = GITHUB_REPOS[MODULES[repo_name]]
        git_repo = repo.git_repo_v3
        print u"push %s --> %s" % (colored(repo.new_version.tag, "blue"), git_repo.git_url)
        if not repo.is_rc:
            print colored("release notes:", "green")
            print repo.release_msg
            print ""
            if not released:
                released = True

    first_prompt = ""
    while first_prompt.lower() not in ["y", "yes", "n", "no"]:
        first_prompt = raw_input("look good? y/n: ")
    if first_prompt.lower() in ["y", "yes"]:
        pass
    else:
        exit()

    if released:
        second_prompt = ""
        msg = "this will push a release... is this what you mean to do?\n" \
              "type \"ship it\" or \"quit\"...\n"
        while second_prompt.lower() not in ["ship it", "quit"]:
            second_prompt = raw_input(msg)
        if second_prompt.lower() in ["ship it"]:
            pass
        else:
            exit()

    for op in iter(stack):
        pass

    for repo_name in bump_sequence:
        repo = GITHUB_REPOS[MODULES[repo_name]]
        repo.git_repo.index.add([path for path in [os.path.join(repo.directory, repo.module_name,
                                                                '__init__.py'),
                                 os.path.join(repo.directory, 'setup.py'),
                                 os.path.join(repo.directory, 'requirements.txt')]
                                 if os.path.isfile(path)], force=True)
        if not repo.is_rc:
            repo.git_repo.index.add([os.path.join(repo.directory, 'CHANGELOG.md')], force=True)
        repo.git_repo.index.update()
        bump_msg = "Bump version %s --> %s" % (repo.current_version, repo.new_version)
        commit = repo.git_repo.commit(repo.git_repo.index.commit(message=bump_msg))

        with pushd(repo.directory):
            output = subprocess.check_output(['git', 'commit', '-s', '-S', '--amend', '--no-edit'])

        tag = repo.git_repo.create_tag(repo.new_version.tag, repo.git_repo.head.ref,
                                       repo.new_version.tag, False)
        branch = repo.git_repo.active_branch
        repo.git_repo.remote("origin").push(branch.name)
        repo.git_repo.remote("origin").push(tag)
        repo.git_repo_v3.create_git_release(repo.new_version.tag, repo.new_version.tag,
                                            repo.release_msg, draft=True, prerelease=repo.is_rc)

        print u"commit %s (%s)" % (colored(repo.module_name, "green"), commit)

    if released:
        print colored(u"shipped release", 'green') + u"🚀"
    else:
        print colored(u"shipped candidate", 'green') + u"🚚"


def exit():
    print u"don't ship it! 🚚🚓"
    sys.exit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name", type=str, help="python module name")
    parser.add_argument("part", default="candidate", type=str,
                        help="major/minor/patch or candidate/release")
    parser.add_argument("-r", "--recurse_bump", default=True, action="store_true",
                        help="recurse bump dependencies")

    args = parser.parse_args()
    name, part, bump_deps = args.name, args.part, args.recurse_bump
    release_tool(name, part, bump_deps)


if __name__ == "__main__":
    main()
