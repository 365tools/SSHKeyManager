"""GitRepoService 单元测试：URL 解析、别名生成、hostname 反查"""

from pathlib import Path

import pytest


class _FakeState:
    """内存版 state_manager：只暴露 GitRepoService 用到的读写接口"""

    def __init__(self):
        self.hosts = {}
        self._store = {}

    def read_hosts(self) -> dict:
        return self.hosts

    def write_host(self, label: str, hostname: str) -> None:
        self.hosts[label.lower()] = hostname

    def remove_host(self, label: str) -> None:
        self.hosts.pop(label.lower(), None)


class _FakeConfig:
    def __init__(self):
        self.hostname_map = {}
        self.config_file = Path("/tmp/nonexistent_config")

    def get_hostname(self, host: str):
        return self.hostname_map.get(host)

    def has_host(self, label: str) -> bool:
        return False


class _FakeKeyStore:
    def __init__(self, labels=None):
        self.labels = labels or []

    def scan_all_keys(self) -> dict:
        return {l: [] for l in self.labels}


@pytest.fixture
def service():
    from sshm.core.services.git.gitrepo import GitRepoService

    errors = []
    svc = GitRepoService(
        Path("/tmp/ssh"),
        _FakeConfig(),
        _FakeState(),
        _FakeKeyStore(),
        error_reporter=errors.append,
    )
    svc._errors = errors
    return svc


class TestParseGitUrl:
    def test_scp_like(self, service):
        # git@github.com:user/repo.git
        assert service.parse_git_url("git@github.com:user/repo.git") == (
            "github",
            "user",
            "repo",
        )

    def test_scp_like_no_git_suffix(self, service):
        assert service.parse_git_url("git@gitlab.com:org/proj") == (
            "gitlab",
            "org",
            "proj",
        )

    def test_ssh_protocol(self, service):
        assert service.parse_git_url("ssh://git@github.com/user/repo.git") == (
            "github",
            "user",
            "repo",
        )

    def test_ssh_protocol_with_port(self, service):
        assert service.parse_git_url("ssh://git@gitlab.com:2222/org/proj") == (
            "gitlab",
            "org",
            "proj",
        )

    def test_https(self, service):
        assert service.parse_git_url("https://github.com/user/repo.git") == (
            "github",
            "user",
            "repo",
        )

    def test_invalid_url(self, service):
        assert service.parse_git_url("not a url") is None
        assert service.parse_git_url("") is None


class TestPlatformFromHostname:
    def test_dot_host(self):
        from sshm.core.services.git.gitrepo import GitRepoService

        assert GitRepoService.platform_from_hostname("github.com") == "github"

    def test_dash_host(self):
        from sshm.core.services.git.gitrepo import GitRepoService

        assert GitRepoService.platform_from_hostname("git-codecommit.example") == "git"

    def test_with_port(self):
        from sshm.core.services.git.gitrepo import GitRepoService

        assert GitRepoService.platform_from_hostname("gitlab.com:2222") == "gitlab"


class TestHostnameForLabel:
    def test_uses_stored_mapping(self, service):
        service.state_manager.write_host("work", "self-hosted.com")
        assert service.get_hostname_for_label("work") == "self-hosted.com"

    def test_falls_back_to_wellknown(self, service):
        assert service.get_hostname_for_label("mygithub") == "github.com"

    def test_default_github(self, service):
        assert service.get_hostname_for_label("unknown-label") == "github.com"


class TestGetHostAlias:
    def test_alias_format(self, service):
        service.state_manager.write_host("work", "gitlab.com")
        assert service.get_host_alias("work") == "gitlab-work"


class TestResolveLabelFromAlias:
    def test_roundtrip(self, service):
        """get_host_alias 后能反解出原 label"""
        service.state_manager.write_host("eavelabs", "github.com")
        alias = service.get_host_alias("eavelabs")
        assert service.resolve_label_from_alias(alias) == "eavelabs"

    def test_unknown_alias_returns_none(self, service):
        assert service.resolve_label_from_alias("nope-xyz") is None


class TestResolveRepoHostname:
    def test_uses_config_hostname(self, service):
        # config 中有别名 -> 反查真实域名
        service.config_manager.hostname_map["mygit"] = "internal.example.com"
        assert (
            service.resolve_repo_hostname("git@mygit:org/repo")
            == "internal.example.com"
        )

    def test_fallback_to_url_host(self, service):
        assert service.resolve_repo_hostname("git@github.com:u/r") == "github.com"

    def test_invalid_returns_none(self, service):
        assert service.resolve_repo_hostname("not a url") is None
