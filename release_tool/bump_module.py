import git
import github
import os
import sys
import contextlib
import datetime
from termcolor import colored

import changelog
from conf import get_settings

SETTINGS = get_settings()
MODULES = {v['module']: k for k, v in SETTINGS.iteritems()}


def get_gh_token():
    if 'GH_TOKEN' in os.environ:
        return os.environ['GH_TOKEN']
    else:
        print """
        Please enter your personal access token. If you don't have one
        See https://github.com/lbryio/lbry-app/wiki/Release-Script#generate-a-personal-access-token
        for instructions on how to generate one.

        You can also set the GH_TOKEN environment variable to avoid seeing this message
        in the future"""
        return raw_input('token: ').strip()


class Version(object):
    candidate_separator = "rc"

    def __init__(self, major, minor, patch, candidate=None):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.candidate = candidate

    def __repr__(self):
        v = "%i.%i.%i" % (self.major, self.minor, self.patch)
        if self.candidate:
            v += "rc%i" % self.candidate
        return v

    def __str__(self):
        return repr(self)

    @classmethod
    def parse(cls, version_string):
        major, minor, patch = version_string.split(".")
        major, minor = int(major), int(minor)
        try:
            patch = int(patch)
            candidate = None
        except ValueError:
            patch, candidate = patch.split(cls.candidate_separator)
            patch, candidate = int(patch), int(candidate)
        return cls(major, minor, patch, candidate)

    @property
    def is_candidate(self):
        return False if not self.candidate else True

    @property
    def is_release(self):
        return True if not self.candidate else False

    @property
    def tag(self):
        return "v%s" % self

    def release(self):
        if not self.is_candidate:
            print "there is no candidate to release"
            sys.exit(1)

    def bump_candidate(self, major=None, minor=None, patch=None):
        if not major and not minor and not patch and self.is_release:
            patch = True
        is_version_bump = True if (major or minor or patch) else False

        if major:
            self.major += 1
            self.minor = 0
            self.patch = 0
        elif minor:
            self.minor += 1
            self.patch = 0
        elif patch:
            self.patch += 1
        if is_version_bump:
            self.candidate = 0
        self.candidate += 1

    def bump_release(self, major=None, minor=None, patch=None):

        if not major and not minor and not patch and self.is_release:
            patch = True
        elif self.is_candidate:
            self.candidate = None

        if major:
            self.major += 1
            self.minor = 0
            self.patch = 0
        elif minor:
            self.minor += 1
            self.patch = 0
        elif patch:
            self.patch += 1
            self.candidate = 0


