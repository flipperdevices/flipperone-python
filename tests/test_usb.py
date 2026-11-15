from flipperone.transport.usb import _bcd_sysfs, bcd_from_ioreg_plist, bcd_from_text, bcd_text

IOREG = [{
    "IORegistryEntryName": "Root",
    "IORegistryEntryChildren": [
        {"IORegistryEntryName": "USB3.0 Hub", "locationID": 0x02140000, "USB Address": 3, "bcdUSB": 0x0300,
         "IORegistryEntryChildren": [
             {"IORegistryEntryName": "USB download gadget", "locationID": 0x02144110, "USB Address": 15,
              "bcdUSB": 0x0200, "idVendor": 0x2207, "idProduct": 0x350E},
         ]},
        {"IORegistryEntryName": "Other", "locationID": 0x01100000, "USB Address": 15, "bcdUSB": 0x0210},
    ],
}]


def test_bcd_text_round_trip():
    assert bcd_text(0x0200) == "2.00" and bcd_text(0x0201) == "2.01" and bcd_text(0x0310) == "3.10"
    assert bcd_from_text(" 2.01\n") == 0x0201 and bcd_from_text("3.10") == 0x0310


def test_bcd_from_ioreg_matches_bus_from_location_and_address():
    assert bcd_from_ioreg_plist(IOREG, 2, 15) == 0x0200
    assert bcd_from_ioreg_plist(IOREG, 1, 15) == 0x0210
    assert bcd_from_ioreg_plist(IOREG, 2, 99) is None


def test_bcd_from_sysfs(tmp_path):
    dev = tmp_path / "2-1.4"
    dev.mkdir()
    (dev / "busnum").write_text("2\n")
    (dev / "devnum").write_text("15\n")
    (dev / "version").write_text(" 2.01\n")
    (tmp_path / "usb2").mkdir()  # a root hub dir without the files must not break the scan
    assert _bcd_sysfs(2, 15, tmp_path) == 0x0201
    assert _bcd_sysfs(2, 16, tmp_path) is None
    assert _bcd_sysfs(2, 15, tmp_path / "missing") is None
