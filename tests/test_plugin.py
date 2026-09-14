"""Tests for the crypto plugin."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from plugins.crypto import (
    CryptoPlugin,
    Plugin,
    coin_name,
    coin_symbol,
    format_change,
    format_price,
    parse_coins,
)


MANIFEST = {
    "id": "crypto",
    "name": "Crypto Prices",
    "version": "1.0.0",
    "settings_schema": {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean", "default": False},
            "refresh_seconds": {
                "type": "integer",
                "default": 300,
                "minimum": 60,
                "maximum": 3600,
            },
        },
    },
}

THREE_COINS = {
    "bitcoin": {"usd": 77679, "usd_24h_change": 0.6084841503114448},
    "ethereum": {"usd": 2512.67, "usd_24h_change": -0.27796600699265583},
    "solana": {"usd": 84.1, "usd_24h_change": 2.13},
}


def mock_response(payload, status_code=200):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status = Mock()
    return response


@pytest.fixture
def plugin():
    p = CryptoPlugin(MANIFEST)
    p._config = {"coins": "bitcoin,ethereum,solana", "currency": "usd"}
    return p


class TestCryptoPlugin:
    def test_plugin_id(self, plugin):
        assert plugin.plugin_id == "crypto"
        assert Plugin is CryptoPlugin

    @patch("plugins.crypto.requests.get")
    def test_fetch_data_success_three_coins(self, mock_get, plugin):
        mock_get.return_value = mock_response(THREE_COINS)

        result = plugin.fetch_data()

        assert result.available is True
        assert result.error is None
        assert result.data["count"] == 3
        assert [c["symbol"] for c in result.data["coins"]] == ["BTC", "ETH", "SOL"]

        btc = result.data["coins"][0]
        assert btc["id"] == "bitcoin"
        assert btc["name"] == "Bitcoin"
        assert btc["price"] == "77,679"
        assert btc["change_24h"] == "+0.6"
        assert btc["change_sign"] == "+"
        assert btc["formatted"] == "BTC      77,679  +0.6%"
        assert len(btc["formatted"]) == 22

        eth = result.data["coins"][1]
        assert eth["price"] == "2,513"
        assert eth["change_24h"] == "-0.3"
        assert eth["change_sign"] == "-"

        # Primary (first coin) fields mirror the first array item
        assert result.data["symbol"] == "BTC"
        assert result.data["price"] == "77,679"
        assert result.data["change_24h"] == "+0.6"
        assert result.data["formatted"] == btc["formatted"]

    @patch("plugins.crypto.requests.get")
    def test_fetch_data_returns_all_declared_variables(self, mock_get, plugin):
        mock_get.return_value = mock_response(THREE_COINS)

        result = plugin.fetch_data()

        manifest = json.loads((Path(__file__).parent.parent / "manifest.json").read_text())
        for var in manifest["variables"]["simple"]:
            assert var in result.data, f"Variable '{var}' declared in manifest but not in data"
        for arr_name, spec in manifest["variables"]["arrays"].items():
            assert arr_name in result.data
            for item in result.data[arr_name]:
                for field in spec["item_fields"]:
                    assert field in item, f"Array field '{field}' missing from item"
        # And vice versa: nothing undeclared
        declared = set(manifest["variables"]["simple"]) | set(manifest["variables"]["arrays"])
        assert set(result.data) == declared

    @patch("plugins.crypto.requests.get")
    def test_fetch_data_sends_params_and_headers(self, mock_get, plugin):
        mock_get.return_value = mock_response(THREE_COINS)
        plugin._config["api_key"] = "CG-secret"
        plugin._config["currency"] = "EUR"

        plugin.fetch_data()

        mock_get.assert_called_once()
        kwargs = mock_get.call_args.kwargs
        assert kwargs["params"]["ids"] == "bitcoin,ethereum,solana"
        assert kwargs["params"]["vs_currencies"] == "eur"
        assert kwargs["params"]["include_24hr_change"] == "true"
        assert kwargs["headers"]["x-cg-demo-api-key"] == "CG-secret"
        assert "User-Agent" in kwargs["headers"]
        assert kwargs["timeout"] == 10

    @patch("plugins.crypto.requests.get")
    def test_no_api_key_header_when_unset(self, mock_get, plugin):
        mock_get.return_value = mock_response(THREE_COINS)

        plugin.fetch_data()

        assert "x-cg-demo-api-key" not in mock_get.call_args.kwargs["headers"]

    @patch("plugins.crypto.requests.get")
    def test_unknown_coin_ids_are_skipped(self, mock_get, plugin):
        plugin._config["coins"] = "bitcoin,notarealcoin,ethereum"
        # CoinGecko silently omits unknown ids from the response
        mock_get.return_value = mock_response(
            {k: v for k, v in THREE_COINS.items() if k != "solana"}
        )

        result = plugin.fetch_data()

        assert result.available is True
        assert result.data["count"] == 2
        assert [c["id"] for c in result.data["coins"]] == ["bitcoin", "ethereum"]

    @patch("plugins.crypto.requests.get")
    def test_all_coins_unknown(self, mock_get, plugin):
        plugin._config["coins"] = "notarealcoin"
        mock_get.return_value = mock_response({})

        result = plugin.fetch_data()

        assert result.available is False
        assert "No price data" in result.error

    @patch("plugins.crypto.requests.get")
    def test_http_429_rate_limit(self, mock_get, plugin):
        mock_get.return_value = mock_response({"status": {"error_code": 429}}, status_code=429)

        result = plugin.fetch_data()

        assert result.available is False
        assert "429" in result.error

    @patch("plugins.crypto.requests.get")
    def test_http_error(self, mock_get, plugin):
        response = mock_response(None, status_code=500)
        response.raise_for_status.side_effect = Exception("HTTP 500")
        mock_get.return_value = response

        result = plugin.fetch_data()

        assert result.available is False
        assert "HTTP 500" in result.error

    @patch("plugins.crypto.requests.get")
    def test_network_error(self, mock_get, plugin):
        mock_get.side_effect = Exception("Connection timed out")

        result = plugin.fetch_data()

        assert result.available is False
        assert "Connection timed out" in result.error

    @patch("plugins.crypto.requests.get")
    def test_malformed_response(self, mock_get, plugin):
        mock_get.return_value = mock_response(["not", "a", "dict"])

        result = plugin.fetch_data()

        assert result.available is False
        assert "Malformed" in result.error

    @patch("plugins.crypto.requests.get")
    def test_missing_currency_or_change_fields(self, mock_get, plugin):
        mock_get.return_value = mock_response({
            "bitcoin": {"usd": 77679},  # no 24h change -> treated as 0
            "ethereum": {"eur": 2300},  # wrong currency -> skipped
            "solana": "garbage",  # not a dict -> skipped
        })

        result = plugin.fetch_data()

        assert result.available is True
        assert result.data["count"] == 1
        assert result.data["coins"][0]["change_24h"] == "+0.0"
        assert result.data["coins"][0]["change_sign"] == "+"

    @patch("plugins.crypto.requests.get")
    def test_no_coins_configured(self, mock_get, plugin):
        plugin._config["coins"] = "  ,  "

        result = plugin.fetch_data()

        assert result.available is False
        mock_get.assert_not_called()

    @patch("plugins.crypto.requests.get")
    def test_get_formatted_display(self, mock_get, plugin):
        mock_get.return_value = mock_response(THREE_COINS)

        lines = plugin.get_formatted_display()

        assert lines is not None
        assert len(lines) == 6
        assert all(len(line) <= 22 for line in lines)
        assert lines[0].strip() == "CRYPTO"
        assert lines[1] == "BTC      77,679  +0.6%"
        assert lines[2].startswith("ETH")
        assert lines[3].startswith("SOL")
        assert lines[4] == "" and lines[5] == ""

    @patch("plugins.crypto.requests.get")
    def test_get_formatted_display_note_board(self, mock_get, plugin):
        mock_get.return_value = mock_response(THREE_COINS)
        board = Mock(rows=3, cols=15, device_type="note")

        with plugin._bound_board(board):
            lines = plugin.get_formatted_display()

        assert len(lines) == 3
        assert all(len(line) <= 15 for line in lines)
        assert lines[1] == "BTC      77,679"

    @patch("plugins.crypto.requests.get")
    def test_get_formatted_display_returns_none_on_error(self, mock_get, plugin):
        mock_get.side_effect = Exception("Network error")

        assert plugin.get_formatted_display() is None


class TestValidateConfig:
    def test_valid(self, plugin):
        assert plugin.validate_config({"coins": "bitcoin, ethereum", "currency": "usd"}) == []

    def test_defaults_are_valid(self, plugin):
        assert plugin.validate_config({}) == []

    def test_rejects_empty_coins(self, plugin):
        errors = plugin.validate_config({"coins": ""})
        assert any("At least one coin" in e for e in errors)

    def test_rejects_more_than_ten_coins(self, plugin):
        coins = ",".join(f"coin{i}" for i in range(11))
        errors = plugin.validate_config({"coins": coins})
        assert any("Maximum 10" in e for e in errors)

    def test_accepts_exactly_ten_coins(self, plugin):
        coins = ",".join(f"coin{i}" for i in range(10))
        assert plugin.validate_config({"coins": coins}) == []

    def test_rejects_bad_currency(self, plugin):
        assert plugin.validate_config({"coins": "bitcoin", "currency": "dollars"})
        assert plugin.validate_config({"coins": "bitcoin", "currency": "us"})
        assert plugin.validate_config({"coins": "bitcoin", "currency": "u$d"})


class TestFormatting:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (77679, "77,679"),
            (1234567.89, "1,234,568"),
            (1000, "1,000"),
            (999.999, "1000.00"),
            (2512.67, "2,513"),
            (84.1, "84.10"),
            (1, "1.00"),
            (0.1234, "0.1234"),
            (0.9999, "0.9999"),
            (0.08765, "0.08765"),
            (0.00001234, "0.00001234"),
            (0.000000001234, "0.00000000"),
            (0, "0.00"),
        ],
    )
    def test_format_price(self, value, expected):
        assert format_price(value) == expected

    @pytest.mark.parametrize(
        "value,expected",
        [(1.2, "+1.2"), (-0.8, "-0.8"), (0, "+0.0"), (12.345, "+12.3"), (-100, "-100.0")],
    )
    def test_format_change(self, value, expected):
        assert format_change(value) == expected

    def test_known_symbols(self):
        assert coin_symbol("bitcoin") == "BTC"
        assert coin_symbol("avalanche-2") == "AVAX"
        assert coin_symbol("ripple") == "XRP"

    def test_unknown_symbol_uses_first_four_letters(self):
        assert coin_symbol("shiba-inu") == "SHIB"
        assert coin_symbol("binancecoin") == "BINA"
        assert coin_symbol("ab") == "AB"

    def test_coin_name(self):
        assert coin_name("bitcoin") == "Bitcoin"
        assert coin_name("avalanche-2") == "Avalanche"
        assert coin_name("shiba-inu") == "Shiba Inu"

    def test_parse_coins(self):
        assert parse_coins(" Bitcoin , ethereum,,solana ") == ["bitcoin", "ethereum", "solana"]
        assert parse_coins("") == []
        assert parse_coins(None) == []
        assert parse_coins(["bitcoin"]) == []


class TestManifestMetadata:
    @pytest.fixture
    def manifest(self):
        return json.loads((Path(__file__).parent.parent / "manifest.json").read_text())

    def test_all_variables_have_descriptions_and_groups(self, manifest):
        groups = set(manifest["variables"]["groups"])
        for name, meta in manifest["variables"]["simple"].items():
            assert meta.get("description"), f"{name} missing description"
            assert meta["group"] in groups, f"{name} has undefined group"

    def test_previews_fit_boards(self, manifest):
        for preview in manifest["previews"]:
            width = 22 if preview["device_type"] == "flagship" else 15
            for row in preview["rows"]:
                assert len(row) <= width