class BumpGitModule(object):
    def __init__(self, repo_name):
        self.repo_name = repo_name
        self.module_name = SETTINGS[self.repo_name]['module']
        self.directory = SETTINGS[self.repo_name]['path']
        self.git_repo = git.Repo(self.directory)
        active_branch = self.git_repo.active_branch
        is_dirty = self.git_repo.is_dirty()
        self.current_version = self._get_current_version()

        msg = u"%s" % self.module_name
        if active_branch != "master":
            msg += colored(u" (%s)" % active_branch, 'blue')
        else:
            msg += colored(u" (%s)" % active_branch, 'green')
        if is_dirty:
            msg += colored(u" dirty ", 'red') + u"\U0001F4A9"

        print msg

        gh_token = get_gh_token()
        auth = github.Github(gh_token)
        self.git_repo_v3 = auth.get_repo("%s/%s" % (SETTINGS[self.repo_name]['remote'],
                                                    self.repo_name))
        self.new_version = None
        changelog_path = os.path.join(self.directory, 'CHANGELOG.md')
        self._changelog = changelog.Changelog(self.module_name, changelog_path)

    @staticmethod
    def read_file(path, skip_setup=True):
        with open(path, "r") as f:
            data = f.read()
        lines = data.splitlines()
        results = []
        for line in lines:
            if skip_setup and line.startswith("setup("):
                break
            results.append(line)
        return "\n".join(results)

    @staticmethod
    def _exec_file(path, module_directory):
        _globals, _locals = {}, {"__file__": path}
        code = "import sys; sys.path.append('%s');\n%s" % (module_directory,
                                                           BumpGitModule.read_file(path))
        eval(compile(code, path, "exec"), _globals, _locals)
        return _locals

    @property
    def release_msg(self):
        return self.get_release_message()

    @property
    def is_rc(self):
        return self.new_version.is_candidate

    def _get_current_version(self):
        path = os.path.join(self.directory, self.module_name, "__init__.py")
        _locals = self._exec_file(path, self.directory)
        module_version = _locals.get("__version__")
        if not module_version:
            raise Exception("Repository %s (%s) does not have a __version__ configured "
                            "in __init__.py" % (self.repo_name, self.module_name))
        return Version.parse(module_version)

    def update_init(self):
        assert self.new_version
        path = os.path.join(self.directory, self.module_name, "__init__.py")
        init_file_content = self.read_file(path, False)
        lines = init_file_content.splitlines()
        position = None
        for i, line in enumerate(lines):
            if line.startswith("__version__ = "):
                position = i
                break
        if position is None:
            raise Exception("Failed to find __version__ in %s" % path)
        lines[position] = "__version__ = \"%s\"" % self.new_version
        updated_init_contents = "\n".join(lines) + "\n"
        with open(path, "w") as init_file:
            init_file.write(updated_init_contents)

    def get_module_requires(self):
        path = os.path.join(self.directory, "setup.py")
        _locals = self._exec_file(path, self.directory)
        requires = {req.split("==")[0]: req.split("==")[1] for req in _locals.get("requires")
                    if req.split("==")[0] in MODULES}
        return requires

    def update_setup(self, module_name, new_version):
        assert new_version
        path = os.path.join(self.directory, "setup.py")
        setup_file_contents = self.read_file(path, False)
        lines = setup_file_contents.splitlines()
        position = None
        for i, line in enumerate(lines):
            if "%s==" % module_name in line:
                position = i
                break
        if position is None:
            raise Exception("Failed to find requirement for %s in %s" % (module_name, path))
        wspace = len(lines[position]) - len(lines[position].lstrip())
        lines[position] = "'%s==%s'," % (module_name, new_version)
        if wspace:
            lines[position] = "%s%s" % (" " * wspace, lines[position])
        updated_setup_contents = "\n".join(lines) + "\n"
        with open(path, "w") as setup_file:
            setup_file.write(updated_setup_contents)

    def update_requires(self, module_name, new_version):
        assert new_version
        path = os.path.join(self.directory, "requirements.txt")
        requirements_file_contents = self.read_file(path, False)
        lines = requirements_file_contents.splitlines()
        position = None
        for i, line in enumerate(lines):
            if "egg=%s" % module_name in line:
                position = i
                break
        if position is None:
            raise Exception("Failed to find requirement for %s in %s" % (module_name, path))
        lines[position] = self.get_pip_link(module_name, new_version)
        updated_requirements_contents = "\n".join(lines) + "\n"
        with open(path, "w") as requirements_file:
            requirements_file.write(updated_requirements_contents)

    def get_pip_link(self, module_name, version):
        repo_name = MODULES[module_name]
        remote = SETTINGS[repo_name]['remote']
        return "git+https://github.com/%s/%s.git@v%s#egg=%s" % (remote, repo_name,
                                                                version, module_name)

    def get_release_message(self):
        return self._changelog.get_release_message(self.new_version)

    def bump_changelog(self):
        self._changelog.bump(self.new_version)
        with pushd(self.directory):
            self.git_repo.git.add(os.path.basename(self._changelog.path))

    def assert_new_tag_is_absent(self):
        new_tag = "v%s" % self.new_version
        tags = self.git_repo.git.tag()
        if new_tag in tags.split('\n'):
            raise Exception('Tag {} is already present in repo {}.'.format(new_tag,
                                                                           self.module_name))


