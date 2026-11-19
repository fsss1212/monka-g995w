from copy import deepcopy
import unittest

from monka import protocol as p
from monka.device import decode


class ProtocolTests(unittest.TestCase):
    def test_marvo_factory_vectors(self):
        expected = (
            "04380100003f00000f1f3f5f9f070000000000000002000002ff000000ff000000ffffff0000ffffff00ffff4000ffffff010ee900000000",
            "050f015003080000ff0100015b0000",
            "06090101fe00000000",
            "083b010200000300000400000d00003c00000f00000600000500000100000100000100000100000100000100000100000100000a00000900000087",
        )
        reports = [reports[0].hex() for _, reports in p.packets(p.defaults())]
        self.assertEqual(reports, list(expected))

    def test_dpi_flags_and_16_bit_boundary(self):
        sensor = deepcopy(p.defaults()["sensor"])
        sensor["dpi"][1] = 12850
        sensor["enabled"][0] = False
        packet = p.sensor_report(sensor)
        self.assertEqual(packet[5], 62)
        self.assertEqual(packet[9], 0)
        self.assertEqual(packet[17], 1)
        self.assertEqual(int.from_bytes(packet[50:52], "big"), sum(packet[3:50]))
        sensor["stage"] = 1
        with self.assertRaises(ValueError):
            p.sensor_report(sensor)

    def test_switch_polling_rates(self):
        for rate, wire_value in p.RATES.items():
            self.assertEqual(p.polling_report(rate),
                             bytes((6, 9, 1, wire_value, wire_value ^ 255, 0, 0, 0, 0)))
        with self.assertRaises(ValueError):
            p.polling_report(2000)

    def test_macro_fragments_and_button_binding(self):
        profile = p.defaults()
        profile["macros"]["A"] = {"mode": 2, "repeat": 3,
                                  "events": [("a", "down", 10), ("a", "up", 2000)]}
        profile["buttons"][-1] = {"action": "Макрос", "arg": "A"}
        first, second, last, buttons = p.button_reports(profile["buttons"], profile["macros"])
        self.assertEqual(list(map(len, (first, second, last, buttons))), [64, 64, 64, 59])
        self.assertEqual((first[:4], second[:4], last[:4]),
                         tuple(bytes((9, 12 if i == 2 else 64, 1, i)) for i in range(3)))
        self.assertEqual(first[4:9], bytes((2, 0, 0, 0, 3)))
        self.assertEqual(first[29:36], bytes((3, 1, 4, 129, 4, 10, 3)))
        self.assertEqual(buttons[24:27], bytes((18, 0, 1)))

    def test_keep_left_click(self):
        profile = p.defaults()
        profile["buttons"][0]["action"] = "Выкл."
        with self.assertRaises(ValueError):
            p.validate(profile)

    def test_receiver_notifications(self):
        self.assertEqual(decode(bytes.fromhex("03 10 40 01 08")), ("battery", (90, True)))
        self.assertEqual(decode(bytes.fromhex("03 10 50 00 06")), ("ack", (0, 6)))
        self.assertEqual(decode(bytes.fromhex("03 00 10 02 00")), ("stage", 2))
        self.assertIsNone(decode(bytes.fromhex("03 10 ff ff fe")))
        self.assertIsNone(decode(bytes.fromhex("03 10 50")))


if __name__ == "__main__":
    unittest.main()
