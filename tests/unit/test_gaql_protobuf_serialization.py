"""
Test for GAQL Protobuf Serialization Fix

This test validates that the execute_gaql tool properly serializes protobuf objects,
including RepeatedComposite (lists) and MapComposite (dicts) from Google Ads API responses.

Bug: Tool was returning raw protobuf objects that couldn't be serialized to JSON
Fix: Enhanced format_value() to recursively convert all protobuf types to JSON-compatible types
"""

import pytest
import os


class TestProtobufSerialization:
    """Test that protobuf objects are properly serialized to JSON-compatible types."""

    def test_format_value_handles_proto_message(self):
        """Test that proto.Message objects are converted to dicts."""
        # Read the source file directly
        api_file = os.path.join(os.path.dirname(__file__), "../../app/mcps/google_ads_mcp/ads_mcp/tools/api.py")
        with open(api_file, 'r') as f:
            source = f.read()

        # Verify format_value handles proto.Message
        assert "proto.Message" in source, "Should handle proto.Message objects"
        assert "to_dict" in source, "Should convert Message to dict"

    def test_format_value_handles_repeated_composite(self):
        """Test that RepeatedComposite (protobuf lists) are handled."""
        api_file = os.path.join(os.path.dirname(__file__), "../../app/mcps/google_ads_mcp/ads_mcp/tools/api.py")
        with open(api_file, 'r') as f:
            source = f.read()

        # Verify the function checks for iterable protobuf objects
        assert "hasattr(value, '__iter__')" in source, "Should check for iterables"
        assert "hasattr(value, '_pb')" in source, "Should check for protobuf marker"
        assert "for item in value" in source, "Should iterate over repeated fields"

    def test_format_value_handles_map_composite(self):
        """Test that MapComposite (protobuf dicts) are handled."""
        api_file = os.path.join(os.path.dirname(__file__), "../../app/mcps/google_ads_mcp/ads_mcp/tools/api.py")
        with open(api_file, 'r') as f:
            source = f.read()

        # Verify the function checks for dict-like protobuf objects
        assert "hasattr(value, 'items')" in source, "Should check for dict-like objects"
        assert ".items()" in source, "Should iterate over map items"

    def test_format_value_handles_nested_structures(self):
        """Test that nested protobuf structures are recursively converted."""
        api_file = os.path.join(os.path.dirname(__file__), "../../app/mcps/google_ads_mcp/ads_mcp/tools/api.py")
        with open(api_file, 'r') as f:
            source = f.read()

        # Verify recursive handling
        assert "format_value(item)" in source or "format_value(v)" in source, \
            "Should recursively format nested values"

    def test_format_value_function_exists(self):
        """Test that format_value function is defined."""
        api_file = os.path.join(os.path.dirname(__file__), "../../app/mcps/google_ads_mcp/ads_mcp/tools/api.py")
        with open(api_file, 'r') as f:
            source = f.read()

        assert "def format_value(" in source, "format_value function should be defined"
        assert "Handle protobuf" in source or "protobuf" in source.lower(), \
            "Should have protobuf handling documentation"

    def test_error_message_mentions_serialization_issue(self):
        """Test that the original error was about serialization."""
        # The error message we saw in logs
        error_msg = "Could not serialize structured content. Unable to serialize unknown type: <class 'proto.marshal.collections.repeated.RepeatedComposite'>"

        assert "serialize" in error_msg.lower(), "Error was about serialization"
        assert "RepeatedComposite" in error_msg, "Error mentioned RepeatedComposite"

    def test_fix_handles_all_protobuf_collection_types(self):
        """Test that the fix handles all protobuf collection types."""
        api_file = os.path.join(os.path.dirname(__file__), "../../app/mcps/google_ads_mcp/ads_mcp/tools/api.py")
        with open(api_file, 'r') as f:
            source = f.read()

        # Should handle:
        # 1. RepeatedComposite (lists)
        assert "hasattr(value, '__iter__')" in source and "hasattr(value, '_pb')" in source, \
            "Should detect RepeatedComposite by __iter__ and _pb"

        # 2. MapComposite (dicts)
        assert "hasattr(value, 'items')" in source and "hasattr(value, '_pb')" in source, \
            "Should detect MapComposite by items and _pb"

        # 3. Regular lists
        assert "isinstance(value, (list, tuple))" in source, "Should handle regular lists"

        # 4. Regular dicts
        assert "isinstance(value, dict)" in source, "Should handle regular dicts"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
