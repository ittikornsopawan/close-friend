from close_friend_worker.tasks import ping


def test_ping_returns_payload() -> None:
    result = ping.run({"hello": "world"})
    assert result == "pong: {'hello': 'world'}"
