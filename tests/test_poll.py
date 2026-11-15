from flipperone._poll import wait_until


def test_returns_first_truthy_result_and_polls_in_between():
    results = iter([None, [], 0, "found"])
    slept = []
    assert wait_until(lambda: next(results), poll=0.25, sleep=slept.append) == "found"
    assert slept == [0.25, 0.25, 0.25]


def test_times_out():
    now = [0.0]

    def sleep(s):
        now[0] += s

    assert wait_until(lambda: None, timeout=2.5, poll=1.0, sleep=sleep, clock=lambda: now[0]) is None
    assert now[0] == 3.0


def test_immediate_hit_does_not_sleep():
    slept = []
    assert wait_until(lambda: 42, timeout=0, sleep=slept.append) == 42
    assert slept == []
