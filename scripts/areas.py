"""Areas covered by the app. Collectors take the area name as their first argument (default: shoreditch).
Shoreditch keeps its files in data/; other areas write to data/<area>/."""
import os, sys

AREAS = {
    'shoreditch': {'label': 'Shoreditch & Hoxton', 'center': (51.527626, -0.083849), 'cases_radius': 400, 'venues_radius': 900,
                   'outward': {'E1', 'E2', 'E8', 'N1', 'EC2'}, 'ch_locations': ['E1', 'E2', 'E8', 'N1', 'EC2A', 'EC2M', 'EC2Y', 'EC2R', 'EC2V', 'EC2N']},
    'richmond': {'label': 'Richmond & St Margarets', 'center': (51.4593, -0.3109), 'cases_radius': 1100, 'venues_radius': 1300,
                 'outward': {'TW1', 'TW9', 'TW10'}, 'ch_locations': ['TW1', 'TW9', 'TW10']},
}

def current():
    name = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in AREAS else 'shoreditch'
    return name, AREAS[name]

def data_path(name, file):
    d = 'data' if name == 'shoreditch' else os.path.join('data', name)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, file)
