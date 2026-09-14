"""Deterministic mock data for local development and tests.

Mock mode is strictly non-production (the config layer refuses to start a
production process with mock mode enabled).
"""

from __future__ import annotations

import json

LATEST_MONTH = "2024-06-01T00:00:00.000Z"
PREVIOUS_MONTH = "2024-05-01T00:00:00.000Z"

# Complete community-area list so mock-mode selection and the local boundary
# fallback exercise the same 77-area interaction model as production.
NEIGHBORHOODS: list[tuple[int, str]] = [
(1, "Rogers Park"),
    (2, "West Ridge"),
    (3, "Uptown"),
    (4, "Lincoln Square"),
    (5, "North Center"),
    (6, "Lake View"),
    (7, "Lincoln Park"),
    (8, "Near North Side"),
    (9, "Edison Park"),
    (10, "Norwood Park"),
    (11, "Jefferson Park"),
    (12, "Forest Glen"),
    (13, "North Park"),
    (14, "Albany Park"),
    (15, "Portage Park"),
    (16, "Irving Park"),
    (17, "Dunning"),
    (18, "Montclare"),
    (19, "Belmont Cragin"),
    (20, "Hermosa"),
    (21, "Avondale"),
    (22, "Logan Square"),
    (23, "Humboldt Park"),
    (24, "West Town"),
    (25, "Austin"),
    (26, "West Garfield Park"),
    (27, "East Garfield Park"),
    (28, "Near West Side"),
    (29, "North Lawndale"),
    (30, "South Lawndale"),
    (31, "Lower West Side"),
    (32, "Loop"),
    (33, "Near South Side"),
    (34, "Armour Square"),
    (35, "Douglas"),
    (36, "Oakland"),
    (37, "Fuller Park"),
    (38, "Grand Boulevard"),
    (39, "Kenwood"),
    (40, "Washington Park"),
    (41, "Hyde Park"),
    (42, "Woodlawn"),
    (43, "South Shore"),
    (44, "Chatham"),
    (45, "Avalon Park"),
    (46, "South Chicago"),
    (47, "Burnside"),
    (48, "Calumet Heights"),
    (49, "Roseland"),
    (50, "Pullman"),
    (51, "South Deering"),
    (52, "East Side"),
    (53, "West Pullman"),
    (54, "Riverdale"),
    (55, "Hegewisch"),
    (56, "Garfield Ridge"),
    (57, "Archer Heights"),
    (58, "Brighton Park"),
    (59, "McKinley Park"),
    (60, "Bridgeport"),
    (61, "New City"),
    (62, "West Elsdon"),
    (63, "Gage Park"),
    (64, "Clearing"),
    (65, "West Lawn"),
    (66, "Chicago Lawn"),
    (67, "West Englewood"),
    (68, "Englewood"),
    (69, "Greater Grand Crossing"),
    (70, "Ashburn"),
    (71, "Auburn Gresham"),
    (72, "Beverly"),
    (73, "Washington Heights"),
    (74, "Mount Greenwood"),
    (75, "Morgan Park"),
    (76, "O'Hare"),
    (77, "Edgewater"),
]

# Per-neighborhood latest-month metrics keyed by community_area.
# Fields mirror gold_latest_neighborhood_pulse columns used by the pulse query.
_PULSE: dict[int, dict] = {
    25: {  # Austin
        "service_request_count": 4820,
        "previous_month_request_count": 4210,
        "request_count_mom_pct": 14.49,
        "open_request_count": 640,
        "closed_request_count": 4180,
        "avg_resolution_days": 8.7,
        "new_license_issues": 74,
        "previous_month_new_license_issues": 66,
        "permit_count": 61,
        "previous_month_permit_count": 58,
        "new_construction_permit_count": 4,
        "total_permit_fees": 128400.0,
        "violation_count": 512,
        "previous_month_violation_count": 470,
        "open_violation_count": 210,
        "business_data_available": True,
        "permit_data_available": True,
        "violation_data_available": True,
    },
    6: {  # Lake View
        "service_request_count": 5230,
        "previous_month_request_count": 5510,
        "request_count_mom_pct": -5.08,
        "open_request_count": 410,
        "closed_request_count": 4820,
        "avg_resolution_days": 5.2,
        "new_license_issues": 188,
        "previous_month_new_license_issues": 172,
        "permit_count": 143,
        "previous_month_permit_count": 130,
        "new_construction_permit_count": 9,
        "total_permit_fees": 402100.0,
        "violation_count": 96,
        "previous_month_violation_count": 88,
        "open_violation_count": 22,
        "business_data_available": True,
        "permit_data_available": True,
        "violation_data_available": True,
    },
    24: {  # West Town
        "service_request_count": 4990,
        "previous_month_request_count": 4550,
        "request_count_mom_pct": 9.67,
        "open_request_count": 520,
        "closed_request_count": 4470,
        "avg_resolution_days": 6.1,
        "new_license_issues": 154,
        "previous_month_new_license_issues": 149,
        "permit_count": 121,
        "previous_month_permit_count": 118,
        "new_construction_permit_count": 7,
        "total_permit_fees": 351200.0,
        "violation_count": 178,
        "previous_month_violation_count": 165,
        "open_violation_count": 61,
        "business_data_available": True,
        "permit_data_available": True,
        "violation_data_available": True,
    },
    7: {  # Lincoln Park
        "service_request_count": 4110,
        "previous_month_request_count": 4020,
        "request_count_mom_pct": 2.24,
        "open_request_count": 300,
        "closed_request_count": 3810,
        "avg_resolution_days": 4.8,
        "new_license_issues": 132,
        "previous_month_new_license_issues": 141,
        "permit_count": 108,
        "previous_month_permit_count": 96,
        "new_construction_permit_count": 6,
        "total_permit_fees": 288900.0,
        "violation_count": 74,
        "previous_month_violation_count": 70,
        "open_violation_count": 15,
        "business_data_available": True,
        "permit_data_available": True,
        "violation_data_available": True,
    },
    76: {  # O'Hare — sparse business/permit data to exercise N/A rendering
        "service_request_count": 640,
        "previous_month_request_count": 590,
        "request_count_mom_pct": 8.47,
        "open_request_count": 70,
        "closed_request_count": 570,
        "avg_resolution_days": 11.4,
        "new_license_issues": None,
        "previous_month_new_license_issues": None,
        "permit_count": None,
        "previous_month_permit_count": None,
        "new_construction_permit_count": None,
        "total_permit_fees": None,
        "violation_count": 12,
        "previous_month_violation_count": 9,
        "open_violation_count": 5,
        "business_data_available": False,
        "permit_data_available": False,
        "violation_data_available": True,
    },
}

