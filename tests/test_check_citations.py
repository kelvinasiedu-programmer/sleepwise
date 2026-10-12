import pytest

from scripts.check_citations import classify


@pytest.mark.parametrize("status", [200, 204, 301, 304])
def test_success_and_redirect_statuses_are_ok(status):
    assert classify(status) == "ok"


@pytest.mark.parametrize("status", [401, 403, 429])
def test_host_refusing_the_checker_is_blocked_not_broken(status):
    # NIH ODS answers scripted clients with a Cloudflare 403 for pages that load in a browser.
    assert classify(status) == "blocked"


@pytest.mark.parametrize("status", [404, 410, 500, 503])
def test_missing_or_erroring_pages_are_broken(status):
    assert classify(status) == "broken"
