import pytest

from flipperone._cli import strip_ansi
from flipperone.mcu import parsers
from replies import DEVICE_INFO, FREE, HELP, POWER_INFO


def test_strip_ansi_and_key_values():
    assert strip_ansi("\x1b[31mred\x1b[0m \x1b[1G\x1b[0K\x1b[?25l") == "red "
    info = parsers.key_values(DEVICE_INFO)
    assert info["rp2350_hardware_uid"] == "c5976c76a8d0974d" and len(info) == 12


def test_uptime_and_help():
    assert parsers.uptime_seconds("Uptime: 1h2m3s") == 3723
    with pytest.raises(ValueError):
        parsers.uptime_seconds("nothing")
    assert parsers.help_names(HELP)[:3] == ["expander_ext", "input", "uart_echo"]


def test_heap_stats_is_tolerant():
    heap = parsers.heap_stats(FREE)
    assert (heap.free, heap.total, heap.minimum, heap.max_block, heap.pool_free) == (131800, 496788, 131264, 129696, 0)
    older = parsers.heap_stats("Free heap size: 1\nTotal heap size: 2\nSomething new: 3")
    assert older.minimum is None and older.raw["Something new"] == "3"
    with pytest.raises(ValueError):
        parsers.heap_stats("nothing")


def test_power_info_is_tolerant():
    p = parsers.power_info(POWER_INFO)
    assert (p.state, p.battery_level, p.battery_voltage_mv, p.battery_ntc_c) == ("charged", 96, 8580, 29.6)
    assert p.charger_enabled is True and p.charger_temperature_c == 45.0 and p.raw["USB.current_limit"] == "1600 mA"
    partial = parsers.power_info("state : charging\nBAT.level : 50%")
    assert partial.battery_level == 50 and partial.usb_voltage_mv is None and partial.charger_enabled is None


def test_nvm_value_and_saradc():
    assert parsers.nvm_value("k: 5", "i", "k") == 5
    assert parsers.nvm_value("k: true", "b", "k") is True
    assert parsers.nvm_value("k: name", "s", "k") == "name"
    with pytest.raises(KeyError):
        parsers.nvm_value("Key k is missing", "u", "k")
    assert parsers.saradc_id("Current SARADC ID: 1") == 1


def test_input_event_lines():
    assert parsers.input_event("key: Power type: Short") == parsers.KeyEvent("Power", "Short")
    assert parsers.input_event("touch: Move x=400 y=300 p=900") == parsers.TouchEvent("Move", 400, 300, 900)
    assert parsers.input_event("touch: End x=65535 y=65535 p=0") == parsers.TouchEvent("End", None, None, 0)
    assert parsers.input_event("Press CTRL+C to stop") is None
