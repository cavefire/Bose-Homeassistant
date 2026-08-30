"""Tests for the Bose media player entity."""

from bose.media_player import BoseMediaPlayer


async def test_options_update_survives_a_failing_refresh():
    """A failed refresh must not become an unretrieved task exception.

    Token refreshes update the config entry, which fires this listener, and the
    speaker may reject the fresh token until its clock catches up (issue #78).
    """
    player = object.__new__(BoseMediaPlayer)
    player.entity_id = "media_player.test"
    player._load_linked_media_players = lambda: None  # noqa: SLF001
    player._setup_linked_player_listeners = lambda: None  # noqa: SLF001
    written = []
    player.async_write_ha_state = lambda: written.append(True)

    async def failing_update():
        raise ValueError(
            "'GET /content/nowPlaying' returned 401: JWT not before check failed"
        )

    player.async_update = failing_update

    # Must not raise, and the state write still happens.
    await player._async_options_updated(None, None)  # noqa: SLF001
    assert written