class UpdateOp(object):
    def __init__(self, path, repo, fn, *args):
        self.path = path
        self.repo = repo
        self.fn = fn
        self.args = tuple(args)
        self._called = False

    def __call__(self):
        if self._called:
            raise Exception("Already called!")
        self._called = True
        args = self.args
        self.fn(*args)

    def get_info(self):
        return {
            "file": self.path,
            "repo": self.repo,
            "operation": self.fn.__name__,
            "params": list(self.args)
        }


class Stack(object):
    def __init__(self):
        self._stack = []
        self._position = 0
        self.verbose = False

    def add(self, item):
        if not isinstance(item, UpdateOp):
            raise Exception("Invalid op")
        self._stack.append(item)

    def __iter__(self):
        while self._stack:
            item, self._stack = self._stack[0], self._stack[1:]
            if self.verbose:
                print "update operation %i:\n%s\n" % (self._position + 1, item.get_info())
            yield item()
            self._position += 1

    def __len__(self):
        return len(self._stack)

    @property
    def files_touched(self):
        files = set(item.path for item in self._stack if item.path)
        return list(files)

    @property
    def repos_touched(self):
        repos = set(item.repo for item in self._stack if item.repo)
        return list(repos)

    @property
    def repo_sequence(self):
        result = []
        for item in self._stack:
            if item.repo and item.repo not in result:
                result.append(item.repo)
        return result

    @property
    def total_operations(self):
        return len(self._stack)


def bump_recurse(module_name, is_release, stack, bumped):
    _repo = GITHUB_REPOS[MODULES[module_name]]
    depends_on = [repo_settings['module'] for repo_name, repo_settings in SETTINGS.iteritems()
                  if module_name in repo_settings.get('depends on', [])]
    for to_bump in depends_on:
        req = GITHUB_REPOS[MODULES[to_bump]].get_module_requires().get(module_name)
        if req != _repo.current_version:
            if is_release:
                GITHUB_REPOS[MODULES[to_bump]].new_version = Version.parse(
                    repr(GITHUB_REPOS[MODULES[to_bump]].current_version))
                GITHUB_REPOS[MODULES[to_bump]].new_version.bump_release()
            else:
                GITHUB_REPOS[MODULES[to_bump]].new_version = Version.parse(
                    repr(GITHUB_REPOS[MODULES[to_bump]].current_version))
                GITHUB_REPOS[MODULES[to_bump]].new_version.bump_candidate()

                GITHUB_REPOS[MODULES[to_bump]].assert_new_tag_is_absent()

            print "bump %s from %s-->%s" % (GITHUB_REPOS[MODULES[to_bump]].module_name,
                                            colored(GITHUB_REPOS[MODULES[to_bump]].current_version,
                                                    attrs=['bold']),
                                            colored(GITHUB_REPOS[MODULES[to_bump]].new_version,
                                                    attrs=['bold']))

            stack.add(UpdateOp(os.path.join(GITHUB_REPOS[MODULES[to_bump]].directory,
                                            GITHUB_REPOS[MODULES[to_bump]].module_name,
                                            "__init__.py"), to_bump,
                                GITHUB_REPOS[MODULES[to_bump]].update_init))
            stack.add(UpdateOp(os.path.join(GITHUB_REPOS[MODULES[to_bump]].directory,
                                            "setup.py"), to_bump,
                                GITHUB_REPOS[MODULES[to_bump]].update_setup, _repo.module_name,
                                _repo.new_version))
            stack.add(UpdateOp(os.path.join(GITHUB_REPOS[MODULES[to_bump]].directory,
                                            "requirements.txt"), to_bump,
                                GITHUB_REPOS[MODULES[to_bump]].update_requires, _repo.module_name,
                                _repo.new_version))


            pos = None
            for i, l in enumerate(GITHUB_REPOS[MODULES[to_bump]]._changelog.unreleased):
                if l.startswith("  * Bumped `%s`" % bumped):
                    print "Updating changelog version bump (%i)" % i
                    pos = i
                    break

            if GITHUB_REPOS[MODULES[bumped]].new_version.is_release:
                skip_to = repr(GITHUB_REPOS[MODULES[bumped]].new_version)
                skip_to = skip_to.replace(".", "")
                skip_to = "%s---%s" % (skip_to, datetime.datetime.today().strftime('%Y-%m-%d'))
            else:
                skip_to = "unreleased"

            changelog_link = "https://github.com/lbryio/%s/blob/master/CHANGELOG.md#%s" % (bumped,
                                                                                           skip_to)
            msg = " * Bumped `%s` requirement to %s [see changelog](%s)"
            msg %= (bumped, GITHUB_REPOS[MODULES[bumped]].new_version, changelog_link)
            if pos is not None:
                GITHUB_REPOS[MODULES[to_bump]]._changelog.unreleased[pos] = msg
            else:
                if "### Changed" not in GITHUB_REPOS[MODULES[to_bump]]._changelog.unreleased:
                    GITHUB_REPOS[MODULES[to_bump]]._changelog.unreleased.append("### Changed")
                    GITHUB_REPOS[MODULES[to_bump]]._changelog.unreleased.append(msg)
                else:
                    for i, l in enumerate(GITHUB_REPOS[MODULES[to_bump]]._changelog.unreleased):
                        if l == "### Changed":
                            pos = i + 1
                            break

                    unreleased = GITHUB_REPOS[MODULES[to_bump]]._changelog.unreleased[:pos]
                    unreleased += [msg]
                    unreleased += GITHUB_REPOS[MODULES[to_bump]]._changelog.unreleased[pos:]
                    GITHUB_REPOS[MODULES[to_bump]]._changelog.unreleased = unreleased

            if GITHUB_REPOS[MODULES[to_bump]].new_version.is_release:
                # only update the changelog file for a release
                stack.add(UpdateOp(os.path.join(GITHUB_REPOS[MODULES[to_bump]].directory,
                                                'CHANGELOG.md'), to_bump,
                                    GITHUB_REPOS[MODULES[to_bump]].bump_changelog))

            if SETTINGS[MODULES[to_bump]].get('depends on'):
                stack = bump_recurse(to_bump, is_release, stack, to_bump)
    return stack


