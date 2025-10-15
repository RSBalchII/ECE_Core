import pytest
import asyncio
import httpx
from unittest.mock import AsyncMock, patch
from utcp.utcp_client import UtcpClient
from utcp.data.tool import Tool


@pytest.mark.asyncio
async def test_orchestrator_tool_registration():
    """Test that the Orchestrator agent registers its tools with the UTCP Registry."""
    # Import the Orchestrator agent
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'ece', 'agents', 'tier1', 'orchestrator'))
    
    # Mock the UTCP client to capture tool registrations
    with patch('ece.agents.tier1.orchestrator.orchestrator_agent.UTCPClient') as mock_utcp_client_class:
        mock_utcp_client = AsyncMock()
        mock_utcp_client_class.return_value = mock_utcp_client
        
        # Mock successful tool registration
        mock_utcp_client.register_tool.return_value = True
        
        # Import and initialize the Orchestrator agent
        from ece.agents.tier1.orchestrator.orchestrator_agent import OrchestratorAgent
        
        # Create a mock session ID
        orchestrator = OrchestratorAgent(session_id="test_session")
        
        # Wait for the registration task to complete
        # Note: In a real test, we would need to properly await the registration task
        # For this test, we'll just verify that the UTCP client was called
        
        # Verify that the UTCP client was initialized with the correct URL
        mock_utcp_client_class.assert_called_once_with("http://utcp-registry:8005")
        
        # Verify that register_tool was called for each tool
        assert mock_utcp_client.register_tool.call_count >= 2
        
        # Verify the first tool registration (process_prompt)
        call_args_list = mock_utcp_client.register_tool.call_args_list
        first_call_args = call_args_list[0][0][0]  # First call, first argument
        assert isinstance(first_call_args, ToolDefinition)
        assert first_call_args.id == "orchestrator.process_prompt"
        assert first_call_args.name == "Process Prompt"
        assert first_call_args.agent == "Orchestrator"
        
        # Verify the second tool registration (get_analysis_result)
        second_call_args = call_args_list[1][0][0]  # Second call, first argument
        assert isinstance(second_call_args, ToolDefinition)
        assert second_call_args.id == "orchestrator.get_analysis_result"
        assert second_call_args.name == "Get Analysis Result"
        assert second_call_args.agent == "Orchestrator"


@pytest.mark.asyncio
async def test_archivist_tool_registration():
    """Test that the Archivist agent registers its tools with the UTCP Registry."""
    # Import the Archivist agent app
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'ece', 'agents', 'tier3', 'archivist'))
    
    # Mock the UTCP client to capture tool registrations
    with patch('ece.agents.tier3.archivist.archivist_agent.UTCPClient') as mock_utcp_client_class:
        mock_utcp_client = AsyncMock()
        mock_utcp_client_class.return_value = mock_utcp_client
        
        # Mock successful tool registration
        mock_utcp_client.register_tool.return_value = True
        
        # Import the Archivist app to trigger startup event
        from ece.agents.tier3.archivist import archivist_agent
        
        # Call the startup event directly to trigger tool registration
        await archivist_agent.startup_event()
        
        # Verify that the UTCP client was initialized with the correct URL
        mock_utcp_client_class.assert_called_once_with("http://utcp-registry:8005")
        
        # Verify that register_tool was called for each tool
        assert mock_utcp_client.register_tool.call_count >= 3
        
        # Collect all registered tools
        registered_tools = []
        for call_args in mock_utcp_client.register_tool.call_args_list:
            tool_definition = call_args[0][0]
            assert isinstance(tool_definition, ToolDefinition)
            registered_tools.append(tool_definition)
        
        # Verify all expected tools were registered
        tool_ids = [tool.id for tool in registered_tools]
        expected_tool_ids = [
            "archivist.get_context",
            "archivist.get_enhanced_context", 
            "archivist.memory_query"
        ]
        
        for expected_id in expected_tool_ids:
            assert expected_id in tool_ids, f"Expected tool {expected_id} was not registered"
        
        # Verify specific tool properties
        for tool in registered_tools:
            if tool.id == "archivist.get_context":
                assert tool.name == "Get Context"
                assert tool.agent == "Archivist"
                assert tool.category == "retrieval"
            elif tool.id == "archivist.get_enhanced_context":
                assert tool.name == "Get Enhanced Context"
                assert tool.agent == "Archivist"
                assert tool.category == "retrieval"
            elif tool.id == "archivist.memory_query":
                assert tool.name == "Memory Query"
                assert tool.agent == "Archivist"
                assert tool.category == "retrieval"


@pytest.mark.asyncio
async def test_distiller_tool_registration():
    """Test that the Distiller agent registers its tools with the UTCP Registry."""
    # Import the Distiller agent app
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'ece', 'agents', 'tier3', 'distiller'))
    
    # Mock the UTCP client to capture tool registrations
    with patch('ece.agents.tier3.distiller.distiller_agent.UTCPClient') as mock_utcp_client_class:
        mock_utcp_client = AsyncMock()
        mock_utcp_client_class.return_value = mock_utcp_client
        
        # Mock successful tool registration
        mock_utcp_client.register_tool.return_value = True
        
        # Import the Distiller app to trigger startup event
        from ece.agents.tier3.distiller import distiller_agent
        
        # Create a mock app state to hold the UTCP client
        class MockAppState:
            pass
            
        distiller_agent.app.state = MockAppState()
        
        # Call the startup event directly to trigger tool registration
        await distiller_agent.startup_event()
        
        # Verify that the UTCP client was initialized with the correct URL
        mock_utcp_client_class.assert_called_once_with("http://utcp-registry:8005")
        
        # Verify that register_tool was called
        assert mock_utcp_client.register_tool.call_count >= 1
        
        # Verify the tool registration
        call_args = mock_utcp_client.register_tool.call_args
        tool_definition = call_args[0][0]
        assert isinstance(tool_definition, ToolDefinition)
        assert tool_definition.id == "distiller.process_text"
        assert tool_definition.name == "Process Text"
        assert tool_definition.agent == "Distiller"
        assert tool_definition.category == "processing"


