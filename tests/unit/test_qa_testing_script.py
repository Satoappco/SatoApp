# """
# Unit tests for QA Testing Script
# """

# import pytest
# import pandas as pd
# from unittest.mock import Mock, patch, AsyncMock
# import sys
# import os
# from pathlib import Path

# # Add parent directory to path for imports
# sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# from scripts.qa_testing_script import QATestingScript


# class TestQATestingScript:
#     """Test cases for QATestingScript class."""

#     def test_is_google_sheets_url(self):
#         """Test Google Sheets URL detection."""
#         script = QATestingScript(sheet_url="dummy")

#         # Test Google Sheets URLs
#         assert script._is_google_sheets_url(
#             "https://docs.google.com/spreadsheets/d/123/edit"
#         )
#         assert script._is_google_sheets_url(
#             "https://docs.google.com/spreadsheets/d/123/edit?gid=456"
#         )

#         # Test non-Google Sheets URLs
#         assert not script._is_google_sheets_url("/path/to/file.xlsx")
#         assert not script._is_google_sheets_url("file.xlsx")
#         assert not script._is_google_sheets_url("https://example.com")

#     def test_extract_sheet_id_and_gid(self):
#         """Test extraction of sheet ID and GID from Google Sheets URL."""
#         script = QATestingScript(sheet_url="dummy")

#         # Test with GID
#         url = "https://docs.google.com/spreadsheets/d/1Trpy3H_VvfZfHPky-f47ilwU714kmrem2kWETibECeM/edit?gid=2126514740"
#         sheet_id, gid = script._extract_sheet_id_and_gid(url)
#         assert sheet_id == "1Trpy3H_VvfZfHPky-f47ilwU714kmrem2kWETibECeM"
#         assert gid == "2126514740"

#         # Test without GID (should default to '0')
#         url = "https://docs.google.com/spreadsheets/d/1Trpy3H_VvfZfHPky-f47ilwU714kmrem2kWETibECeM/edit"
#         sheet_id, gid = script._extract_sheet_id_and_gid(url)
#         assert sheet_id == "1Trpy3H_VvfZfHPky-f47ilwU714kmrem2kWETibECeM"
#         assert gid == "0"

#     def test_extract_sheet_id_invalid_url(self):
#         """Test extraction with invalid URL."""
#         script = QATestingScript(sheet_url="dummy")

#         with pytest.raises(ValueError, match="Invalid Google Sheets URL"):
#             script._extract_sheet_id_and_gid("https://example.com")

#     @patch("scripts.qa_testing_script.ServiceAccountCredentials")
#     @patch("scripts.qa_testing_script.gspread")
#     @patch("scripts.qa_testing_script.GSHEETS_AVAILABLE", True)
#     def test_load_google_sheets(self, mock_gspread, mock_creds):
#         """Test loading data from Google Sheets."""
#         # Mock the settings
#         mock_settings = Mock()
#         mock_settings.google_sheets_service_account_path = "/path/to/creds.json"

#         # Create test data
#         test_data = [
#             {"Type": "A", "Question": "Q1", "Expected Answer": "A1"},
#             {"Type": "A", "Question": "Q2", "Expected Answer": "A2"},
#         ]

#         # Mock gspread components
#         mock_client = Mock()
#         mock_spreadsheet = Mock()
#         mock_worksheet = Mock()
#         mock_worksheet.get_all_records.return_value = test_data

#         mock_gspread.authorize.return_value = mock_client
#         mock_client.open_by_key.return_value = mock_spreadsheet
#         mock_spreadsheet.get_worksheet_by_id.return_value = mock_worksheet

#         script = QATestingScript(
#             sheet_url="https://docs.google.com/spreadsheets/d/123/edit?gid=456",
#             jwt_token="test_token",
#         )
#         script.settings = mock_settings

#         df = script._load_google_sheets()

#         assert len(df) == 2
#         assert df.iloc[0]["Question"] == "Q1"
#         assert df.iloc[1]["Question"] == "Q2"

#     def test_load_excel(self, tmp_path):
#         """Test loading data from Excel file."""
#         # Create test Excel file
#         test_data = {
#             "Type": ["A", "B"],
#             "Question": ["Q1", "Q2"],
#             "Expected Answer": ["A1", "A2"],
#         }
#         df_test = pd.DataFrame(test_data)
#         excel_path = tmp_path / "test.xlsx"
#         df_test.to_excel(excel_path, index=False)

#         script = QATestingScript(sheet_url=str(excel_path), jwt_token="test_token")
#         df = script._load_excel()

