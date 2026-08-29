"""Tests for stream resolution: caching, spacing and challenge handling."""

import time
from unittest.mock import patch

import pytest

import wsr_live_capture as w


@pytest.fixture(autouse=True)
def clean_cache():
    w._cache.clear()
    yield
    w._cache.clear()


FAKE_INFO = {'formats': [
    {'format_id': '231', 'url': 'https://example/480p.m3u8'},
    {'format_id': '270', 'url': 'https://example/1080p.m3u8'},
]}


class FakeYDL:
    calls = 0

    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download=False):
        FakeYDL.calls += 1
        return FAKE_INFO


class TestCaching:
    def test_one_extraction_serves_every_rendition(self):
        FakeYDL.calls = 0
        with patch.object(w.yt_dlp, 'YoutubeDL', FakeYDL):
            low = w.resolve_hls_url('blue_anchor', '231')
            high = w.resolve_hls_url('blue_anchor', '270')
        assert FakeYDL.calls == 1, 'the second format must come from cache'
        assert low != high

    def test_cache_expires(self):
        FakeYDL.calls = 0
        with patch.object(w.yt_dlp, 'YoutubeDL', FakeYDL):
            w.resolve_hls_url('blue_anchor', '231')
            w._cache[w.CAMERAS['blue_anchor']] = (
                time.time() - w.CACHE_TTL_S - 1, {'231': 'stale'})
            w.resolve_hls_url('blue_anchor', '231')
        assert FakeYDL.calls == 2


class TestChallenge:
    def test_a_bot_challenge_is_raised_as_its_own_error(self):
        class Challenged(FakeYDL):
            def extract_info(self, url, download=False):
                raise RuntimeError(
                    'ERROR: [youtube] abc: Sign in to confirm you are not a bot.')

        with patch.object(w.yt_dlp, 'YoutubeDL', Challenged):
            with pytest.raises(w.BotChallenge) as caught:
                w.resolve_hls_url('blue_anchor', '231')
        # the message should tell the operator what to do about it
        assert 'WSR_COOKIES_FROM' in str(caught.value)

    def test_other_errors_are_not_disguised_as_challenges(self):
        class Broken(FakeYDL):
            def extract_info(self, url, download=False):
                raise RuntimeError('connection reset')

        with patch.object(w.yt_dlp, 'YoutubeDL', Broken):
            with pytest.raises(RuntimeError) as caught:
                w.resolve_hls_url('blue_anchor', '231')
        assert not isinstance(caught.value, w.BotChallenge)

    def test_challenge_detection_reads_the_real_message(self):
        assert w._looks_like_challenge(
            RuntimeError("Sign in to confirm you're not a bot"))
        assert not w._looks_like_challenge(RuntimeError('404 not found'))


class TestSpacing:
    def test_resolutions_are_spaced_apart(self):
        with patch.object(w.yt_dlp, 'YoutubeDL', FakeYDL), \
             patch.object(w, 'RESOLVE_SPACING_S', 0.3):
            w._last_resolve = 0.0
            started = time.time()
            w.resolve_hls_url('blue_anchor', '231')
            w.resolve_hls_url('minehead_station', '231')
            elapsed = time.time() - started
        # the second call must wait rather than pile straight in
        assert elapsed >= 0.3