@pytest.mark.asyncio
async def test_qlearning_tool_registration():
    """Test that the QLearning agent registers its tools with the UTCP Registry."""
    # Import the QLearning agent app
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'ece', 'agents', 'tier3', 'qlearning'))
    
    # Mock the UTCP client to capture tool registrations
    with patch('ece.agents.tier3.qlearning.qlearning_app.UTCPClient') as mock_utcp_client_class:
        mock_utcp_client = AsyncMock()
        mock_utcp_client_class.return_value = mock_utcp_client
        
        # Mock successful tool registration
        mock_utcp_client.register_tool.return_value = True
        
        # Import the QLearning app to trigger startup event
        from ece.agents.tier3.qlearning import qlearning_app
        
        # Create a mock app state to hold the UTCP client
        class MockAppState:
            pass
            
        qlearning_app.app.state = MockAppState()
        
        # Call the startup event directly to trigger tool registration
        await qlearning_app.startup_event()
        
        # Verify that the UTCP client was initialized with the correct URL
        mock_utcp_client_class.assert_called_once_with("http://utcp-registry:8005")
        
        # Verify that register_tool was called for each tool
        assert mock_utcp_client.register_tool.call_count >= 2
        
        # Collect all registered tools
        registered_tools = []
        for call_args in mock_utcp_client.register_tool.call_args_list:
            tool_definition = call_args[0][0]
            assert isinstance(tool_definition, ToolDefinition)
            registered_tools.append(tool_definition)
        
        # Verify all expected tools were registered
        tool_ids = [tool.id for tool in registered_tools]
        expected_tool_ids = [
            "qlearning.find_optimal_path",
            "qlearning.refine_relationships"
        ]
        
        for expected_id in expected_tool_ids:
            assert expected_id in tool_ids, f"Expected tool {expected_id} was not registered"
        
        # Verify specific tool properties
        for tool in registered_tools:
            if tool.id == "qlearning.find_optimal_path":
                assert tool.name == "Find Optimal Path"
                assert tool.agent == "QLearning"
                assert tool.category == "analysis"
            elif tool.id == "qlearning.refine_relationships":
                assert tool.name == "Refine Relationships"
                assert tool.agent == "QLearning"
                assert tool.category == "analysis"


@pytest.mark.asyncio
async def test_injector_tool_registration():
    """Test that the Injector agent registers its tools with the UTCP Registry."""
    # Import the Injector agent app
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'ece', 'agents', 'tier3', 'injector'))
    
    # Mock the UTCP client to capture tool registrations
    with patch('ece.agents.tier3.injector.injector_app.UTCPClient') as mock_utcp_client_class:
        mock_utcp_client = AsyncMock()
        mock_utcp_client_class.return_value = mock_utcp_client
        
        # Mock successful tool registration
        mock_utcp_client.register_tool.return_value = True
        
        # Import the Injector app to trigger startup event
        from ece.agents.tier3.injector import injector_app
        
        # Create a mock app state to hold the UTCP client
        class MockAppState:
            pass
            
        injector_app.app.state = MockAppState()
        
        # Call the startup event directly to trigger tool registration
        await injector_app.startup_event()
        
        # Verify that the UTCP client was initialized with the correct URL
        mock_utcp_client_class.assert_called_once_with("http://utcp-registry:8005")
        
        # Verify that register_tool was called for each tool
        assert mock_utcp_client.register_tool.call_count >= 3
        
        # Collect all registered tools
        registered_tools = []
        for call_args in mock_utcp_client.register_tool.call_args_list:
            tool_definition = call_args[0][0]
            assert isinstance(tool_definition, ToolDefinition)
            registered_tools.append(tool_definition)
        
        # Verify all expected tools were registered
        tool_ids = [tool.id for tool in registered_tools]
        expected_tool_ids = [
            "injector.data_to_inject",
            "injector.get_or_create_timenode",
            "injector.link_memory_to_timenode"
        ]
        
        for expected_id in expected_tool_ids:
            assert expected_id in tool_ids, f"Expected tool {expected_id} was not registered"
        
        # Verify specific tool properties
        for tool in registered_tools:
            if tool.id == "injector.data_to_inject":
                assert tool.name == "Data to Inject"
                assert tool.agent == "Injector"
                assert tool.category == "storage"
            elif tool.id == "injector.get_or_create_timenode":
                assert tool.name == "Get or Create Timenode"
                assert tool.agent == "Injector"
                assert tool.category == "storage"
            elif tool.id == "injector.link_memory_to_timenode":
                assert tool.name == "Link Memory to Timenode"
                assert tool.agent == "Injector"
                assert tool.category == "storage"