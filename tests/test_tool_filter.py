import pytest
from dial_mcp.tool_filter import filter_write_tools


class TestFilterWriteTools:
    def test_blocks_create_tools(self):
        tools = ["create_event", "list_events", "get_event"]
        result = filter_write_tools(tools)
        assert result == ["list_events", "get_event"]

    def test_blocks_update_tools(self):
        tools = ["update_contact", "search_contacts", "get_contact"]
        result = filter_write_tools(tools)
        assert result == ["search_contacts", "get_contact"]

    def test_blocks_delete_tools(self):
        tools = ["delete_record", "find_records"]
        result = filter_write_tools(tools)
        assert result == ["find_records"]

    def test_blocks_send_tools(self):
        tools = ["send_email", "search_emails", "get_email"]
        result = filter_write_tools(tools)
        assert result == ["search_emails", "get_email"]

    def test_blocks_all_write_patterns(self):
        write_tools = [
            "create_item", "update_item", "delete_item",
            "write_file", "send_message", "post_comment",
            "put_object", "patch_record", "remove_entry",
            "add_member", "set_status", "modify_config",
        ]
        read_tools = ["list_items", "get_item", "search_items", "find_records"]
        all_tools = write_tools + read_tools
        result = filter_write_tools(all_tools)
        assert result == read_tools

    def test_case_insensitive(self):
        tools = ["Create_Event", "LIST_EVENTS", "DELETE_record"]
        result = filter_write_tools(tools)
        assert result == ["LIST_EVENTS"]

    def test_empty_list(self):
        assert filter_write_tools([]) == []

    def test_all_read_tools_pass_through(self):
        tools = ["list_events", "get_event", "search_contacts", "find_records", "check_availability"]
        result = filter_write_tools(tools)
        assert result == tools

    def test_blocks_mid_word_matches(self):
        tools = ["bulk_create_events", "get_updates", "auto_send_report"]
        result = filter_write_tools(tools)
        assert result == []
