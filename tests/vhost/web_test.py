from datetime import date
from textwrap import dedent

import mock
import pytest

from ocflib.infra.github import GithubCredentials
from ocflib.infra.rt import RtCredentials
from ocflib.vhost.web import eligible_for_vhost
from ocflib.vhost.web import get_tasks
from ocflib.vhost.web import get_vhost_db
from ocflib.vhost.web import get_vhosts
from ocflib.vhost.web import GITHUB_VHOST_WEB_PATH
from ocflib.vhost.web import has_vhost
from ocflib.vhost.web import NewVirtualHostRequest
from ocflib.vhost.web import pr_new_vhost
from tests.fixtures_test import celery_app  # noqa


VHOSTS_EXAMPLE = """
# added 2017-09-16 kpengboy
staff ofc - /ofc

# [added 2015.05.05 ckuehl]
asucarch archive.asuc.org www.archive.asuc.org,modern.asuc.org,www.modern.asuc.org -

# [added 2015.04.16 ckuehl]
ocfwiki docs.ocf.berkeley.edu - - [hsts]
"""

VHOSTS_EXAMPLE_PARSED = {
    'ofc.berkeley.edu': {
        'aliases': [],
        'docroot': '/ofc',
        'flags': [],
        'username': 'staff',
    },
    'archive.asuc.org': {
        'aliases': [
            'www.archive.asuc.org',
            'modern.asuc.org',
            'www.modern.asuc.org',
        ],
        'docroot': '/',
        'flags': [],
        'username': 'asucarch',
    },
    'docs.ocf.berkeley.edu': {
        'aliases': [],
        'docroot': '/',
        'flags': ['hsts'],
        'username': 'ocfwiki',
    },
}


@pytest.yield_fixture
def mock_get_vhosts_db():
    with mock.patch(
        'ocflib.vhost.web.get_vhost_db',
        return_value=VHOSTS_EXAMPLE.splitlines()
    ):
        yield


class TestVirtualHosts:

    def test_reads_file(self):
        with mock.patch('builtins.open', mock.mock_open()) as mock_open:
            text = 'hello\nworld\n'
            mock_open.return_value.read.return_value = text
            assert get_vhost_db() == text.splitlines()

    def test_proper_parse(self, mock_get_vhosts_db):
        assert get_vhosts() == VHOSTS_EXAMPLE_PARSED

    @pytest.mark.parametrize('user,should_have_vhost', [
        ('staff', True),
        ('ocfwiki', True),
        ('ckuehl', False),
        ('', False),
    ])
    def test_has_vhost(self, user, should_have_vhost, mock_get_vhosts_db):
        assert has_vhost(user) == should_have_vhost

    @pytest.mark.parametrize('user,should_be_eligible', [
        ('mattmcal', False),
        ('ggroup', True),
        ('bh', True),
    ])
    def test_eligible_for_vhost(self, user, should_be_eligible):
        assert eligible_for_vhost(user) == should_be_eligible


@pytest.yield_fixture
def fake_credentials():
    yield {
        'rt': RtCredentials(username='ocf', password='password'),
        'github': GithubCredentials(token='ocf')
    }


@pytest.yield_fixture
def tasks(celery_app, fake_credentials):
    yield get_tasks(celery_app, fake_credentials)


@pytest.yield_fixture
def fake_new_vhost_request():
    yield NewVirtualHostRequest(
        'ocf',
        'ocf@ocf.berkeley.edu',
        'ocf.berkeley.edu',
        None,
        None,
        None,
        '0',
        'vhost request for ocf',
        'body',
    )


@pytest.yield_fixture
def mock_rt_connection():
    with mock.patch('ocflib.vhost.web.rt_connection') as m:
        yield m


@pytest.yield_fixture
def mock_rtticket_create():
    with mock.patch('ocflib.vhost.web.RtTicket.create') as m:
        yield m


@pytest.yield_fixture
def mock_pr_new_vhost():
    with mock.patch('ocflib.vhost.web.pr_new_vhost') as m:
        yield m


@pytest.yield_fixture
def mock_github():
    with mock.patch('ocflib.infra.github.Github') as m:
        yield m


@pytest.yield_fixture
def mock_gitrepo():
    with mock.patch('ocflib.vhost.web.GitRepo') as m:
        yield m


def test_create_new_vhost_successful(
        celery_app,
        mock_rt_connection,
        mock_rtticket_create,
        fake_new_vhost_request,
        mock_pr_new_vhost,
        fake_credentials,
        tasks):

    mock_rtticket_create.return_value = 3
    resp = tasks.create_new_vhost(fake_new_vhost_request)
    assert resp
    mock_rt_connection.assert_called_with(
        'ocf',
        'password',
    )
    mock_rtticket_create.assert_called_with(
        mock_rt_connection(),
        'hostmaster',
        fake_new_vhost_request.requestor,
        fake_new_vhost_request.subject,
        fake_new_vhost_request.message,
    )

    mock_pr_new_vhost.assert_called_with(
        fake_credentials['github'],
        fake_new_vhost_request.username,
        fake_new_vhost_request.aliases,
        fake_new_vhost_request.docroot,
        fake_new_vhost_request.flags,
        3,
    )


@pytest.yield_fixture
def mock_vhost_db():
    with mock.patch('ocflib.vhost.web.get_vhost_db') as m:
        yield m


@pytest.yield_fixture
def mock_uuid():
    with mock.patch('ocflib.vhost.web.uuid') as m:
        yield m


def test_pr_new_vhost(mock_uuid, mock_vhost_db, mock_gitrepo, fake_credentials):
    mock_vhost_db.return_value = ['']
    pr_new_vhost(
        fake_credentials,
        'ocf',
        aliases=['ocfweb'],
        docroot='/web',
        rt_ticket='1234',
    )

    expected_end_result = dedent("""
    # added {date} web rt#1234
    ocf ocfweb /web{space}

    """.format(
        date=date.today(),
        space=' ')
    )

    expected_branch_name = 'rt#1234-{}'.format(str(mock_uuid.uuid4.return_value.hex))

    mock_gitrepo.return_value.modify_and_branch.assert_called_with(
        'master',
        expected_branch_name,
        'rt#1234: Add vhost for ocf',
        GITHUB_VHOST_WEB_PATH,
        expected_end_result,
    )

    expected_pull_body = dedent("""
        Submitted from ocflib on {date}

        Username: ocf
        Aliases: ocfweb
        Document root: /web
        Flags:{space}

        Associated RT Ticket: rt#1234
        https://ocf.io/rt/1234
        """).format(
        date=date.today(),
        space=' ',
    )

    mock_gitrepo.return_value.github.create_pull.assert_called_with(
        title='rt#1234: Add vhost for ocf',
        body=expected_pull_body,
        base='master',
        head=expected_branch_name,
    )