_DEFAULT_PULSE = {
    "service_request_count": 2100,
    "previous_month_request_count": 2000,
    "request_count_mom_pct": 5.0,
    "open_request_count": 240,
    "closed_request_count": 1860,
    "avg_resolution_days": 7.0,
    "new_license_issues": 40,
    "previous_month_new_license_issues": 38,
    "permit_count": 30,
    "previous_month_permit_count": 28,
    "new_construction_permit_count": 2,
    "total_permit_fees": 75000.0,
    "violation_count": 90,
    "previous_month_violation_count": 84,
    "open_violation_count": 30,
    "business_data_available": True,
    "permit_data_available": True,
    "violation_data_available": True,
}

_TREND_MONTHS = [
    "2023-07-01T00:00:00.000Z",
    "2023-08-01T00:00:00.000Z",
    "2023-09-01T00:00:00.000Z",
    "2023-10-01T00:00:00.000Z",
    "2023-11-01T00:00:00.000Z",
    "2023-12-01T00:00:00.000Z",
    "2024-01-01T00:00:00.000Z",
    "2024-02-01T00:00:00.000Z",
    "2024-03-01T00:00:00.000Z",
    "2024-04-01T00:00:00.000Z",
    "2024-05-01T00:00:00.000Z",
    "2024-06-01T00:00:00.000Z",
]

_SERVICE_TYPES = [
    ("Graffiti Removal", 980),
    ("Rodent Baiting / Rat Complaint", 760),
    ("Pothole in Street", 610),
    ("Tree Trim", 430),
    ("Weed Removal", 380),
    ("Abandoned Vehicle", 350),
    ("Street Light Out", 300),
    ("Sanitation Code Violation", 260),
    ("Aircraft Noise Complaint", 210),
    ("Broken Sidewalk", 180),
]

FRESHNESS = [
    ("311 Service Requests", 14500000, "2019-01-01", "2024-06-30"),
    ("Business Licenses", 210000, "2018-01-01", "2024-06-28"),
    ("Building Permits", 185000, "2018-01-01", "2024-06-29"),
    ("Building Violations", 640000, "2018-01-01", "2024-06-27"),
]

SUCCESSFUL_DATASET_RUNS = {
    "311 Service Requests": "2024-07-01T06:12:00.000Z",
    "Business Licenses": "2024-07-01T06:14:00.000Z",
    "Building Permits": "2024-07-01T06:15:00.000Z",
    "Building Violations": "2024-07-01T06:16:00.000Z",
}

PIPELINE_RUN = {
    "run_id": "mock-successful-run",
    "started_at": "2024-07-01T06:00:00.000Z",
    "completed_at": "2024-07-01T06:20:00.000Z",
    "status": "SUCCESS",
    "message": "Daily refresh and validation completed successfully",
    "last_success_at": "2024-07-01T06:20:00.000Z",
}


def pulse_for(community_area: int) -> dict:
    return _PULSE.get(community_area, _DEFAULT_PULSE)


def name_for(community_area: int) -> str:
    for ca, name in NEIGHBORHOODS:
        if ca == community_area:
            return name
    return f"Community Area {community_area}"


def trend_for(community_area: int) -> list[list]:
    base = pulse_for(community_area)["service_request_count"] or 2000
    rows = []
    for i, month in enumerate(_TREND_MONTHS):
        # Gentle seasonal wave around the base value.
        factor = 0.82 + 0.06 * (i % 4)
        rows.append([month, int(base * factor)])
    return rows


def service_types_for(community_area: int) -> list[list]:
    scale = (pulse_for(community_area)["service_request_count"] or 2000) / 4820
    return [[name, int(v * scale)] for name, v in _SERVICE_TYPES]


def _square_geojson(col: int, row: int) -> str:
    # Small square polygon on a grid near Chicago's bounding box.
    x0 = -87.90 + col * 0.06
    y0 = 41.65 + row * 0.05
    x1, y1 = x0 + 0.055, y0 + 0.045
    return json.dumps(
        {
            "type": "Polygon",
            "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
        }
    )


def geo_rows() -> list[list]:
    rows = []
    for idx, (ca, name) in enumerate(NEIGHBORHOODS):
        col = idx % 6
        row = idx // 6
        rows.append([ca, name, _square_geojson(col, row)])
    return rows
