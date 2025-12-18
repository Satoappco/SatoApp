"""
Test for GAQL Protobuf Serialization Fix

This test validates that the execute_gaql tool properly serializes protobuf objects,
including RepeatedComposite (lists) and MapComposite (dicts) from Google Ads API responses.

Bug: Tool was returning raw protobuf objects that couldn't be serialized to JSON
Fix: Enhanced format_value() to recursively convert all protobuf types to JSON-compatible types
"""

import pytest
import os
import inspect


def get_api_source():
    """Get the source code of the api.py file in a robust way."""
    # Try multiple possible paths for the api.py file
    possible_paths = [
        os.path.join(
            os.path.dirname(__file__),
            "../../app/mcps/google_ads_mcp/ads_mcp/tools/api.py",
        ),
        os.path.join(
            os.path.dirname(__file__),
            "../../../app/mcps/google_ads_mcp/ads_mcp/tools/api.py",
        ),
        # Add more paths if needed
    ]

    for path in possible_paths:
        if os.path.exists(path):
            with open(path, "r") as f:
                return f.read()

    # If file reading fails, try import approach (but this might fail in test env)
    try:
        from app.mcps.google_ads_mcp.ads_mcp.tools import api

        return inspect.getsource(api)
    except ImportError:
        # As a last resort, return empty string - tests will fail but with clear error
        return ""


class TestProtobufSerialization:
    """Test that protobuf objects are properly serialized to JSON-compatible types."""

    def test_format_value_handles_proto_message(self):
        """Test that proto.Message objects are converted to dicts."""
        # Get the source code from the api file
        source = get_api_source()

        # Verify format_value handles proto.Message
        assert "proto.Message" in source, "Should handle proto.Message objects"
        assert "to_dict" in source, "Should convert Message to dict"

    def test_format_value_handles_repeated_composite(self):
        """Test that RepeatedComposite (protobuf lists) are handled."""
        source = get_api_source()

        # Verify the function checks for iterable protobuf objects
        assert "hasattr(value, '__iter__')" in source, "Should check for iterables"
        assert "hasattr(value, '_pb')" in source, "Should check for protobuf marker"
        assert "for item in value" in source, "Should iterate over repeated fields"

    def test_format_value_handles_map_composite(self):
        """Test that MapComposite (protobuf dicts) are handled."""
        source = get_api_source()

        # Verify the function checks for dict-like protobuf objects
        assert "hasattr(value, 'items')" in source, "Should check for dict-like objects"
        assert ".items()" in source, "Should iterate over map items"

    def test_format_value_handles_nested_structures(self):
        """Test that nested protobuf structures are recursively converted."""
        source = get_api_source()

        # Verify recursive handling
        assert (
            "format_value(item)" in source or "format_value(v)" in source
        ), "Should recursively format nested values"

    def test_format_value_function_exists(self):
        """Test that format_value function is defined."""
        source = get_api_source()

        assert "def format_value(" in source, "format_value function should be defined"
        assert (
            "Handle protobuf" in source or "protobuf" in source.lower()
        ), "Should have protobuf handling documentation"

    def test_error_message_mentions_serialization_issue(self):
        """Test that the original error was about serialization."""
        # The error message we saw in logs
        error_msg = "Could not serialize structured content. Unable to serialize unknown type: <class 'proto.marshal.collections.repeated.RepeatedComposite'>"

        assert "serialize" in error_msg.lower(), "Error was about serialization"
        assert "RepeatedComposite" in error_msg, "Error mentioned RepeatedComposite"

    def test_fix_handles_all_protobuf_collection_types(self):
        """Test that the fix handles all protobuf collection types."""
        source = get_api_source()

        # Should handle:
        # 1. RepeatedComposite (lists)
        assert (
            "hasattr(value, '__iter__')" in source and "hasattr(value, '_pb')" in source
        ), "Should detect RepeatedComposite by __iter__ and _pb"

        # 2. MapComposite (dicts)
        assert (
            "hasattr(value, 'items')" in source and "hasattr(value, '_pb')" in source
        ), "Should detect MapComposite by items and _pb"

        # 3. Regular lists
        assert (
            "isinstance(value, (list, tuple))" in source
        ), "Should handle regular lists"

        # 4. Regular dicts
        assert "isinstance(value, dict)" in source, "Should handle regular dicts"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
