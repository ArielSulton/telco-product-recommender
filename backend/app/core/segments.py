from typing import Dict, Any

# Define a mapping for segment_id to its detailed properties
# These properties are used by the frontend to display segment information
SEGMENTS_MAP: Dict[int, Dict[str, Any]] = {
    0: {
        "segment_id": 0,
        "name": "Budget-Conscious",
        "description": "Users who are sensitive to price and seek affordable options.",
        "icon": "💰",
        "color": "green" # Tailwind color prefix
    },
    1: {
        "segment_id": 1,
        "name": "Data Enthusiast",
        "description": "Heavy data users who prioritize large data quotas and fast speeds.",
        "icon": "🚀",
        "color": "purple"
    },
    2: {
        "segment_id": 2,
        "name": "Social Connector",
        "description": "Users who frequently use social media and messaging apps.",
        "icon": "💬",
        "color": "pink"
    },
    3: {
        "segment_id": 3,
        "name": "Balanced User",
        "description": "Users with moderate usage across data, voice, and SMS.",
        "icon": "⚖️",
        "color": "blue"
    },
    # Add more segments as defined by your ML model
}

def get_segment_details(segment_id: int) -> Dict[str, Any]:
    """
    Retrieves segment details by ID.
    Returns a default 'Unknown' segment if ID is not found.
    """
    return SEGMENTS_MAP.get(segment_id, {
        "segment_id": segment_id,
        "name": "Unknown Segment",
        "description": "This user belongs to an unrecognized segment.",
        "icon": "❓",
        "color": "gray"
    })
