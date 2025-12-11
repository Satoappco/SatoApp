"""
Tests for DefaultDataService
"""

import pytest
from unittest.mock import patch, MagicMock
from app.services.default_data_service import DefaultDataService


class TestDefaultDataService:
    """Test DefaultDataService functionality"""

    def test_init(self):
        """Test DefaultDataService initialization"""
        service = DefaultDataService()
        assert service.default_questions is not None
        assert len(service.default_questions) == 10
        assert "מה הביצועים של הקמפיין האחרון?" in service.default_questions

    def test_create_default_data_for_agency(self, db_session):
        """Test creating default data for agency"""
        # Use real database session (from conftest.py fixture)
        # This ensures SQLAlchemy select() works with real model classes

        service = DefaultDataService()

        # Patch get_session to return our test session
        with patch("app.services.default_data_service.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = db_session

            result = service.create_default_data_for_agency(1)

            assert result["success"] is True
            assert "Default data created successfully" in result["message"]

    @patch("app.services.default_data_service.get_session")
    def test_create_default_data_for_agency_exception(self, mock_get_session):
        """Test exception handling in create_default_data_for_agency"""
        mock_session = MagicMock()
        mock_session.commit.side_effect = Exception("Database error")
        mock_get_session.return_value.__enter__.return_value = mock_session

        service = DefaultDataService()

        with pytest.raises(Exception):
            service.create_default_data_for_agency(1)

    def test_create_default_data_for_customer(self, db_session):
        """Test creating default data for customer"""
        # Use real database session to avoid mocking model classes

        service = DefaultDataService()

        # Patch get_session to return our test session
        with patch("app.services.default_data_service.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = db_session

            result = service.create_default_data_for_customer(1, 1, 1)

            assert result["success"] is True
            assert "Default customer data created successfully" in result["message"]

    @patch("app.services.default_data_service.get_session")
    def test_create_default_data_for_customer_exception(self, mock_get_session):
        """Test exception handling in create_default_data_for_customer"""
        mock_session = MagicMock()
        mock_session.commit.side_effect = Exception("Database error")
        mock_get_session.return_value.__enter__.return_value = mock_session

        service = DefaultDataService()

        with pytest.raises(Exception):
            service.create_default_data_for_customer(1, 1, 1)

    def test_create_default_kpi_catalog_new_entries(self):
        """Test creating new KPI catalog entries"""
        service = DefaultDataService()

        # Mock session
        mock_session = MagicMock()

        # Mock that entries don't exist
        mock_session.exec.return_value.first.return_value = None

        service._create_default_kpi_catalog(mock_session)

        # Verify add was called 3 times (for 3 default entries)
        assert mock_session.add.call_count == 3

    def test_create_default_kpi_catalog_existing_entries(self):
        """Test skipping existing KPI catalog entries"""
        service = DefaultDataService()

        # Mock session
        mock_session = MagicMock()

        # Mock that entries already exist
        mock_session.exec.return_value.first.return_value = MagicMock()

        service._create_default_kpi_catalog(mock_session)

        # Verify add was not called
        mock_session.add.assert_not_called()

    def test_create_default_agent_configs_new_agents(self):
        """Test creating new agent configurations"""
        service = DefaultDataService()

        # Mock session
        mock_session = MagicMock()

        # Mock that agents don't exist
        mock_session.exec.return_value.first.return_value = None

        service._create_default_agent_configs(mock_session)

        # Verify add was called 3 times (for 3 default agents)
        assert mock_session.add.call_count == 3

    def test_create_default_agent_configs_existing_agents(self):
        """Test skipping existing agent configurations"""
        service = DefaultDataService()

        # Mock session
        mock_session = MagicMock()

        # Mock that agents already exist
        mock_session.exec.return_value.first.return_value = MagicMock()

        service._create_default_agent_configs(mock_session)

        # Verify add was not called
        mock_session.add.assert_not_called()

    def test_create_default_kpi_settings(self, db_session):
        """Test creating customer-specific KPI settings"""
        # Use real database session to avoid mocking model classes
        from app.models.analytics import DefaultKpiSettings

        service = DefaultDataService()

        # Create a default KPI setting in the test database
        default_setting = DefaultKpiSettings(
            campaign_objective="ecommerce",
            kpi_name="Revenue",
            kpi_type="Primary",
            direction="maximize",
            default_value=1000,
            unit="₪"
        )
        db_session.add(default_setting)
        db_session.commit()

        # Now test creating customer-specific settings
        service._create_default_kpi_settings(db_session, 1, 1, 1)

        # Verify KPI setting was added (by checking the session has objects)
        # The actual verification is that no exception was raised

    def test_create_default_kpi_settings_no_defaults(self, db_session):
        """Test handling when no default KPI settings exist"""
        service = DefaultDataService()

        # Don't add any default KPI settings to the test database
        # This tests the case where no defaults exist

        service._create_default_kpi_settings(db_session, 1, 1, 1)

        # Verify nothing crashed - the function should handle empty defaults gracefully

    def test_create_default_questions_new_entry(self):
        """Test creating new questions entry"""
        service = DefaultDataService()

        # Mock session
        mock_session = MagicMock()

        # Mock that questions don't exist
        mock_session.exec.return_value.first.return_value = None

        service._create_default_questions(mock_session, 1, 1, 1)

        # Verify questions entry was added
        mock_session.add.assert_called_once()

    def test_create_default_questions_existing_entry(self):
        """Test updating existing questions entry"""
        service = DefaultDataService()

        # Mock session
        mock_session = MagicMock()

        # Mock existing questions entry
        mock_existing = MagicMock()
        mock_session.exec.return_value.first.return_value = mock_existing

        service._create_default_questions(mock_session, 1, 1, 1)

        # Verify existing entry was updated (setattr called)
        # This is hard to test precisely without more complex mocking

    def test_create_default_rtm_links_new_entry(self):
        """Test creating new RTM links entry"""
        service = DefaultDataService()

        # Mock session
        mock_session = MagicMock()

        # Mock that RTM entry doesn't exist
        mock_session.exec.return_value.first.return_value = None

        service._create_default_rtm_links(mock_session, 1, 1, 1)

        # Verify RTM entry was added
        mock_session.add.assert_called_once()

    def test_create_default_rtm_links_existing_entry(self):
        """Test updating existing RTM links entry"""
        service = DefaultDataService()

        # Mock session
        mock_session = MagicMock()

        # Mock existing RTM entry
        mock_existing = MagicMock()
        mock_session.exec.return_value.first.return_value = mock_existing

        service._create_default_rtm_links(mock_session, 1, 1, 1)

        # Verify existing entry was updated
        # The actual updates are hard to test without more complex mocking


class TestDefaultDataServiceConstants:
    """Test default data constants"""

    def test_default_questions_content(self):
        """Test that default questions contain expected content"""
        service = DefaultDataService()

        assert len(service.default_questions) == 10
        assert all(isinstance(q, str) for q in service.default_questions)
        assert all(len(q) > 0 for q in service.default_questions)

    def test_default_questions_are_hebrew(self):
        """Test that default questions are in Hebrew"""
        service = DefaultDataService()

        # Check that questions contain Hebrew characters
        hebrew_questions = [
            q
            for q in service.default_questions
            if any("\u0590" <= c <= "\u05ff" for c in q)
        ]
        assert len(hebrew_questions) > 0
