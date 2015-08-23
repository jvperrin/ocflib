from datetime import date
from datetime import datetime

import mock
import pytest
from freezegun import freeze_time

from ocflib.lab.hours import DayHours
from ocflib.lab.hours import get_hours
from ocflib.lab.hours import is_open


FAKE_HOLIDAYS = {
    (date(2015, 3, 14), date(2015, 3, 14), 'Pi Day', (None, None)),
    (date(2015, 3, 20), date(2015, 3, 22), 'Random 3 Days', (1, 2)),
}
FAKE_REGULAR_HOURS = {
    0: (9, 18),  # Monday
    1: (9, 18),  # Tuesday
    2: (9, 18),  # Wednesday
    3: (9, 18),  # Thursday
    4: (9, 18),  # Friday
    5: (11, 18),  # Saturday
    6: (12, 17),  # Sunday
}


@pytest.yield_fixture
def mock_hours():
    with mock.patch('ocflib.lab.hours.HOLIDAYS', FAKE_HOLIDAYS), \
            mock.patch('ocflib.lab.hours.REGULAR_HOURS', FAKE_REGULAR_HOURS):
        yield FAKE_HOLIDAYS, FAKE_REGULAR_HOURS


@pytest.yield_fixture
def mock_today():
    with freeze_time('2015-08-22 14:11:00'):
        yield


@pytest.mark.parametrize('now,expected_open', [
    # regular hours
    (datetime(2015, 3, 15, 12), True),
    (datetime(2015, 3, 19, 17), True),
    (datetime(2015, 3, 19, 9), True),
    (datetime(2015, 3, 19, 18), False),
    (datetime(2015, 3, 19, 0), False),
    (None, True),

    # holidays
    (datetime(2015, 3, 14, 12), False),
    (datetime(2015, 3, 14, 0), False),
    (datetime(2015, 3, 20, 0), False),
    (datetime(2015, 3, 20, 1), True),
    (datetime(2015, 3, 20, 1, 30), True),
    (datetime(2015, 3, 20, 1, 59), True),
    (datetime(2015, 3, 20, 2, 0), False),
])
def test_is_open(now, expected_open, mock_hours, mock_today):
    assert is_open(now) == expected_open


def test_is_open_fails_with_just_date():
    with pytest.raises(ValueError):
        is_open(date(2015, 3, 14))


class TestDayHours:

    @pytest.mark.parametrize('when,name,open,close', [
        (date(2015, 3, 15), 'Sunday', 12, 17),
        (datetime(2015, 3, 15), 'Sunday', 12, 17),
        (datetime(2015, 3, 18), 'Wednesday', 9, 18),
        (datetime(2015, 3, 14), 'Pi Day (Saturday)', None, None),
        (date(2015, 3, 22), 'Random 3 Days (Sunday)', 1, 2),
        (None, 'Saturday', 11, 18),
    ])
    def test_creation(self, mock_hours, mock_today, when, name, open, close):
        for day_hours in [DayHours.from_date(when), get_hours(when)]:
            assert day_hours.name == name
            assert day_hours.open == open
            assert day_hours.close == close
