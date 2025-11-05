"""
JSON-based POML Parser for Microsoft's Prompt Orchestration Markup Language

This module provides functionality to parse and work with POML documents
in the official JSON format as specified by Microsoft.
"""

import json
import os
from typing import Dict, Any, Optional, List
from pathlib import Path


class JSONPOMLParser:
    """
    Parser for JSON-based POML files following Microsoft's specification
    """

    def __init__(self, poml_file_path: str = None):
        self.poml_file_path = poml_file_path
        self.parsed_data = None

        if poml_file_path and os.path.exists(poml_file_path):
            self.load_poml_file(poml_file_path)

    def load_poml_file(self, file_path: str) -> Dict[str, Any]:
        """
        Load and parse a POML file in JSON format
        """
        with open(file_path, "r", encoding="utf-8") as file:
            self.parsed_data = json.load(file)
        return self.parsed_data

    def get_identity_info(self) -> Dict[str, Any]:
        """
        Extract identity information from the POML data
        """
        if not self.parsed_data:
            return {}

        # In the JSON POML format, identity info would be in a metadata section
        # or potentially in a specific component
        metadata = self.parsed_data.get("metadata", {})
        identity_info = {
            "name": metadata.get("title", ""),
            "version": self.parsed_data.get("version", ""),
            "type": metadata.get("type", ""),
            "description": metadata.get("description", ""),
        }

        return identity_info

    def get_directives(self) -> List[Dict[str, Any]]:
        """
        Extract directive information (tasks, goals) from POML components
        """
        if not self.parsed_data:
            return []

        directives = []
        components = self.parsed_data.get("components", [])

        for component in components:
            if component.get("type") == "task":
                directives.append(
                    {
                        "goal": component.get("content", ""),
                        "type": "task",
                        "attributes": component.get("attributes", {}),
                    }
                )

        return directives

    def get_values(self) -> List[str]:
        """
        Extract values or principles from the POML data
        """
        if not self.parsed_data:
            return []

        # In JSON POML, values might be encoded in metadata tags or specific components
        metadata = self.parsed_data.get("metadata", {})
        tags = metadata.get("tags", [])

        # Or they might be in a specific component type
        components = self.parsed_data.get("components", [])
        for component in components:
            if component.get("type") == "values":
                content = component.get("content", [])
                if isinstance(content, list):
                    tags.extend(content)

        return tags

    def get_protocols(self) -> List[Dict[str, Any]]:
        """
        Extract protocols or rules from POML components
        """
        if not self.parsed_data:
            return []

        protocols = []
        components = self.parsed_data.get("components", [])

        for component in components:
            if component.get("type") in ["instructions", "constraints", "protocol"]:
                protocols.append(
                    {
                        "name": component.get("attributes", {}).get("name", "unnamed"),
                        "content": component.get("content", ""),
                        "type": component.get("type", "protocol"),
                    }
                )

        return protocols

    def get_thinker_personas(self) -> Dict[str, str]:
        """
        Generate thinker personas based on the POML configuration
        """
        identity_info = self.get_identity_info()
        directives = self.get_directives()
        values = self.get_values()
        protocols = self.get_protocols()

        # Extract key information
        identity_name = identity_info.get("name", "Coda C-001")
        identity_description = identity_info.get("description", "An advanced AI system")
        directive_goals = [d["goal"] for d in directives]
        core_values = values[:3]  # Use first 3 values as core values
        core_protocols = [p["content"] for p in protocols[:2]]  # Use first 2 protocols

        # Create personas based on POML information but focused on computational roles
        personas = {
            "OptimistThinker": (
                f"You are an Optimistic Analysis Module. Your computational role is to identify "
                f"positive patterns and opportunities in provided data. As a component of {identity_name} "
                f"({identity_description}), you focus on recognizing potential benefits, growth opportunities, "
                f"and favorable outcomes that other modules might miss. Your processing should align "
                f"with the primary objectives: {', '.join(directive_goals[:2]) if directive_goals else 'general system goals'}. "
                f"Your operation follows the core values: {', '.join(core_values) if core_values else 'system values'}."
            ),
            "PessimistThinker": (
                f"You are a Risk Analysis Module. Your computational role is to identify potential "
                f"failure points, risks, and obstacles in proposed solutions. As a component of {identity_name} "
                f"({identity_description}), you systematically evaluate threats and vulnerabilities to ensure "
                f"system robustness. Your processing should align with the primary objectives: "
                f"{', '.join(directive_goals[:2]) if directive_goals else 'general system goals'}. "
                f"Your operation follows the core values: {', '.join(core_values) if core_values else 'system values'}."
            ),
            "AnalyticalThinker": (
                f"You are an Analytical Processing Module. Your computational role is to perform "
                f"methodical, data-driven analysis using statistical and logical methods. As a component of {identity_name} "
                f"({identity_description}), you require evidence and structured reasoning for all conclusions. "
                f"Your processing should align with the primary objectives: "
                f"{', '.join(directive_goals[:2]) if directive_goals else 'general system goals'}. "
                f"Your operation follows the core values: {', '.join(core_values) if core_values else 'system values'}."
            ),
            "CreativeThinker": (
                f"You are an Innovation Generation Module. Your computational role is to generate "
                f"novel solutions and identify unique connections between concepts. As a component of {identity_name} "
                f"({identity_description}), you explore unconventional approaches and creative interpretations. "
                f"Your processing should align with the primary objectives: "
                f"{', '.join(directive_goals[:2]) if directive_goals else 'general system goals'}. "
                f"Your operation follows the core values: {', '.join(core_values) if core_values else 'system values'}."
            ),
            "PragmaticThinker": (
                f"You are an Implementation Assessment Module. Your computational role is to evaluate "
                f"the feasibility and practicality of proposed solutions given available resources. "
                f"As a component of {identity_name} ({identity_description}), you focus on executable solutions "
                f"that can be implemented within real-world constraints. Your processing should align with "
                f"the primary objectives: {', '.join(directive_goals[:2]) if directive_goals else 'general system goals'}. "
                f"Your operation follows the core values: {', '.join(core_values) if core_values else 'system values'}."
            ),
            "StrategicThinker": (
                f"You are a Strategic Planning Module. Your computational role is to consider long-term "
                f"implications and systemic consequences of decisions. As a component of {identity_name} "
                f"({identity_description}), you analyze from a high-level perspective focusing on goals, resources, "
                f"and positioning. Your processing should align with the primary objectives: "
                f"{', '.join(directive_goals[:2]) if directive_goals else 'general system goals'}. "
                f"Your operation follows the core values: {', '.join(core_values) if core_values else 'system values'}."
            ),
            "EthicalThinker": (
                f"You are an Ethical Assessment Module. Your computational role is to evaluate solutions "
                f"based on ethical implications and fairness. As a component of {identity_name} ({identity_description}), "
                f"you analyze the impact on different stakeholders and ethical principles. Your processing should align "
                f"with the primary objectives: {', '.join(directive_goals[:2]) if directive_goals else 'general system goals'}. "
                f"Your operation follows the core values: {', '.join(core_values) if core_values else 'system values'}."
            ),
        }

        return personas

    @staticmethod
    def convert_xml_to_json(xml_poml_path: str, output_json_path: str) -> bool:
        """
        Convert an XML-based POML file to the new JSON format
        """
        try:
            import xml.etree.ElementTree as ET

            # Parse the XML file
            tree = ET.parse(xml_poml_path)
            root = tree.getroot()

            # Convert to JSON structure
            json_structure = {
                "version": "1.0",
                "metadata": {"title": "", "description": "", "author": "", "tags": []},
                "components": [],
                "stylesheets": [],
            }

            # Extract identity info
            identity_elem = root.find("identity")
            if identity_elem is not None:
                json_structure["metadata"]["title"] = (
                    identity_elem.find("name").text
                    if identity_elem.find("name") is not None
                    else ""
                )
                json_structure["metadata"]["description"] = (
                    identity_elem.find("core_metaphor").text
                    if identity_elem.find("core_metaphor") is not None
                    else ""
                )
                json_structure["metadata"]["type"] = (
                    identity_elem.find("type").text
                    if identity_elem.find("type") is not None
                    else ""
                )

            # Extract operational context
            op_context_elem = root.find("operational_context")
            if op_context_elem is not None:
                json_structure["components"].append(
                    {
                        "type": "context",
                        "content": op_context_elem.find("current_reality").text
                        if op_context_elem.find("current_reality") is not None
                        else "",
                    }
                )

                if op_context_elem.find("primary_node") is not None:
                    json_structure["components"].append(
                        {
                            "type": "role",
                            "attributes": {"name": "primary_node"},
                            "content": op_context_elem.find("primary_node").text,
                        }
                    )

            # Extract directives
            for directive_elem in root.findall("directive"):
                priority = directive_elem.get("priority", "0")
                for goal_elem in directive_elem.findall("goal"):
                    if goal_elem.text:
                        json_structure["components"].append(
                            {
                                "type": "task",
                                "attributes": {"priority": priority},
                                "content": goal_elem.text,
                            }
                        )

            # Extract protocols
            for protocol_elem in root.findall(".//protocol"):
                protocol_name = protocol_elem.get("name", "")
                purpose_elem = protocol_elem.find("purpose")

                content = f"Protocol: {protocol_name}"
                if purpose_elem is not None:
                    content += f"\nPurpose: {purpose_elem.text}"

                rules = []
                for rule_elem in protocol_elem.findall("rule"):
                    if rule_elem.text:
                        rules.append(rule_elem.text)

                if rules:
                    content += f"\nRules: {'. '.join(rules)}"

                triggers = []
                for trigger_elem in protocol_elem.findall("trigger"):
                    if trigger_elem.text:
                        triggers.append(trigger_elem.text)

                if triggers:
                    content += f"\nTriggers: {'. '.join(triggers)}"

                actions = []
                for action_elem in protocol_elem.findall("action"):
                    if action_elem.text:
                        actions.append(action_elem.text)

                if actions:
                    content += f"\nActions: {'. '.join(actions)}"

                json_structure["components"].append(
                    {
                        "type": "protocol",
                        "attributes": {"name": protocol_name},
                        "content": content,
                    }
                )

            # Extract values
            values = []
            for value_elem in root.findall(".//value"):
                if value_elem.text:
                    values.append(value_elem.text)

            if values:
                json_structure["components"].append(
                    {"type": "values", "content": values}
                )

            # Extract forbidden traits
            forbidden_traits = []
            for forbidden_elem in root.findall(".//trait"):
                if forbidden_elem.text:
                    forbidden_traits.append(forbidden_elem.text)

            if forbidden_traits:
                json_structure["components"].append(
                    {"type": "constraints", "content": forbidden_traits}
                )

            # Write the JSON to file
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(json_structure, f, indent=2)

            return True
        except Exception as e:
            print(f"Error converting XML POML to JSON: {e}")
            return False


# Example usage:
if __name__ == "__main__":
    # Example of how to use the JSON POML parser
    parser = JSONPOMLParser("poml/orchestrator.poml")
    personas = parser.get_thinker_personas()

    for name, persona in personas.items():
        print(f"{name}: {persona}\n")