def get_update_ops(name, part, bump_deps=False):
    stack = Stack()
    repo = GITHUB_REPOS[MODULES[name]]
    repo.new_version = Version.parse(repr(repo.current_version))

    bump = {}
    if part == "release":
        is_release = True
        if repo.current_version.is_release:
            bump = {'patch': True}
    elif part == "candidate":
        is_release = False
    elif part in ['major', 'minor', 'patch']:
        bump = {part: True}
        is_release = True
    else:
        raise Exception("Invalid part to bump")

    if is_release:
        repo.new_version.bump_release(**bump)
    else:
        repo.new_version.bump_candidate(**bump)

    repo.assert_new_tag_is_absent()
    print "bump %s from %s-->%s" % (repo.module_name, colored(repo.current_version, attrs=['bold']),
                                    colored(repo.new_version, attrs=['bold']))

    if repo.new_version.is_release:
        stack.add(UpdateOp(os.path.join(repo.directory, 'CHANGELOG.md'), name, repo.bump_changelog))

    stack.add(UpdateOp(os.path.join(repo.directory, repo.module_name, "__init__.py"), name,
                       repo.update_init))

    if bump_deps:
        stack = bump_recurse(repo.module_name, is_release, stack, repo.module_name)

    return stack


@contextlib.contextmanager
def pushd(new_dir):
    previous_dir = os.getcwd()
    os.chdir(new_dir)
    yield
    os.chdir(previous_dir)


GITHUB_REPOS = {}

for repo_name, repo_settings in SETTINGS.iteritems():
    GITHUB_REPOS[repo_name] = BumpGitModule(repo_name)
