import requests
from requests.auth import HTTPBasicAuth

GEOSERVER_URL = "https://geoserver.rottengrapes.tech/geoserver"
WORKSPACE = "Purandar_New"
STORE = "monarch_lmrs"
USERNAME = "admin"
PASSWORD = "geoserver"

NATIVE_CRS = "EPSG:32643"
SERVE_CRS  = "EPSG:3857"

tables = [
    "bag",
    "borewell",
    "bund",
    "district_boundry",
    "gut_bnd",
    "purandar_aoi",
    "purandar_farmers",
    "purandar_tehsil",
    "purandhar_airport_village_bo",
    "purandhar_airport_villages",
    "shed",
    "structures",
    "tree",
    "well",
]

for table in tables:
    url = f"{GEOSERVER_URL}/rest/workspaces/{WORKSPACE}/datastores/{STORE}/featuretypes"
    xml = f"""<featureType>
    <name>{table}</name>
    <nativeName>{table}</nativeName>
    <title>{table}</title>
    <nativeCRS>{NATIVE_CRS}</nativeCRS>
    <srs>{SERVE_CRS}</srs>
    <projectionPolicy>REPROJECT_TO_DECLARED</projectionPolicy>
    <enabled>true</enabled>
</featureType>"""
    headers = {"Content-type": "text/xml"}
    r = requests.post(
        url,
        data=xml,
        headers=headers,
        auth=HTTPBasicAuth(USERNAME, PASSWORD),
    )
    if r.status_code in [200, 201]:
        print(f"Published: {table}")
    else:
        print(f"Failed: {table} - {r.text}")