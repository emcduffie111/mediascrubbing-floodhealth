"""Default data and configuration for the semantic bridge package."""

from __future__ import annotations

from copy import deepcopy

DEFAULT_SCIENCE_BACKBONE = {
    "Water Systems": [
        "Groundwater",
        "Surface Water",
        "Hydrology",
        "Water Management",
    ],
    "Earth and Environmental Change": [
        "Geology",
        "Geophysics",
        "Subsidence",
        "Climate Impacts",
    ],
    "Infrastructure and Operations": [
        "Water Supply Infrastructure",
        "Monitoring Systems",
        "Utilities Planning",
        "Risk Management",
    ],
    "Governance and Decision-Making": [
        "Policy",
        "Regulation",
        "Planning",
        "Stakeholder Engagement",
    ],
    "Society and Economy": [
        "Community Impacts",
        "Economics",
        "Public Communication",
        "Regional Development",
    ],
    "Modeling and Analysis": [
        "Scenario Analysis",
        "Decision Support",
        "Data Integration",
        "Spatial Analysis",
    ],
}


DEFAULT_DOMAIN_KEYWORDS = {
    "Water Systems": ["water", "groundwater", "aquifer", "well", "pumping", "supply"],
    "Earth and Environmental Change": ["subsidence", "land", "surface", "geology", "climate", "environment"],
    "Infrastructure and Operations": ["infrastructure", "utility", "system", "operations", "monitoring", "facility"],
    "Governance and Decision-Making": ["policy", "regulatory", "regulation", "district", "planning", "management"],
    "Society and Economy": ["community", "people", "public", "economic", "residents", "stakeholder"],
    "Modeling and Analysis": ["model", "analysis", "data", "scenario", "decision", "indicator"],
}


DEFAULT_COMPONENT_PATTERNS = {
    "goals": ["goal", "aim", "protect", "maintain", "preserve"],
    "objectives": ["objective", "minimize", "maximize", "reduce"],
    "variables": ["investment", "decision", "strategy", "implementation"],
    "constraints": ["constraint", "limit", "budget", "cannot"],
    "indicators": ["indicator", "measure", "metric", "depth", "damage"],
}


DEFAULT_COMPONENT_SEED_PHRASES = {
    "goals": [
        "desired outcome",
        "long term target",
        "community protection goal",
    ],
    "objectives": [
        "specific measurable objective",
        "optimize system performance",
        "reduce negative impacts",
    ],
    "variables": [
        "decision option",
        "management strategy choice",
        "implementation alternative",
    ],
    "constraints": [
        "budget limitation",
        "policy restriction",
        "feasibility boundary",
    ],
    "indicators": [
        "success metric",
        "performance indicator",
        "measurable signal",
    ],
}


DEFAULT_SVO_VOCABULARY = {
    "water_level": {
        "standard_name": "surface_water_elevation",
        "units": "meters",
        "data_source": "USGS stream gauges",
        "keywords": ["water", "level", "flood", "depth"],
        "domain": "Hydrology",
    },
    "precipitation": {
        "standard_name": "rainfall_rate",
        "units": "mm/hour",
        "data_source": "NOAA precipitation network",
        "keywords": ["rain", "rainfall", "precipitation", "storm"],
        "domain": "Climate Science",
    },
    "groundwater_level": {
        "standard_name": "depth_to_groundwater",
        "units": "meters below surface",
        "data_source": "USGS groundwater monitoring",
        "keywords": ["groundwater", "aquifer", "wells"],
        "domain": "Hydrology",
    },
    "sea_level": {
        "standard_name": "sea_surface_height",
        "units": "meters",
        "data_source": "NOAA tide gauges",
        "keywords": ["sea level", "ocean", "tide", "surge"],
        "domain": "Oceanography",
    },
    "population_at_risk": {
        "standard_name": "exposed_population",
        "units": "count",
        "data_source": "Census data",
        "keywords": ["people", "population", "residents"],
        "domain": "Social Science",
    },
    "economic_damage": {
        "standard_name": "flood_damage_cost",
        "units": "USD",
        "data_source": "HAZUS assessments",
        "keywords": ["damage", "cost", "economic", "loss"],
        "domain": "Economics",
    },
    "infrastructure_vulnerability": {
        "standard_name": "critical_infrastructure_exposure",
        "units": "index",
        "data_source": "Infrastructure inventories",
        "keywords": ["infrastructure", "facilities", "buildings"],
        "domain": "Engineering",
    },
}