#         assert len(df) == 2
#         assert df.iloc[0]["Question"] == "Q1"
#         assert df.iloc[1]["Question"] == "Q2"

#     def test_move_current_to_previous(self):
#         """Test moving current answers to previous column."""
#         test_data = {
#             "Question": ["Q1", "Q2"],
#             "Current Answer": ["C1", "C2"],
#             "Previous Answer": ["", ""],
#         }
#         df = pd.DataFrame(test_data)

#         script = QATestingScript(sheet_url="dummy", jwt_token="test_token")
#         result_df = script.move_current_to_previous(df)

#         assert result_df.iloc[0]["Previous Answer"] == "C1"
#         assert result_df.iloc[1]["Previous Answer"] == "C2"
#         assert result_df.iloc[0]["Current Answer"] == ""
#         assert result_df.iloc[1]["Current Answer"] == ""

#     @pytest.mark.asyncio
#     async def test_process_test_cases_fail_fast_enabled(self):
#         """Test fail-fast behavior when enabled."""
#         # Create test data with groups (3 questions in Group1, 1 in Group2)
#         test_data = {
#             "Type": ["Group1", "Group1", "Group1", "Group2"],
#             "Question": ["Q1", "Q2", "Q3", "Q4"],
#             "Expected Answer": ["A1", "A2", "A3", "A4"],
#             "Current Answer": ["", "", "", ""],
#             "Previous Answer": ["", "", "", ""],
#             "Rank": ["", "", "", ""],
#             "Suggestion": ["", "", "", ""],
#         }
#         df = pd.DataFrame(test_data)

#         script = QATestingScript(
#             sheet_url="dummy", jwt_token="test_token", fail_fast=True
#         )

#         # Mock the API call and ranking
#         with (
#             patch.object(script, "call_chat_api", new_callable=AsyncMock) as mock_api,
#             patch.object(script, "rank_with_llm", new_callable=AsyncMock) as mock_rank,
#             patch.object(script, "save_data") as mock_save,
#         ):
#             # First question succeeds, second fails (both bad), third should be skipped (same group)
#             mock_api.return_value = {"message": "Response"}
#             mock_rank.side_effect = [
#                 {"rank": "both good", "suggestion": "Good"},
#                 {"rank": "both bad", "suggestion": "Bad"},
#                 {"rank": "both good", "suggestion": "Good"},  # Q4 from Group2
#             ]

#             result_df = await script.process_test_cases(df, start_row=0, end_row=4)

#             # Should have called rank 3 times: Q1 (good), Q2 (bad), skip Q3, process Q4
#             assert mock_rank.call_count == 3

#             # Check that first question was processed
#             assert result_df.iloc[0]["Rank"] == "both good"
#             # Check that second question was processed and failed
#             assert result_df.iloc[1]["Rank"] == "both bad"
#             # Third should be skipped (same group as failed question)
#             assert result_df.iloc[2]["Rank"] == ""
#             # Fourth should be processed (different group)
#             assert result_df.iloc[3]["Rank"] == "both good"

#     @pytest.mark.asyncio
#     async def test_process_test_cases_fail_fast_disabled(self):
#         """Test processing all questions when fail-fast is disabled."""
#         # Create test data
#         test_data = {
#             "Type": ["Group1", "Group1"],
#             "Question": ["Q1", "Q2"],
#             "Expected Answer": ["A1", "A2"],
#             "Current Answer": ["", ""],
#             "Previous Answer": ["", ""],
#             "Rank": ["", ""],
#             "Suggestion": ["", ""],
#         }
#         df = pd.DataFrame(test_data)

#         script = QATestingScript(
#             sheet_url="dummy", jwt_token="test_token", fail_fast=False
#         )

#         # Mock the API call and ranking
#         with (
#             patch.object(script, "call_chat_api", new_callable=AsyncMock) as mock_api,
#             patch.object(script, "rank_with_llm", new_callable=AsyncMock) as mock_rank,
#             patch.object(script, "save_data") as mock_save,
#         ):
#             mock_api.return_value = {"message": "Response"}
#             mock_rank.side_effect = [
#                 {"rank": "both bad", "suggestion": "Bad"},
#                 {"rank": "both good", "suggestion": "Good"},
#             ]

#             result_df = await script.process_test_cases(df, start_row=0, end_row=2)

#             # Should have called rank for all questions
#             assert mock_rank.call_count == 2
#             assert result_df.iloc[0]["Rank"] == "both bad"
#             assert result_df.iloc[1]["Rank"] == "both good"
