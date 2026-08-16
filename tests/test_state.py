"""StateManager 持久化测试"""
import json
from pathlib import Path

import pytest


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / '.sshm_state'


@pytest.fixture
def state(state_file):
    from sshm.core.state import StateManager
    return StateManager(state_file)


class TestLang:
    def test_default_lang(self, state):
        assert state.read_lang() == 'en'

    def test_write_read_lang(self, state):
        state.write_lang('zh')
        assert state.read_lang() == 'zh'

    def test_lang_persisted_to_file(self, state, state_file):
        state.write_lang('zh')
        data = json.loads(state_file.read_text(encoding='utf-8'))
        assert data['lang'] == 'zh'


class TestAutoAuthor:
    def test_default_true(self, state):
        assert state.read_auto_author() is True

    def test_persist(self, state, state_file):
        state.write_auto_author(False)
        data = json.loads(state_file.read_text(encoding='utf-8'))
        assert data['auto_author'] is False


class TestHostsAuthors:
    def test_hosts(self, state):
        state.write_host('work', 'gitlab.com')
        assert state.read_hosts()['work'] == 'gitlab.com'

    def test_authors(self, state):
        state.write_author('work', 'Alice', 'a@x.com')
        assert state.read_authors()['work']['name'] == 'Alice'

    def test_active_keys(self, state):
        state.write_active_key('ed25519', 'work')
        assert state.read_active_keys()['ed25519'] == 'work'