SAMPLE_TRANSCRIPTS = {
    "interview_001.txt": """
    Interview with Community Resident - Sarah Martinez
    Date: March 15, 2024

    We've been experiencing significant flooding in our neighborhood during heavy rains.
    The storm drains seem inadequate, and water pools on Main Street for hours.
    Several basements have flooded in the past year.

    Our primary goal is to protect our homes and preserve property values in this neighborhood.
    We need to maintain safe access to schools and emergency services even during storm events.

    The main objective should be to minimize flood damage to residential properties and reduce
    the frequency of street closures. We're looking at different investment options for
    stormwater management, but we have a budget constraint of about $2 million from the city
    council allocation.

    I think we need better drainage infrastructure as our decision variable. The implementation
    strategy could include both green and gray infrastructure. We cannot exceed the current
    budget without additional grant funding.

    We should use flood depth as a key indicator of success, measuring the water depth on
    Main Street during storm events. Another important metric would be the number of properties
    with basement flooding per year.
    """,
    "interview_002.txt": """
    Interview with Local Business Owner - James Chen
    Date: March 18, 2024

    The flooding issue is directly related to new development upstream. Since they built
    the shopping center, our area gets much more runoff during storms.

    Our goal is to protect local businesses from flood damage while maintaining economic
    vitality downtown. We aim to preserve the historic character of our business district.

    The key objective here is to maximize stormwater retention upstream and minimize runoff
    reaching our downtown area. We need green infrastructure like retention ponds and
    permeable pavement as part of our strategy.

    The investment decision should consider both short-term fixes and long-term solutions.
    We face a major constraint - the shopping center owner won't participate unless required
    by regulation. We also have a time limit since hurricane season starts in June.

    I'd suggest tracking business interruption days as an indicator of improvement. We should
    measure economic damage in dollars per storm event. The depth of flooding in parking areas
    would be another useful metric to monitor progress.
    """,
    "meeting_notes_001.txt": """
    Community Stakeholder Meeting - Flood Mitigation Planning
    Date: March 22, 2024
    Attendees: 45 residents, city council members, county planning staff

    Meeting Summary:

    Community members reported increased flooding frequency over the past five years.
    Main concerns include inadequate drainage, upstream development impacts, and aging infrastructure.

    GOALS IDENTIFIED:
    - Protect residential and commercial properties from flood damage
    - Maintain neighborhood livability and safety during storm events
    - Preserve environmental quality of local waterways
    - Aim to restore pre-development runoff conditions

    OBJECTIVES DISCUSSED:
    - Minimize flood damage costs to the community
    - Reduce flood depth on critical roadways by 50%
    - Maximize green infrastructure implementation where feasible

    DECISION VARIABLES:
    - Infrastructure investment levels (ranging from $1M to $5M)
    - Strategy selection: gray infrastructure vs. green infrastructure vs. hybrid
    - Implementation timeline: phased over 3 years vs. comprehensive approach

    CONSTRAINTS IDENTIFIED:
    - Budget limit of $2.5 million from city general fund
    - Cannot disrupt traffic on Main Street for more than 2 weeks
    - Must comply with historic district design guidelines
    - Limited right-of-way for new infrastructure

    PERFORMANCE INDICATORS:
    - Measure flood depth at 5 key monitoring locations
    - Track number of flood events per year exceeding 6 inches
    - Calculate economic damage per storm event
    - Monitor basement flooding frequency as a key metric
    - Assess stormwater quality indicators (pollutant levels)

    Proposed solutions include comprehensive stormwater management systems, coordination
    with county planning on upstream development, and establishment of maintenance protocols.

    Next steps: Form technical committee to evaluate decision alternatives using
    multi-criteria decision analysis framework.
    """,
    "stakeholder_report.txt": """
    Stormwater Infrastructure Assessment Report
    Prepared by: City Engineering Department
    Date: April 1, 2024

    EXECUTIVE SUMMARY

    This report evaluates stormwater management alternatives for the downtown district
    experiencing chronic flooding issues.

    PROJECT GOALS:
    The overarching goal is to protect the community from flood hazards while preserving
    environmental resources. We aim to maintain infrastructure resilience under future
    climate conditions.
    """,
}


def default_science_backbone() -> dict[str, list[str]]:
    return deepcopy(DEFAULT_SCIENCE_BACKBONE)


def default_svo_vocabulary() -> dict[str, dict[str, object]]:
    return deepcopy(DEFAULT_SVO_VOCABULARY)
