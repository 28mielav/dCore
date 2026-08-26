from __future__ import annotations

import unittest
from pathlib import Path


class OpenApiContractTests(unittest.TestCase):
    def test_private_bridge_declares_bearer_auth_for_every_private_operation(self) -> None:
        text = (Path(__file__).resolve().parents[1] / "integrations" / "custom-gpt" / "openapi.yaml").read_text(encoding="utf-8")
        self.assertIn("securitySchemes:", text)
        self.assertIn("bearerAuth:", text)
        self.assertEqual(text.count("- bearerAuth: []"), 2)
        self.assertIn('"401":', text)


if __name__ == "__main__":
    unittest.main()
